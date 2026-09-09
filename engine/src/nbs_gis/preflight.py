from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from shapely.geometry import box

from nbs_gis.aoi import AoiData, load_aoi, transform_geometry
from nbs_gis.config import RunConfig
from nbs_gis.crosswalk import load_crosswalk
from nbs_gis.errors import NbsGisError
from nbs_gis.grid import build_grid, is_likely_equal_area, parse_target_crs


def _check(
    checks: list[dict[str, Any]],
    check_id: str,
    status: str,
    message: str,
    **details: Any,
) -> None:
    item: dict[str, Any] = {"id": check_id, "status": status, "message": message}
    if details:
        item["details"] = details
    checks.append(item)


def _path_check(checks: list[dict[str, Any]], check_id: str, path: Path, label: str) -> bool:
    if path.is_file():
        _check(checks, check_id, "pass", f"{label} found", path=str(path))
        return True
    _check(checks, check_id, "error", f"{label} not found", path=str(path))
    return False


def run_preflight(config: RunConfig) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    aoi: AoiData | None = None

    if _path_check(checks, "aoi-file", config.project.aoi_path, "AOI GeoJSON"):
        try:
            aoi = load_aoi(config.project.aoi_path, config.project.aoi_crs)
            _check(
                checks,
                "aoi-geometry",
                "pass",
                "AOI polygon geometry is valid",
                geometry_type=aoi.geometry.geom_type,
                feature_count=aoi.feature_count,
                source_crs=aoi.crs.to_string(),
            )
        except NbsGisError as error:
            _check(checks, "aoi-geometry", "error", str(error))

    target_crs = None
    try:
        target_crs = parse_target_crs(config.analysis.target_crs)
        _check(
            checks,
            "target-crs",
            "pass",
            "Target CRS is projected and uses metres",
            crs=target_crs.to_string(),
        )
        if is_likely_equal_area(target_crs):
            _check(
                checks,
                "area-crs",
                "pass",
                "Target CRS is identified as equal-area",
                crs=target_crs.to_string(),
            )
        else:
            _check(
                checks,
                "area-crs",
                "warning",
                "Target CRS is not identified as equal-area; GIS review is required before "
                "releasing area statistics",
                crs=target_crs.to_string(),
            )
    except NbsGisError as error:
        _check(checks, "target-crs", "error", str(error))

    if target_crs is not None and aoi:
        try:
            target_aoi = transform_geometry(aoi.geometry, aoi.crs, target_crs)
            grid = build_grid(
                target_aoi,
                target_crs,
                config.analysis.target_resolution,
                config.analysis.max_output_pixels,
            )
            _check(
                checks,
                "target-grid",
                "pass",
                "Target raster grid is within the configured safety limit",
                width=grid.width,
                height=grid.height,
                pixels=grid.pixel_count,
                resolution=grid.resolution,
                bounds=list(grid.bounds),
            )
        except NbsGisError as error:
            _check(checks, "target-grid", "error", str(error))

    if _path_check(checks, "crosswalk-file", config.analysis.crosswalk_path, "Class crosswalk"):
        try:
            crosswalk = load_crosswalk(
                config.analysis.crosswalk_path, config.analysis.output_nodata
            )
            _check(
                checks,
                "crosswalk-schema",
                "pass",
                "Class crosswalk is structurally valid",
                source_classes=len(crosswalk.source_to_target),
                target_classes=len(crosswalk.target_classes),
            )
        except NbsGisError as error:
            _check(checks, "crosswalk-schema", "error", str(error))

    raster_metadata: dict[str, Any] = {}
    for year, path in config.analysis.rasters.items():
        if not _path_check(checks, f"raster-{year}-file", path, f"LULC raster {year}"):
            continue
        try:
            with rasterio.open(path) as source:
                if source.count != 1:
                    raise ValueError(f"expected one band, found {source.count}")
                if source.crs is None:
                    raise ValueError("CRS is missing")
                if not np.issubdtype(np.dtype(source.dtypes[0]), np.integer):
                    raise ValueError(
                        f"categorical raster must use an integer dtype, found {source.dtypes[0]}"
                    )
                intersects = True
                if aoi:
                    source_aoi = transform_geometry(aoi.geometry, aoi.crs, source.crs)
                    overlap = source_aoi.intersection(box(*source.bounds))
                    intersects = not overlap.is_empty and overlap.area > 0
                    if not intersects:
                        raise ValueError("raster extent does not intersect the AOI")
                metadata = {
                    "path": str(path),
                    "crs": source.crs.to_string(),
                    "width": source.width,
                    "height": source.height,
                    "dtype": source.dtypes[0],
                    "nodata": source.nodata,
                    "bounds": list(source.bounds),
                    "intersects_aoi": intersects,
                }
                raster_metadata[str(year)] = metadata
                _check(
                    checks,
                    f"raster-{year}-metadata",
                    "pass",
                    f"LULC raster {year} is a readable categorical raster",
                    **metadata,
                )
        except (OSError, ValueError, rasterio.errors.RasterioError, NbsGisError) as error:
            _check(
                checks,
                f"raster-{year}-metadata",
                "error",
                f"LULC raster {year} is not usable: {error}",
                path=str(path),
            )

    if len(config.analysis.rasters) >= 2:
        _check(
            checks,
            "period-count",
            "pass",
            "At least two analysis years are configured",
            years=sorted(config.analysis.rasters),
            transitions=[list(pair) for pair in config.analysis.transitions],
        )

    errors = [item for item in checks if item["status"] == "error"]
    warnings = [item for item in checks if item["status"] == "warning"]
    status = "ready" if not errors else "blocked"
    return {
        "schema": "nbs-gis-preflight/v0.1",
        "status": status,
        "project": config.project.name,
        "config": str(config.source_path),
        "summary": {
            "checks": len(checks),
            "passed": sum(item["status"] == "pass" for item in checks),
            "warnings": len(warnings),
            "errors": len(errors),
        },
        "checks": checks,
        "raster_metadata": raster_metadata,
    }
