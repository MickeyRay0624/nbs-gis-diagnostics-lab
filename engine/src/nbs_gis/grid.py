from __future__ import annotations

import math
from dataclasses import dataclass

from pyproj import CRS
from rasterio.transform import Affine, from_origin
from shapely.geometry.base import BaseGeometry

from nbs_gis.errors import PipelineError

EQUAL_AREA_METHOD_MARKERS = (
    "equal area",
    "mollweide",
    "sinusoidal",
    "eckert iv",
    "eckert vi",
    "equal earth",
)


@dataclass(frozen=True)
class GridSpec:
    crs: CRS
    transform: Affine
    width: int
    height: int
    resolution: float
    bounds: tuple[float, float, float, float]

    @property
    def pixel_count(self) -> int:
        return self.width * self.height

    @property
    def pixel_area_ha(self) -> float:
        return abs(self.transform.a * self.transform.e) / 10_000


def parse_target_crs(value: str) -> CRS:
    try:
        crs = CRS.from_user_input(value)
    except Exception as error:
        raise PipelineError(f"Invalid target CRS {value!r}: {error}") from error
    if not crs.is_projected:
        raise PipelineError("Target CRS must be projected so area statistics use linear units")
    axes = crs.axis_info
    if axes and any(abs((axis.unit_conversion_factor or 1) - 1) > 1e-9 for axis in axes[:2]):
        raise PipelineError("Target CRS axes must use metres")
    return crs


def is_likely_equal_area(crs: CRS) -> bool:
    """Return whether PROJ identifies the CRS as using an equal-area method.

    PROJ does not expose a single equal-area flag. This deliberately conservative
    check covers common method names; an unrecognised CRS is reported for expert
    review instead of being silently treated as area-preserving.
    """
    operation = crs.coordinate_operation
    description = " ".join(
        part
        for part in (
            getattr(operation, "name", None),
            getattr(operation, "method_name", None),
        )
        if part
    ).lower()
    return any(marker in description for marker in EQUAL_AREA_METHOD_MARKERS)


def build_grid(
    aoi_geometry: BaseGeometry,
    target_crs: CRS,
    resolution: float,
    max_output_pixels: int,
) -> GridSpec:
    min_x, min_y, max_x, max_y = aoi_geometry.bounds
    left = math.floor(min_x / resolution) * resolution
    bottom = math.floor(min_y / resolution) * resolution
    right = math.ceil(max_x / resolution) * resolution
    top = math.ceil(max_y / resolution) * resolution
    width = max(1, int(round((right - left) / resolution)))
    height = max(1, int(round((top - bottom) / resolution)))
    pixel_count = width * height
    if pixel_count > max_output_pixels:
        raise PipelineError(
            f"Target grid would contain {pixel_count:,} pixels, above the configured "
            f"limit of {max_output_pixels:,}"
        )
    return GridSpec(
        crs=target_crs,
        transform=from_origin(left, top, resolution, resolution),
        width=width,
        height=height,
        resolution=resolution,
        bounds=(left, bottom, right, top),
    )
