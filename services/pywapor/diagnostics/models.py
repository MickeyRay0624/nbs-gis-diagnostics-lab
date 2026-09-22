import hashlib
import json
import math
import os
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pyproj import Transformer
from shapely.geometry import shape, box
from shapely.ops import transform, unary_union

from nbs_prepare.config import validate_config

MODULES = {
    "lulc": "Land-cover change", "fragmentation": "Forest fragmentation",
    "groundwater": "Groundwater storage", "drought": "Drought & vegetation",
    "climate": "Climate extremes", "flood": "River flood hazard",
    "degradation": "Land degradation",
}
ModuleId = Literal["lulc", "fragmentation", "groundwater", "drought", "climate", "flood", "degradation"]
NASA_MODULES = {"groundwater", "drought"}
PUBLIC_MODULES = set(MODULES) - NASA_MODULES
AREA = Transformer.from_crs(4326, 6933, always_xy=True).transform


def nasa_ready(module):
    flag = {"groundwater": "NBS_GLDAS_VERIFIED", "drought": "NBS_MODIS_VERIFIED"}[module]
    verified = os.getenv(flag, os.getenv("NBS_EARTHDATA_VERIFIED", "false"))
    return verified.lower() == "true" and bool(os.getenv("NBS_NASA_USERNAME")) and bool(os.getenv("NBS_NASA_PASSWORD"))


class LandCoverOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    resolution: Literal[30, 50, 100] = 50
    edge_width_m: float = Field(default=50, ge=30, le=1000)
    include_mangroves: bool = True
    count_boundary_as_edge: bool = False

    @model_validator(mode="after")
    def valid_edge(self):
        if self.edge_width_m < self.resolution:
            raise ValueError("Forest edge width must be at least one analysis cell.")
        return self


class DiagnosticRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["ganjam", "custom"] = "ganjam"
    name: str = Field(default="Ganjam District, Odisha", min_length=1, max_length=120)
    modules: list[ModuleId] = Field(default_factory=lambda: list(MODULES), min_length=1, max_length=7)
    boundary: dict | None = None
    config: dict | None = None
    land_cover: LandCoverOptions = Field(default_factory=LandCoverOptions)

    @model_validator(mode="after")
    def validate_job(self):
        if not self.name.strip() or any(ord(c) < 32 for c in self.name):
            raise ValueError("Use a study-area name without control characters.")
        if len(set(self.modules)) != len(self.modules):
            raise ValueError("Select each diagnostic only once.")
        if self.mode == "ganjam":
            if self.boundary is not None or self.config is not None:
                raise ValueError("The Ganjam reference run uses its recorded boundary and periods. Choose a new-area task for custom parameters.")
            if self.land_cover != LandCoverOptions():
                raise ValueError("The Ganjam reference run uses its documented 50 m grid and forest settings.")
            return self
        if not self.boundary or not self.config:
            raise ValueError("A new-area task needs a boundary and analysis parameters.")
        encoded = json.dumps(self.boundary, allow_nan=False).encode()
        if len(encoded) > 190_000:
            raise ValueError("Simplify the boundary to under 190 KB for online submission.")
        if self.boundary.get("type") != "FeatureCollection":
            raise ValueError("Use a WGS84 GeoJSON FeatureCollection.")
        features = self.boundary.get("features", [])
        if not 1 <= len(features) <= 100:
            raise ValueError("Use 1–100 polygon features.")
        try:
            shapes = [shape(f["geometry"]) for f in features]
            if any(g.geom_type not in ("Polygon", "MultiPolygon") or not g.is_valid or g.is_empty or g.has_z for g in shapes):
                raise ValueError("Use valid two-dimensional polygons.")
            geometry = unary_union(shapes)
            w, s, e, n = geometry.bounds
            if not all(math.isfinite(v) for v in (w,s,e,n)) or not (-180 <= w < e <= 180 and -85 <= s < n <= 85) or e-w > 180:
                raise ValueError("Use a WGS84 boundary that does not cross the date line.")
            enclosing = transform(AREA, box(w,s,e,n)).area / 1e6
            if not 0 < enclosing <= 20_000:
                raise ValueError("Online tasks allow an enclosing rectangle up to 20,000 km².")
            if set(self.modules) & {"lulc", "fragmentation"}:
                if enclosing > 2_000 or enclosing * 1e6 / self.land_cover.resolution**2 > 2_000_000:
                    raise ValueError("For new-area land cover and fragmentation, use an enclosing rectangle up to 2,000 km² and at most two million analysis cells.")
        except (KeyError, TypeError) as exc:
            raise ValueError("The GeoJSON boundary is incomplete.") from exc
        config = json.loads(json.dumps(self.config, allow_nan=False))
        config.update(name=self.name, boundarySha256=hashlib.sha256(encoded).hexdigest(), modules=[m for m in self.modules if m not in ("lulc", "fragmentation")] or ["flood"])
        try:
            validate_config(config)
        except (KeyError, TypeError, IndexError) as exc:
            raise ValueError("The analysis configuration is incomplete.") from exc
        if "climate" in self.modules:
            k = config["climate"]
            variables = {"hot":"tasmax", "warm":"tasmin", "frost":"tasmin", "temperature":"tas", "rain":"pr", "dry":"pr"}
            requests = len(k["models"]) * len({variables[m] for m in k["metrics"]}) * (k["baseline"][1]-k["baseline"][0]+1 + len(k["scenarios"])*(k["future"][1]-k["future"][0]+1))
            if requests > 240:
                raise ValueError("This server allows up to 240 annual climate subset requests per task. Keep the intended climate periods and split models or indices into separate tasks.")
        if config["maxDownloadGB"] > 10:
            raise ValueError("Online managed downloads are limited to 10 GB per task.")
        self.config = config
        return self
