from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pyproj import CRS, Transformer
from shapely.errors import ShapelyError
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform, unary_union
from shapely.validation import explain_validity

from nbs_gis.errors import PipelineError


@dataclass(frozen=True)
class AoiData:
    geometry: BaseGeometry
    crs: CRS
    feature_count: int
    path: Path


def load_aoi(path: Path, crs_value: str) -> AoiData:
    if not path.is_file():
        raise PipelineError(f"AOI file not found: {path}")
    try:
        payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PipelineError(f"Unable to read AOI GeoJSON: {path}: {error}") from error

    try:
        payload_type = payload.get("type")
        if payload_type == "FeatureCollection":
            features = payload.get("features")
            if not isinstance(features, list) or not features:
                raise PipelineError("AOI FeatureCollection is empty")
            geometries = []
            for index, item in enumerate(features, start=1):
                if not isinstance(item, dict):
                    raise PipelineError(f"AOI feature {index} is not a GeoJSON object")
                geometry_payload = item.get("geometry")
                if not geometry_payload:
                    raise PipelineError(f"AOI feature {index} has no geometry")
                geometries.append(shape(geometry_payload))
            feature_count = len(geometries)
        elif payload_type == "Feature":
            geometry_payload = payload.get("geometry")
            if not geometry_payload:
                raise PipelineError("AOI Feature has no geometry")
            geometries = [shape(geometry_payload)]
            feature_count = 1
        elif payload_type in {"Polygon", "MultiPolygon"}:
            geometries = [shape(payload)]
            feature_count = 1
        else:
            raise PipelineError(
                "AOI must be a GeoJSON FeatureCollection, Feature, Polygon or MultiPolygon"
            )

        unsupported = sorted({geom.geom_type for geom in geometries} - {"Polygon", "MultiPolygon"})
        if unsupported:
            raise PipelineError(
                f"AOI contains unsupported geometry types: {', '.join(unsupported)}"
            )
        geometry = unary_union(geometries)
    except PipelineError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError, ShapelyError) as error:
        raise PipelineError(f"AOI contains invalid GeoJSON geometry: {error}") from error

    if geometry.is_empty:
        raise PipelineError("AOI geometry is empty")
    if geometry.geom_type not in {"Polygon", "MultiPolygon"}:
        raise PipelineError(f"AOI union produced unsupported geometry: {geometry.geom_type}")
    if not geometry.is_valid:
        raise PipelineError(f"AOI geometry is invalid: {explain_validity(geometry)}")

    try:
        crs = CRS.from_user_input(crs_value)
    except Exception as error:  # pyproj raises several input-specific exception types
        raise PipelineError(f"Invalid AOI CRS {crs_value!r}: {error}") from error

    return AoiData(geometry=geometry, crs=crs, feature_count=feature_count, path=path)


def transform_geometry(geometry: BaseGeometry, source: CRS, target: CRS) -> BaseGeometry:
    if source == target:
        return geometry
    try:
        transformer = Transformer.from_crs(source, target, always_xy=True)
        transformed = transform(transformer.transform, geometry)
    except Exception as error:
        raise PipelineError(
            f"Unable to transform AOI from {source} to {target}: {error}"
        ) from error
    if transformed.is_empty or not transformed.is_valid:
        raise PipelineError("AOI became empty or invalid after coordinate transformation")
    return transformed
