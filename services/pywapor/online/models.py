from datetime import date
import json
import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from shapely.geometry import shape
from shapely.ops import unary_union

SAMPLE_BBOX = [31.0, 28.9, 31.2, 29.1]


def rectangle(bbox):
    w, s, e, n = bbox
    return {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {}, "geometry": {
        "type": "Polygon", "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]],
    }}]}


def bounds_area(bbox):
    w, s, e, n = bbox
    return 6371.0088**2 * math.radians(e - w) * (math.sin(math.radians(n)) - math.sin(math.radians(s)))


class JobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    mode: Literal["sample", "custom"] = "sample"
    name: str = Field(default="Fayoum public sample, Egypt", min_length=1, max_length=80)
    start: date = date(2021, 7, 1)
    end: date = date(2021, 7, 31)
    bbox: list[float] = Field(default_factory=lambda: SAMPLE_BBOX.copy(), min_length=4, max_length=4)
    boundary: dict | None = None

    @model_validator(mode="after")
    def geography_and_dates(self):
        self.name = self.name.strip()
        if not self.name or any(ord(c) < 32 for c in self.name):
            raise ValueError("Enter a study-area name without control characters.")
        w, s, e, n = self.bbox
        if not (-180 <= w < e <= 180 and -50 <= s < n <= 50 and e - w <= 180):
            raise ValueError("Use WGS84 bounds, west < east, south < north, within CHIRPS coverage (50°S–50°N), without crossing the date line.")
        if self.start > self.end or self.start < date(2018, 1, 1) or self.end >= date.today():
            raise ValueError("Choose completed dates from 2018 onwards, with the end on or after the start.")
        if self.mode == "sample":
            if self.bbox != SAMPLE_BBOX or self.start != date(2021, 7, 1) or self.end != date(2021, 7, 31) or self.boundary is not None:
                raise ValueError("The public sample is fixed to Fayoum, 1–31 July 2021. Choose custom to change the region or dates.")
        if self.boundary is not None:
            if len(json.dumps(self.boundary)) > 200_000:
                raise ValueError("Simplify the boundary to less than 200 KB.")
            if self.boundary.get("type") != "FeatureCollection" or not 1 <= len(self.boundary.get("features", [])) <= 100:
                raise ValueError("Provide a GeoJSON FeatureCollection with 1–100 polygon features.")
            geometries = []
            for feature in self.boundary["features"]:
                geometry = feature.get("geometry", {})
                if geometry.get("type") not in ("Polygon", "MultiPolygon"):
                    raise ValueError("Only Polygon and MultiPolygon boundaries are supported.")
                try:
                    g = shape(geometry)
                except Exception as exc:
                    raise ValueError("The boundary coordinates are invalid.") from exc
                if g.is_empty or not g.is_valid or g.has_z:
                    raise ValueError("Use valid, nonempty 2D polygons without self-intersections.")
                geometries.append(g)
            gb = unary_union(geometries).bounds
            if any(abs(a - b) > 1e-6 for a, b in zip(gb, self.bbox)):
                raise ValueError("The bounding box must match the polygon extent.")
        return self

    def validate_limits(self, settings):
        if (self.end - self.start).days + 1 > settings.max_days:
            raise ValueError(f"The pilot supports at most {settings.max_days} days per job.")
        if bounds_area(self.bbox) > settings.max_area_km2:
            raise ValueError(f"Choose a smaller area: the enclosing rectangle must be at most {settings.max_area_km2:g} km².")
        return self
