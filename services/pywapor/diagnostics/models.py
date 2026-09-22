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


class CrosswalkRow(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    source: int = Field(ge=1, le=65534)
    code: int = Field(ge=0, le=999)
    name: str = Field(min_length=1, max_length=80, pattern=r"^[^\x00-\x1f]+$")
    color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")


class RasterInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    year: int = Field(ge=1900, le=2100)
    upload_id: str = Field(pattern=r"^[a-f0-9]{32}$")


class LandCoverOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    resolution: Literal[30, 50, 100] = 50
    edge_width_m: float = Field(default=50, ge=30, le=1000)
    include_mangroves: bool = True
    count_boundary_as_edge: bool = False
    source: Literal["default", "uploaded"] = "default"
    source_name: str = Field(default="User-supplied land cover", min_length=1, max_length=100)
    years: list[int] | None = Field(default=None, min_length=1, max_length=3)
    rasters: list[RasterInput] = Field(default_factory=list, max_length=3)
    crosswalk: list[CrosswalkRow] | None = Field(default=None, min_length=1, max_length=256)
    forest_codes: list[int] | None = Field(default=None, min_length=1, max_length=64)
    protected_upload_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    oecm_upload_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    protection_note: str = Field(default="", max_length=400)

    @model_validator(mode="after")
    def valid_options(self):
        if self.edge_width_m < self.resolution:
            raise ValueError("Forest edge width must be at least one analysis cell.")
        if self.years is not None and (len(set(self.years))!=len(self.years) or any(y<1900 or y>2100 for y in self.years)):
            raise ValueError("Choose distinct analysis years between 1900 and 2100.")
        if self.source == "uploaded":
            if not self.rasters or self.crosswalk is None:
                raise ValueError("Upload land-cover rasters and define their class crosswalk.")
            years=[r.year for r in self.rasters]
            if len(set(years))!=len(years) or len({r.upload_id for r in self.rasters})!=len(self.rasters):
                raise ValueError("Use a different uploaded raster and year for every period.")
            if self.years is not None and set(years)!=set(self.years):
                raise ValueError("Selected years must match the uploaded raster periods.")
        elif self.rasters:
            raise ValueError("Select uploaded inputs to use these rasters.")
        if self.crosswalk:
            if len({r.source for r in self.crosswalk})!=len(self.crosswalk):
                raise ValueError("Each source class needs exactly one crosswalk row.")
            targets={}
            for r in self.crosswalk:
                identity=(r.name.strip(),r.color.lower())
                if r.code in targets and targets[r.code]!=identity:
                    raise ValueError("Merged classes must share the same target name and colour.")
                targets[r.code]=identity
            if len(targets)>64:
                raise ValueError("Use at most 64 target classes.")
            if self.forest_codes and not set(self.forest_codes)<=set(targets):
                raise ValueError("Forest selections must be target classes in the crosswalk.")
        if self.forest_codes and (len(set(self.forest_codes))!=len(self.forest_codes) or any(not 1<=c<=999 for c in self.forest_codes)):
            raise ValueError("Use distinct valid target codes for forest.")
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
            self.validate_land_periods()
            if self.land_cover.source == "default" and self.land_cover.resolution < 50:
                raise ValueError("The prepared Ganjam source grid is 50 m. Choose 50 or 100 m.")
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
                cap = 8_000_000 if self.land_cover.source == "uploaded" else 2_000_000
                area_cap = 20_000 if self.land_cover.source == "uploaded" else 2_000
                if enclosing > area_cap or enclosing * 1e6 / self.land_cover.resolution**2 > cap:
                    raise ValueError(f"Land-cover inputs allow an enclosing rectangle up to {area_cap:,} km² and {cap:,} analysis cells. Reduce the area or use a coarser grid.")
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
        self.validate_land_periods()
        return self

    def validate_land_periods(self):
        if not set(self.modules)&{"lulc","fragmentation"}:
            return
        land=self.land_cover
        available=[2002,2012,2022] if self.mode=="ganjam" else [2020,2021]
        years=[r.year for r in land.rasters] if land.source=="uploaded" else land.years or available
        if land.source=="default" and not set(years)<=set(available):
            raise ValueError("These years are not available from the selected public reference. Upload your own rasters for other periods.")
        if "lulc" in self.modules and len(years)<2:
            raise ValueError("Land-cover change needs at least two distinct periods.")
        if "fragmentation" in self.modules and land.crosswalk and not land.forest_codes:
            raise ValueError("Choose the target classes that count as forest.")
