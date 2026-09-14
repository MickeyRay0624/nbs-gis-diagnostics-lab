"""Forest fragmentation adapted from the SCALA ArcPy reference (September 2026).

Classify the whole valid landscape before stratification. Internal clearings
are NON-FOREST, not perforated forest. NoData holes are never counted as clearings.
Forest connectivity is eight-neighbour; clearing connectivity is four-neighbour.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.warp import transform_geom
from scipy import ndimage

from nbs_gis.errors import PipelineError

LABELS = {0: "Non-forest", 1: "Patch", 2: "Edge", 3: "Internal clearing", 4: "Core"}
STRATA = {1: "Protected", 2: "OECM", 3: "Unprotected"}


def classify_forest(
    data: np.ndarray,
    forest_codes: list[int],
    cell_m: float,
    edge_m: float = 50,
    nodata: int = 0,
    strata: np.ndarray | None = None,
    count_boundary: bool = False,
) -> tuple[np.ndarray, list[dict], dict]:
    """Return classes (255=NoData), metrics and QA; input must be a square metre grid.

    Area and TE are allocated by pixel. NP/MPS/MSI/AWMSI/MPE use whole patches
    assigned to the stratum with most pixels (ties: Protected, OECM, Unprotected).
    LPI uses the largest patch's actual intersection with the stratum.
    Without protection input only the All row is produced: no protection inferred.
    """
    if data.ndim != 2 or not data.size:
        raise PipelineError("Fragmentation needs a non-empty 2D raster")
    if not np.isfinite(cell_m) or cell_m <= 0:
        raise PipelineError("Cell size must be finite and positive")
    if not np.isfinite(edge_m) or edge_m < cell_m:
        raise PipelineError("Edge width must be finite and at least one analysis cell")
    if not forest_codes or nodata in forest_codes:
        raise PipelineError("Choose forest classes distinct from NoData")
    valid = data != nodata
    forest = np.isin(data, forest_codes) & valid
    if strata is not None and (
        strata.shape != data.shape or not np.isin(strata[valid], [1, 2, 3]).all()
    ):
        raise PipelineError("Protection strata must match the grid and use codes 1, 2, 3")
    # An invalid pixel is unknown, not an ecological edge. Explicit padding also
    # handles the all-forest case without SciPy's implicit exterior seed.
    seeds = valid & ~forest
    if count_boundary:
        seeds |= ~valid
    if seeds.any() or count_boundary:
        padded = np.pad(~seeds, 1, constant_values=not count_boundary)
        distance = ndimage.distance_transform_edt(padded, sampling=cell_m)[1:-1, 1:-1]
        core = forest & (distance > edge_m)
        del padded, distance
    else:
        core = forest.copy()
    labels, patch_count = ndimage.label(forest, structure=np.ones((3, 3)))
    has_core = np.zeros(patch_count + 1, dtype=bool)
    has_core[np.unique(labels[core])] = True
    has_core[0] = False
    patch = forest & ~has_core[labels]

    # Flood four-connected non-forest/unknown cells from the rectangular edge;
    # any component touching unknown data is excluded from internal clearings.
    bg_labels, bg_count = ndimage.label(~forest)
    exterior = np.zeros(bg_count + 1, dtype=bool)
    exterior[np.unique(np.concatenate((bg_labels[0], bg_labels[-1],
                                      bg_labels[:, 0], bg_labels[:, -1],
                                      bg_labels[~valid])))] = True
    exterior[0] = True
    holes = valid & ~forest & ~exterior[bg_labels]
    out = np.zeros(data.shape, dtype=np.uint8)
    out[holes] = 3
    out[forest & ~core] = 2
    out[core] = 4
    out[patch] = 1
    out[~valid] = 255

    areas = np.bincount(labels.ravel(), minlength=patch_count + 1).astype(float)
    areas[0] = 0
    # Actual ecological sides, never protected-area administrative lines.
    edge_ok = valid & ~forest if not count_boundary else ~forest
    padded = np.pad(edge_ok, 1, constant_values=count_boundary)
    sides = np.zeros(data.shape, dtype=np.uint8)
    h, w = data.shape
    for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        sides += forest & padded[1 + dy:1 + dy + h, 1 + dx:1 + dx + w]
    perims = np.bincount(labels.ravel(), weights=sides.ravel(),
                        minlength=patch_count + 1) * cell_m
    strata_ids = [1, 2, 3] if strata is not None else []
    portions = np.array([
        np.bincount(labels[(strata == s) & forest], minlength=patch_count + 1)
        for s in strata_ids
    ]) if strata_ids else None
    assignment = np.argmax(portions, axis=0) + 1 if portions is not None else None
    straddling = int(((portions[:, 1:] > 0).sum(axis=0) > 1).sum()) \
        if portions is not None else 0
    cell_ha = cell_m * cell_m / 10000
    rows = []
    for s in [0, *strata_ids]:
        mask = valid if s == 0 else valid & (strata == s)
        counts = np.bincount(out[mask], minlength=5)
        forest_n = int(counts[1] + counts[2] + counts[4])
        landscape_n = int(mask.sum())
        selected = np.arange(patch_count + 1) > 0
        if s:
            selected &= assignment == s
        npatch = int(selected.sum())
        a = areas[selected] * cell_m * cell_m
        p = perims[selected]
        shape = .25 * p / np.sqrt(a) if npatch else np.array([])
        largest_n = float(areas.max()) if not s else float(portions[s - 1].max())
        te_m = float(sides[mask].sum()) * cell_m
        hole_ids = np.unique(bg_labels[holes & mask])
        rows.append({
            "stratum": "All" if not s else STRATA[s],
            "landscape_ha": landscape_n * cell_ha,
            "forest_ha": forest_n * cell_ha,
            "PLAND": forest_n / landscape_n * 100 if landscape_n else 0,
            "patch_ha": int(counts[1]) * cell_ha,
            "edge_ha": int(counts[2]) * cell_ha,
            "core_ha": int(counts[4]) * cell_ha,
            "clearing_ha": int(counts[3]) * cell_ha,
            "core_pct": int(counts[4]) / forest_n * 100 if forest_n else 0,
            "NP": npatch, "TE_m": te_m,
            "ED": te_m / (landscape_n * cell_ha) if landscape_n else 0,
            "MPS_ha": float(a.mean()) / 10000 if npatch else 0,
            "MPE": float(p.mean()) if npatch else 0,
            "MSI": float(shape.mean()) if npatch else 0,
            "AWMSI": float((shape * a).sum() / a.sum()) if npatch else 0,
            "LPI": largest_n / landscape_n * 100 if landscape_n else 0,
            "largest_patch_ha": largest_n * cell_ha,
            "clearings_intersecting": len(hole_ids),
        })
    qa = {
        "forest_pixels": int(forest.sum()),
        "valid_pixels": int(valid.sum()),
        "class_conservation": int(np.isin(out, [1, 2, 4]).sum()) == int(forest.sum()),
        "straddling_patches": straddling,
        "connectivity": 8,
        "clearing_connectivity": 4,
        "edge_width_m": edge_m,
        "count_boundary_as_edge": count_boundary,
        "protection_available": strata is not None,
    }
    return out, rows, qa


def fragment_raster(
    source: Path, destination: Path, forest_codes: list[int], edge_m: float,
    strata: np.ndarray | None = None, count_boundary: bool = False,
) -> tuple[list[dict], dict]:
    with rasterio.open(source) as src:
        if (not src.crs or not src.crs.is_projected or src.crs.linear_units != "metre"
                or not np.isclose(src.res[0], src.res[1])
                or src.transform.b or src.transform.d):
            raise PipelineError("Fragmentation requires a north-up square grid in metres")
        data = src.read(1)
        out, rows, qa = classify_forest(
            data, forest_codes, src.res[0], edge_m, src.nodata,
            strata=strata, count_boundary=count_boundary,
        )
        profile = src.profile.copy()
    profile.update(dtype="uint8", nodata=255, compress="deflate")
    with rasterio.open(destination, "w", **profile) as dst:
        dst.write(out, 1)
        dst.write_colormap(1, {0: (239, 237, 226, 255), 1: (214, 66, 51, 255),
                              2: (230, 171, 54, 255), 3: (183, 82, 163, 255),
                              4: (40, 104, 69, 255), 255: (0, 0, 0, 0)})
    return rows, qa


def write_metrics(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def protection_grid(protected: Path | None, oecm: Path | None, grid) -> np.ndarray | None:
    """Read WGS84 polygon GeoJSON; Protected overrides OECM where they overlap."""
    if not protected and not oecm:
        return None
    shapes = []
    for path, code in ((oecm, 2), (protected, 1)):
        if path is None:
            continue
        doc = json.loads(path.read_text())
        if doc.get("type") != "FeatureCollection":
            raise PipelineError("Protection inputs must be WGS84 GeoJSON FeatureCollections")
        for feature in doc["features"]:
            geom = feature.get("geometry")
            if not geom or geom["type"] not in {"Polygon", "MultiPolygon"}:
                raise PipelineError("Protection inputs must contain polygons")
            shapes.append((transform_geom("EPSG:4326", grid.crs, geom), code))
    return rasterize(shapes, out_shape=(grid.height, grid.width), transform=grid.transform,
                     fill=3, dtype="uint8") if shapes else np.full(
                         (grid.height, grid.width), 3, dtype=np.uint8)
