"""Compact, masked period COGs and daily series, with strict missing-data rules."""
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

VARIABLES = ["e_24_mm", "t_24_mm", "et_24_mm", "aeti_24_mm", "int_mm", "et_ref_24_mm", "se_root", "npp"]
DISPLAY = [
    ("et_24_mm", "Evapotranspiration (E + T)", "mm", "water"),
    ("npp", "Net primary production", "gC m⁻²", "health"),
    ("se_root", "Root-zone relative saturation", "1", "water"),
    ("et_ref_24_mm", "Reference evapotranspiration", "mm", "water"),
]


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def export_results(model: Path, out: Path, request: dict, run: dict):
    import numpy as np
    import pandas as pd
    from pyproj import Geod
    import rasterio
    from rasterio.features import geometry_mask
    import rioxarray  # noqa: F401
    import xarray as xr

    out.mkdir(parents=True, exist_ok=True)
    checks = []

    def check(name, passed, detail):
        checks.append({"name": name, "passed": bool(passed), "detail": detail})
        if not passed:
            raise ValueError(f"Output validation failed: {name}")

    with xr.open_dataset(model / "et_look_out.nc", decode_coords="all") as source:
        d = source.load()
    d["et_24_mm"] = d.e_24_mm + d.t_24_mm
    d["et_24_mm"].attrs = {"units": "mm day-1", "long_name": "Evaporation plus transpiration, excluding interception"}
    d = d[VARIABLES].astype("float32")
    times = pd.DatetimeIndex(d.time_bins.values)
    expected = pd.date_range(request["start"], request["end"], freq="D")
    check("Daily dates match the submitted inclusive period", times.equals(expected), [str(t.date()) for t in times])
    check("Geographic north-up grid", d.rio.crs.to_epsg() == 4326 and np.all(np.diff(d.x) > 0) and np.all(np.diff(d.y) < 0), str(d.rio.crs))
    height, width = d.sizes["y"], d.sizes["x"]
    check("Pilot grid within memory limit", width * height <= 400_000, [height, width])
    w, s, e, n = request["bbox"]
    boundary = request.get("boundary") or {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {}, "geometry": {"type": "Polygon", "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]}}]}
    transform = d.rio.transform()
    included = geometry_mask([f["geometry"] for f in boundary["features"]], out_shape=(height, width), transform=transform, invert=True, all_touched=False)
    check("Selected area intersects the output", included.any(), int(included.sum()))
    mask = xr.DataArray(included, coords={"y": d.y, "x": d.x}, dims=("y", "x"))
    d = d.where(mask)
    geod = Geod(ellps="WGS84")
    dx, dy = transform.a, -transform.e
    row_areas = []
    for latitude in d.y.values:
        lat0, lat1 = float(latitude) - dy / 2, float(latitude) + dy / 2
        area, _ = geod.polygon_area_perimeter([0, dx, dx, 0], [lat0, lat0, lat1, lat1])
        row_areas.append(abs(area))
    areas = np.broadcast_to(np.array(row_areas)[:, None], included.shape) * included
    eligible = float(areas.sum())

    def stats(a):
        valid = np.isfinite(a) & included
        good_area = float(areas[valid].sum())
        return {"mean": float(np.sum(a[valid].astype("float64") * areas[valid]) / good_area) if good_area else None,
                "min": float(a[valid].min()) if good_area else None, "max": float(a[valid].max()) if good_area else None,
                "validAreaKm2": good_area / 1e6, "eligibleAreaKm2": eligible / 1e6, "missingAreaKm2": (eligible - good_area) / 1e6,
                "coveragePct": 100 * good_area / eligible, "cells": int(valid.sum()), "classes": []}

    for name in VARIABLES:
        a = d[name].values
        good = np.isfinite(a)
        check(f"{name}: usable finite values, no infinities", good.any() and not np.isinf(a).any(), float(good[:, included].mean()))
        check(f"{name}: nonnegative", np.nanmin(a) >= -1e-5, float(np.nanmin(a)))
    check("Saturation is bounded by one", float(d.se_root.max()) <= 1.00001, float(d.se_root.max()))
    residual = np.abs(d.aeti_24_mm.values - d.e_24_mm.values - d.t_24_mm.values - d.int_mm.values)
    check("AETI = E + T + interception", np.nanmax(residual) < 1e-4, float(np.nanmax(residual)))

    notes = ["ET is evaporation plus transpiration; AETI additionally includes interception.",
             "NPP is carbon production in gC m-2 per daily bin, not crop yield or dry biomass.",
             "Root-zone relative saturation is dimensionless (0–1), not volumetric soil moisture.",
             "Period water and NPP totals require all daily values at each pixel. Missing days remain NoData; saturation uses a complete-period mean.",
             "Area statistics use WGS84 geodesic pixel areas and a pixel-centre boundary mask. They include all land-cover types inside the selected boundary.",
             "Model-derived technical screening; no field validation or causal attribution to an NbS intervention."]
    scope = "FAO cached provider products, freshly processed through both preparation stages, SE_ROOT v3 and ETLook v3." if request["mode"] == "sample" else "Server acquisition from configured providers, followed by SE_ROOT v3 and ETLook v3."
    d.attrs.update(title=request["name"], model=f"pyWaPOR {run['version']} / v3", scope=scope, interpretation=" ".join(notes))
    d.to_netcdf(out / "daily-results.nc", encoding={v: {"zlib": True, "complevel": 4, "dtype": "float32", "_FillValue": -9999.} for v in VARIABLES})
    rows, series = [], []
    for i, timestamp in enumerate(times):
        row = {"date": str(timestamp.date())}
        for name in VARIABLES:
            st = stats(d[name].isel(time_bins=i).values)
            row[name], row[name + "_coverage_pct"] = st["mean"], st["coveragePct"]
        rows.append(row)
    with (out / "daily-summary.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    for name, title, _, _ in DISPLAY:
        unit = "1" if name == "se_root" else "gC m⁻² / daily bin" if name == "npp" else "mm/day"
        series.append({"id": name, "title": title, "unit": unit, "points": [{"date": row["date"], "value": row[name], "coveragePct": row[name + "_coverage_pct"]} for row in rows]})

    period_specs = [("whole", "Full selected period", np.ones(len(times), dtype=bool))]
    for month in sorted(set(times.strftime("%Y-%m"))):
        period_specs.append(("month-" + month, month + " · selected days", times.strftime("%Y-%m") == month))
    dekads = [f"{t:%Y-%m}-{min((t.day - 1) // 10 + 1, 3)}" for t in times]
    for dekad in sorted(set(dekads)):
        period_specs.append(("dekad-" + dekad, dekad[:7] + " · dekad " + dekad[-1] + " · selected days", np.array(dekads) == dekad))
    periods, layers, summary_rows = [], [], []
    grid = {"width": width, "height": height, "crs": 4326, "left": transform.c, "top": transform.f, "dx": dx, "dy": dy}
    for period_id, label, indices in period_specs:
        selected = times[indices]
        start, end = str(selected[0].date()), str(selected[-1].date())
        periods.append({"id": period_id, "label": label, "start": start, "end": end, "days": len(selected)})
        block = d.isel(time_bins=np.flatnonzero(indices))
        values = [block[v].mean("time_bins", skipna=False).values if v == "se_root" else block[v].sum("time_bins", skipna=False).values for v in VARIABLES]
        filename = period_id + ".tif"
        with rasterio.open(out / filename, "w", driver="COG", width=width, height=height, count=9, dtype="float32", crs="EPSG:4326", transform=transform, nodata=-9999., compress="DEFLATE", blocksize=256, overview_resampling="average") as dst:
            for b, (name, a) in enumerate(zip(VARIABLES, values), 1):
                dst.write(np.where(np.isfinite(a), a, -9999.).astype("float32"), b)
                dst.set_band_description(b, name)
                dst.update_tags(b, units="1" if name == "se_root" else "gC m-2" if name == "npp" else "mm")
            dst.write(areas.astype("float32"), 9)
            dst.set_band_description(9, "included_pixel_area_m2")
            dst.update_tags(start=start, end_inclusive=end, days=len(selected), pywapor_version=run["version"], aggregation="complete-period totals; mean saturation; pixel-centre AOI mask")
        with rasterio.open(out / filename) as src:
            check(filename + ": COG and area-band round trip", src.tags(ns="IMAGE_STRUCTURE").get("LAYOUT") == "COG" and np.array_equal(src.read(9), areas.astype("float32")), src.count)
            for b, a in enumerate(values, 1):
                np.testing.assert_allclose(src.read(b, masked=True).filled(np.nan), a.astype("float32"), equal_nan=True)
        for name, title, unit, palette in DISPLAY:
            band = VARIABLES.index(name) + 1
            st = stats(values[band - 1])
            layers.append({"id": period_id + "-" + name, "variable": name, "period": period_id, "file": filename, "band": band,
                           "title": title, "unit": unit, "palette": palette, "stats": st})
            summary_rows.append({"period": period_id, "start": start, "end_inclusive": end, "days": len(selected), "variable": name, "unit": unit, "mean": st["mean"], "coverage_pct": st["coveragePct"]})
    with (out / "period-summary.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary_rows[0])); writer.writeheader(); writer.writerows(summary_rows)
    (out / "boundary.geojson").write_text(json.dumps(boundary))
    (out / "validation.json").write_text(json.dumps({"status": "passed", "checks": checks}, indent=2))
    (out / "run-manifest.json").write_text(json.dumps({"request": request, "run": run, "scope": scope, "grid": grid, "notes": notes}, indent=2))
    shutil.copyfile(model / "configuration.json", out / "configuration.json")
    (out / "README.txt").write_text(f"{request['name']}\n{request['start']} to {request['end']} (inclusive)\n{scope}\n\n" + "\n".join(notes) + "\n\nGeoTIFF bands: " + ", ".join(VARIABLES + ["included_pixel_area_m2"]) + "\nDaily grids are in daily-results.nc.\n")
    # Do not zip private logs, credentials, provider caches or model scratch files.
    with zipfile.ZipFile(out / "results.zip", "w", zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
        for path in sorted(out.iterdir()):
            if path.name not in ("results.zip", "result.json"):
                archive.write(path, path.name)
    media = {".tif": "image/tiff", ".nc": "application/x-netcdf", ".csv": "text/csv", ".json": "application/json", ".geojson": "application/geo+json", ".zip": "application/zip", ".txt": "text/plain"}
    assets = [{"file": p.name, "bytes": p.stat().st_size, "sha256": sha256(p), "media_type": media[p.suffix]} for p in sorted(out.iterdir()) if p.name != "result.json"]
    result = {"schema": "nbs-water/v1", "name": request["name"], "model": f"pyWaPOR {run['version']} / v3", "prepared_at": datetime.now(timezone.utc).isoformat(),
              "scope": scope, "notes": notes, "grid": grid, "boundary": boundary, "periods": periods, "layers": layers, "series": series, "assets": assets,
              "validation": {"status": "passed", "checks": len(checks)}, "source_url": "https://storage.googleapis.com/fao-cog-data/pywapor_test_data/test_data.zip" if request["mode"] == "sample" else None}
    (out / "result.json").write_text(json.dumps(result, allow_nan=False))
