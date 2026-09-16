"""Reproducible numeric packages. No authentication tokens are written to metadata."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.features import rasterize
from shapely.geometry import box, mapping, shape
from shapely.ops import transform as transform_geometry
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "public/data/step2"
CACHE = ROOT / "engine/outputs/step2-source"
AOI_PATH = ROOT / "public/data/ganjam-aoi.geojson"
AOI = unary_union([shape(f["geometry"]) for f in json.loads(AOI_PATH.read_text())["features"]])
TO_AREA = Transformer.from_crs(4326, 6933, always_xy=True).transform
AOI_AREA = transform_geometry(TO_AREA, AOI)


def area_weights(transform, width, height, crs=4326):
    """Exact polygon intersections at boundary cells; square kilometres.

    Interiors use the equal-area width of the longitude strip, not cos(latitude)
    or a pixel-centre AOI mask. EPSG:6933 preserves the area of geographic boxes.
    """
    if int(crs) not in (4326, 6933):
        raise ValueError("Prepare inputs in EPSG:4326 or EPSG:6933")
    aoi = AOI if crs == 4326 else AOI_AREA
    weights = np.zeros((height, width), dtype="float32")
    inside = rasterize([(mapping(aoi), 1)], out_shape=weights.shape, transform=transform)
    boundary = rasterize(
        [(mapping(aoi.boundary), 1)], out_shape=weights.shape, transform=transform, all_touched=True
    )
    for row in range(height):
        cell = box(*sorted_box(transform, 0, row))
        if crs == 4326:
            cell = transform_geometry(TO_AREA, cell)
        weights[row, inside[row] == 1] = cell.area / 1e6
    for row, col in zip(*np.where(boundary)):
        cell = box(*sorted_box(transform, col, row))
        if crs == 4326:
            cell = transform_geometry(TO_AREA, cell)
        weights[row, col] = cell.intersection(AOI_AREA).area / 1e6
    return weights


def sorted_box(transform, col, row):
    x, y = transform * (col, row)
    xx, yy = transform * (col + 1, row + 1)
    return min(x, xx), min(y, yy), max(x, xx), max(y, yy)


def write_asset(
    asset_id,
    arrays,
    names,
    transform,
    source,
    native_resolution,
    processing,
    crs=4326,
    weights=None,
):
    OUT.mkdir(parents=True, exist_ok=True)
    data = np.stack(arrays).astype("float32")
    if data.ndim != 3 or len(names) != len(data):
        raise ValueError("Band names and equally shaped arrays are required")
    h, w = data.shape[1:]
    if weights is None:
        weights = area_weights(transform, w, h, crs)
    if not np.isfinite(weights).all() or (weights < 0).any():
        raise ValueError("Invalid area weights")
    data[:, weights == 0] = np.nan
    path = OUT / f"{asset_id}.tif"
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=w,
        height=h,
        count=len(data) + 1,
        dtype="float32",
        crs=f"EPSG:{crs}",
        transform=transform,
        nodata=np.nan,
        compress="deflate",
        predictor=3,
        tiled=True,
    ) as dst:
        dst.write(np.concatenate([data, weights[None]]))
        dst.descriptions = tuple([*names, "AOI intersection area (km2)"])
    grid = dict(
        width=w,
        height=h,
        crs=crs,
        left=transform.c,
        top=transform.f,
        dx=transform.a,
        dy=-transform.e,
    )
    asset = dict(
        id=asset_id,
        file=path.name,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        source=source,
        grid=grid,
        bands=[*names, "AOI area km2"],
        areaBand=len(data) + 1,
        nativeResolution=native_resolution,
        processing=processing,
    )
    reference = []
    for name, array in zip(names, data):
        valid = np.isfinite(array) & (weights > 0)
        area = float(weights[valid].astype("float64").sum())
        reference.append(
            dict(
                name=name,
                validAreaKm2=area,
                mean=float(np.sum(array[valid].astype("float64") * weights[valid]) / area)
                if area
                else None,
                min=float(array[valid].min()) if area else None,
                max=float(array[valid].max()) if area else None,
            )
        )
    return asset, reference


def update_catalog(asset, module, source, reference):
    path = OUT / "catalog.json"
    catalog = json.loads(path.read_text())
    for key, item in [("rasters", asset), ("modules", module), ("sources", source)]:
        catalog[key] = [v for v in catalog[key] if v["id"] != item["id"]] + [item]
    path.write_text(json.dumps(catalog, indent=2) + "\n")
    (OUT / f"{asset['id']}-reference.json").write_text(json.dumps(reference, indent=2) + "\n")


def identity(asset_id, band, title, unit, period, palette="sequential", **kwargs):
    return dict(
        id=f"{asset_id}-{band}",
        title=title,
        unit=unit,
        period=period,
        operation="identity",
        inputs=[dict(raster=asset_id, band=band)],
        palette=palette,
        interpretation=kwargs.pop(
            "interpretation", "Read alongside the documented scale, coverage and method."
        ),
        **kwargs,
    )
