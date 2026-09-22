"""Validated configuration, AOI weights, resumable caches and portable results."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import rasterio
import requests
from pyproj import Transformer
from rasterio.features import rasterize
from rasterio.transform import from_origin
from shapely.geometry import box, mapping, shape
from shapely.ops import transform as transform_geometry
from shapely.ops import unary_union

from .config import METRICS as METRICS
from .config import MODELS as MODELS
from .config import MODULES, validate_config
from .config import years as years

AREA_TRANSFORM = Transformer.from_crs(4326, 6933, always_xy=True).transform


class NoValidDataError(ValueError):
    """Source reads completed but no valid values intersect the eligible area."""


def sha(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()


def atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".part")
    temp.write_bytes(data)
    os.replace(temp, path)






def read_boundary(data):
    value = json.loads(data)
    features = value.get("features", []) if value.get("type") == "FeatureCollection" else [value]
    geometries = [shape(f["geometry"] if f.get("type") == "Feature" else f) for f in features]
    if not geometries or any(
        g.geom_type not in ["Polygon", "MultiPolygon"] or g.is_empty or not g.is_valid
        for g in geometries
    ):
        raise ValueError(
            "The boundary must contain valid WGS84 polygons without self-intersections."
        )
    aoi = unary_union(geometries)
    w, s, e, n = aoi.bounds
    if not (-180 <= w < e <= 180 and -85 <= s < n <= 85) or e - w > 180:
        raise ValueError(
            "Use a WGS84 boundary between 85°S and 85°N that does not cross the date line."
        )
    area = transform_geometry(AREA_TRANSFORM, aoi)
    if not 0 < area.area / 1e6 <= 50_000:
        raise ValueError(
            "Use a study area up to 50,000 km². Larger regions need separate packages."
        )
    return aoi, area


def grid_for(aoi, cell, crs=4326):
    geometry = aoi if crs == 4326 else transform_geometry(AREA_TRANSFORM, aoi)
    west, south, east, north = geometry.bounds
    left, top = math.floor(west / cell) * cell, math.ceil(north / cell) * cell
    width, height = math.ceil((east - left) / cell), math.ceil((top - south) / cell)
    if width * height > 8_000_000:
        raise ValueError(
            "This bounding box exceeds eight million analysis cells. Choose a smaller region."
        )
    return from_origin(left, top, cell, cell), (height, width)


def area_weights(aoi, area_aoi, transform, shape_, crs=4326):
    h, w = shape_
    geometry = aoi if crs == 4326 else area_aoi
    inside = rasterize([(mapping(geometry), 1)], out_shape=shape_, transform=transform)
    edges = rasterize(
        [(mapping(geometry.boundary), 1)], out_shape=shape_, transform=transform, all_touched=True
    )
    result = np.zeros(shape_, dtype="float32")

    def cell(row, col):
        x, y = transform * (col, row)
        xx, yy = transform * (col + 1, row + 1)
        p = box(x, yy, xx, y)
        return transform_geometry(AREA_TRANSFORM, p) if crs == 4326 else p

    for row in range(h):
        result[row, inside[row] == 1] = cell(row, 0).area / 1e6
    for row, col in zip(*np.where(edges), strict=True):
        result[row, col] = cell(row, col).intersection(area_aoi).area / 1e6
    return result


def finite_mean(values, fraction=0.9):
    valid = np.isfinite(values).sum(axis=0)
    return np.divide(
        np.nansum(values, axis=0, dtype="float64"),
        valid,
        out=np.full(valid.shape, np.nan),
        where=valid >= len(values) * fraction,
    ).astype("float32")


def statistics(values, weights):
    valid = np.isfinite(values) & (weights > 0)
    area = float(weights[valid].sum(dtype="float64"))
    eligible = float(weights.sum(dtype="float64"))
    return dict(
        mean=float(np.sum(values[valid].astype("float64") * weights[valid]) / area)
        if area
        else None,
        min=float(values[valid].min()) if area else None,
        max=float(values[valid].max()) if area else None,
        validAreaKm2=area,
        eligibleAreaKm2=eligible,
        missingAreaKm2=max(0, eligible - area),
        coveragePct=area / eligible * 100 if eligible else 0,
    )


def identity(asset, band, title, unit, period, **extras):
    return dict(
        id=f"{asset}-{band}",
        title=title,
        unit=unit,
        period=period,
        operation="identity",
        inputs=[dict(raster=asset, band=band)],
        palette=extras.pop("palette", "sequential"),
        interpretation=extras.pop(
            "interpretation",
            "Inspect source scale, valid coverage and method before interpretation.",
        ),
        **extras,
    )


def difference(asset, before, after, title, unit, period):
    return dict(
        id=f"{asset}-change-{before}-{after}",
        title=title,
        unit=unit,
        period=period,
        operation="difference",
        inputs=[dict(raster=asset, band=b) for b in [before, after]],
        palette="diverging",
        interpretation="Later minus earlier on the common valid footprint. Missing observations remain NoData.",
    )


def layer_values(layer, arrays):
    v = np.stack([arrays[b["band"] - 1] for b in layer["inputs"]])
    if layer["operation"] == "identity":
        return v[0].copy()
    if layer["operation"] == "difference":
        return (v[1] - v[0]).astype("float32")
    if layer["operation"] == "one-out-all-out":
        result = np.where(np.any(v == 1, axis=0), 1.0, 0.0).astype("float32")
        result[~np.isfinite(v).all(axis=0)] = np.nan
        result[np.any(v == -1, axis=0)] = -1
        return result
    raise ValueError("Unsupported local layer operation")


class Context:
    def __init__(self, folder, config=None):
        self.folder = Path(folder).resolve()
        self.config = validate_config(
            config or json.loads((self.folder / "config.json").read_text(encoding="utf-8"))
        )
        boundary = (self.folder / "aoi.geojson").read_bytes()
        if sha(boundary) != self.config["boundarySha256"]:
            raise ValueError("The boundary does not match this job. Download the package again.")
        self.aoi, self.area_aoi = read_boundary(boundary)
        self.job_hash = sha(json_bytes(self.config))
        self.cache = self.folder / "cache" / self.job_hash[:20]
        self.out = self.folder / "results" / "package"
        for path in [self.cache, self.out, self.folder / "results" / "rasters"]:
            path.mkdir(parents=True, exist_ok=True)
        atomic(self.out / "aoi.geojson", boundary)
        self.network_bytes = 0
        self.references = []
        self.failures = {}
        names = {"lulc": "Land-cover change", "fragmentation": "Forest fragmentation", **MODULES}
        self.catalog = dict(
            schema="nbs-step2/v1",
            version="local-" + self.job_hash[:12],
            preparedAt=datetime.now(UTC).isoformat(),
            studyArea=dict(
                name=self.config["name"],
                areaKm2=self.area_aoi.area / 1e6,
                boundary="aoi.geojson",
                sha256=sha(boundary),
            ),
            sources=[],
            rasters=[],
            modules=[
                dict(
                    id=i,
                    title=t,
                    question=f"What does {t.lower()} indicate in this study area?",
                    status="needs-data",
                    method=["Use a source-verified package for the supplied study area."],
                    limitations=["Technical screening requires expert and local review."],
                    fieldChecks=["Can local observations corroborate the mapped pattern?"],
                    sources=[],
                    layers=[],
                    missing=[
                        (
                            "Selected; preparation has not completed yet."
                            if i in self.config["modules"]
                            else "Not selected in this local preparation job."
                        )
                        if i in MODULES
                        else "Upload matching categorical land-cover rasters using the land-cover controls."
                    ],
                )
                for i, t in names.items()
            ],
            protection=dict(
                status="not-assessed",
                detail="Protection / OECM coverage and applicability have not been assessed. No absence is inferred.",
            ),
            review=dict(
                status="pending",
                detail="Prepared locally for technical screening. Expert acceptance and field verification remain pending.",
            ),
        )

    def log(self, message):
        print(message, flush=True)

    def cached_array(self, key, build):
        path = self.cache / (sha(key.encode()) + ".npz")
        if path.exists():
            try:
                with np.load(path, allow_pickle=False) as f:
                    return f["data"].copy()
            except (ValueError, OSError, EOFError):
                path.unlink()
        data = np.asarray(build(), dtype="float32")
        part = path.with_suffix(".part")
        with part.open("wb") as f:
            np.savez_compressed(f, data=data)
        os.replace(part, path)
        return data

    def download(self, url, key, params=None):
        path = self.cache / (sha(key.encode()) + ".download")
        meta = path.with_suffix(".json")
        if path.exists() and meta.exists():
            info = json.loads(meta.read_text(encoding="utf-8"))
            if path.stat().st_size == info["bytes"] and sha(path.read_bytes()) == info["sha256"]:
                return path
        error = None
        for attempt in range(3):
            try:
                with requests.get(url, params=params, stream=True, timeout=(20, 90)) as response:
                    response.raise_for_status()
                    part = path.with_suffix(".part")
                    hasher = hashlib.sha256()
                    with part.open("wb") as f:
                        for chunk in response.iter_content(1024 * 1024):
                            self.network_bytes += len(chunk)
                            if self.network_bytes > self.config["maxDownloadGB"] * 1e9:
                                raise ValueError(
                                    "This run reached the download limit. Start the same package again to continue from completed downloads. A single file larger than the limit needs a new package with a higher limit."
                                )
                            f.write(chunk)
                            hasher.update(chunk)
                    os.replace(part, path)
                    atomic(
                        meta, json_bytes(dict(bytes=path.stat().st_size, sha256=hasher.hexdigest()))
                    )
                    return path
            except (requests.RequestException, OSError) as exc:
                error = type(exc).__name__
                if attempt < 2:
                    time.sleep(attempt + 1)
        raise RuntimeError(
            f"Public data request failed ({error}). Check the connection and rerun; completed work will be reused."
        )

    def source(self, source):
        self.catalog["sources"] = [
            s for s in self.catalog["sources"] if s["id"] != source["id"]
        ] + [source]

    def write(
        self,
        module_id,
        arrays,
        names,
        transform,
        crs,
        weights,
        source,
        layers,
        method,
        limitations,
        series=None,
        extra_sources=None,
    ):
        arrays = np.asarray(arrays, dtype="float32")
        bands, h, w = arrays.shape
        if h * w > 8_000_000 or (bands + 1 + len(layers)) * h * w > 40_000_000:
            raise ValueError(
                "The output exceeds the browser memory limit. Choose a smaller study area or fewer outputs."
            )
        if not np.isfinite(weights).all() or (weights < 0).any():
            raise ValueError("Invalid eligible-area weights.")
        arrays[:, weights <= 0] = np.nan
        asset_id = layers[0]["inputs"][0]["raster"]
        path = self.out / f"{asset_id}.tif"
        profile = dict(
            driver="GTiff",
            width=w,
            height=h,
            count=bands + 1,
            dtype="float32",
            crs=f"EPSG:{crs}",
            transform=transform,
            nodata=np.nan,
            compress="deflate",
            predictor=3,
            tiled=True,
        )
        with rasterio.open(path, "w", **profile) as dst:
            dst.write(np.concatenate([arrays, weights[None]]))
            dst.descriptions = (*names, "Eligible AOI area (km2)")
        if path.stat().st_size > 100_000_000:
            raise ValueError("Prepared TIFF exceeds 100 MB; reduce the study area.")
        any_valid = False
        for layer in layers:
            values = layer_values(layer, arrays)
            if layer.get("categories"):
                valid = values[np.isfinite(values)]
                if not np.isin(valid, [c["value"] for c in layer["categories"]]).all():
                    raise ValueError(f"{layer['title']}: source contains unexpected classes.")
            stats = statistics(values, weights)
            any_valid |= stats["validAreaKm2"] > 0
            self.references.append(
                dict(
                    module=module_id,
                    layer=layer["title"],
                    unit=layer["unit"],
                    period=layer["period"],
                    **stats,
                )
            )
            result_path = self.folder / "results" / "rasters" / f"{layer['id']}.tif"
            with rasterio.open(result_path, "w", **{**profile, "count": 1}) as dst:
                dst.write(values, 1)
        if not any_valid:
            raise NoValidDataError(
                "No valid observations intersect the eligible study area. Missing data has not been converted to zero."
            )
        self.source(source)
        for extra_source in extra_sources or []:
            self.source(extra_source)
        self.catalog["rasters"].append(
            dict(
                id=asset_id,
                file=path.name,
                sha256=sha(path.read_bytes()),
                source=source["id"],
                grid=dict(
                    width=w,
                    height=h,
                    crs=crs,
                    left=transform.c,
                    top=transform.f,
                    dx=transform.a,
                    dy=-transform.e,
                ),
                bands=[*names, "Eligible AOI area (km2)"],
                areaBand=bands + 1,
                nativeResolution=source["resolution"],
                processing=method,
            )
        )
        module = next(m for m in self.catalog["modules"] if m["id"] == module_id)
        module.update(
            status="available",
            sources=[source["id"], *[s["id"] for s in extra_sources or []]],
            layers=layers,
            method=method,
            limitations=limitations,
            missing=[],
            **({"series": series} if series else {}),
        )
        self.log(f"Completed {MODULES[module_id]}: {len(layers)} layers.")

    def finish(self):
        available = [m["id"] for m in self.catalog["modules"] if m["status"] == "available"]
        for m in self.catalog["modules"]:
            if m["id"] in self.failures:
                m["missing"] = [self.failures[m["id"]]]
        atomic(self.out / "catalog.json", json_bytes(self.catalog))
        rows = [r for r in self.references if r["module"] in available]
        if rows:
            with (self.folder / "results" / "statistics.csv").open(
                "w", newline="", encoding="utf-8"
            ) as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(
                    {
                        k: (
                            "'" + v
                            if isinstance(v, str) and v.lstrip().startswith(("=", "+", "-", "@"))
                            else v
                        )
                        for k, v in row.items()
                    }
                    for row in rows
                )
        evidence = dict(
            schema="nbs-local-validation/v1",
            jobSha256=self.job_hash,
            complete=not self.failures and set(available) == set(self.config["modules"]),
            selected=self.config["modules"],
            available=available,
            failures=self.failures,
            statistics=rows,
            interpretation="Integrity and arithmetic checks are not field validation or expert acceptance.",
        )
        atomic(self.folder / "results" / "validation.json", json_bytes(evidence))
        atomic(
            self.folder / "results" / "run-manifest.json",
            json_bytes(dict(config=self.config, catalog=self.catalog)),
        )
        lines = [
            f"# {self.config['name']} — local preparation",
            "",
            f"Prepared modules: {len(available)} / {len(self.config['modules'])}.",
            "Expert review remains pending.",
            "",
            "## Import into the website",
            "Load results.zip in the same website version that generated this Python package.",
            "The archive contains the boundary, numeric inputs and provenance. It does not contain credentials or raw downloads.",
            "",
            "## Module status",
        ]
        lines.extend(
            f"- {MODULES[m]}: {'ready' if m in available else self.failures.get(m, 'not prepared')}"
            for m in self.config["modules"]
        )
        lines.extend(
            [
                "",
                "## Local files",
                "- results.zip: website import package",
                "- results/rasters: calculated numeric result layers",
                "- results/statistics.csv: area-weighted statistics",
                "- cache: reusable source extracts; remove to reclaim disk space",
                "",
                "## Sources",
            ]
        )
        lines.extend(
            f"- {s['name']}; {s['version']}; {s['licence']}; {s['url']}"
            for s in self.catalog["sources"]
        )
        atomic(self.folder / "results" / "README.md", "\n".join(lines).encode())
        part = self.folder / "results.zip.part"
        with zipfile.ZipFile(part, "w", zipfile.ZIP_DEFLATED) as z:
            # Include only catalog-referenced data: stale files cannot leak from an earlier run.
            for name in [
                "catalog.json",
                "aoi.geojson",
                *[r["file"] for r in self.catalog["rasters"]],
            ]:
                z.write(self.out / name, name)
        os.replace(part, self.folder / "results.zip")
        self.log(f"Results saved in: {self.folder / 'results'}")
        self.log(f"Import this file into the website: {self.folder / 'results.zip'}")
        return available
