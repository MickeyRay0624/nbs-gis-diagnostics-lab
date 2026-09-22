"""Five local diagnostic preparations; no platform server or Earth Engine calls."""

from __future__ import annotations

import base64
import calendar
import json
import warnings
from collections import defaultdict
from datetime import date, timedelta

import numpy as np
import requests
from rasterio.warp import Resampling, reproject
from scipy.stats import theilslopes
from shapely.geometry import shape as geometry

from .core import area_weights, difference, finite_mean, grid_for, identity, statistics
from .gldas import GldasReader, read_daily
from .sources import (
    DEGRADATION,
    FLOOD,
    check_modis_budget,
    climate_daily,
    crop_cog,
    download_granule,
    granule_date,
    granules,
    mask_weights,
    modis_array,
)

CLASSES = [
    dict(value=-1, label="Degraded", color="#ba583e"),
    dict(value=0, label="Stable", color="#e1d79f"),
    dict(value=1, label="Improving", color="#3d8562"),
]


def align(values, source_transform, target_transform, target_shape, crs=4326):
    out = np.full(target_shape, np.nan, dtype="float32")
    reproject(
        values,
        out,
        src_transform=source_transform,
        src_crs=crs,
        dst_transform=target_transform,
        dst_crs=crs,
        src_nodata=np.nan,
        dst_nodata=np.nan,
        resampling=Resampling.nearest,
    )
    return out


def flood(ctx):
    path = ctx.download(FLOOD + "tile_extents.geojson", "jrc-tile-index-v2.1.2")
    tiles = [
        f"ID{f['properties']['id']}_{f['properties']['name']}"
        for f in json.loads(path.read_bytes())["features"]
        if geometry(f["geometry"]).intersection(ctx.aoi).area > 0
    ]
    if not tiles:
        raise ValueError("No JRC river-flood tiles cover this region.")
    transform, shape = grid_for(ctx.aoi, 1 / 1200)
    periods = ctx.config["flood"]["returnPeriods"]
    if (2 * (len(periods) + 2) + 1) * np.prod(shape) > 40_000_000:
        raise ValueError(
            "Flood output exceeds the browser memory budget. Choose fewer return periods or a smaller area."
        )
    water, flag = np.full(shape, np.nan), np.full(shape, np.nan)
    depths = [np.full(shape, np.nan, dtype="float32") for _ in periods]
    for tile in tiles:
        ctx.log(f"Flood tile: {tile}")
        w = crop_cog(
            ctx, f"{FLOOD}Permanent_WaterBodies/{tile}_permanent_water.tif", [1], transform, shape
        )[0]
        f = crop_cog(
            ctx, f"{FLOOD}Spurious_Depths/{tile}_spurious_depth_areas.tif", [1], transform, shape
        )[0]
        # Provider flag rasters can encode unflagged land as NoData. Only positive cells exclude depth.
        water = np.fmax(water, np.where(np.isfinite(w), (w > 0).astype("float32"), np.nan))
        flag = np.fmax(flag, np.where(np.isfinite(f), (f > 0).astype("float32"), np.nan))
        for i, rp in enumerate(periods):
            d = crop_cog(ctx, f"{FLOOD}RP{rp}/{tile}_RP{rp}_depth.tif", [1], transform, shape)[0]
            depths[i] = np.fmax(depths[i], d)
    for d in depths:
        d[(d <= 0) | (water > 0) | (flag > 0)] = np.nan
    names = [f"River flood depth · RP{rp}" for rp in periods] + [
        "Permanent water flag",
        "Spurious depth flag",
    ]
    arrays = depths + [water, flag]
    layers = [
        identity(
            "flood",
            i + 1,
            n,
            "m",
            "JRC v2.1.2 · static hazard",
            palette="water",
            domain=[0, 5],
            thresholds=[
                dict(label="0–<1 m", min=0, max=1),
                dict(label="1–<3 m", min=1, max=3),
                dict(label="3–<10 m", min=3, max=10),
                dict(label="10 m or deeper", min=10),
            ],
            interpretation="Positive modelled river inundation only. Missing areas are not evidence of zero risk. Return period is not a forecast date.",
        )
        for i, n in enumerate(names[: len(periods)])
    ]
    for i in range(len(periods), len(arrays)):
        layers.append(
            identity(
                "flood",
                i + 1,
                names[i],
                "class",
                "Quality exclusions",
                categories=[
                    dict(value=0, label="Not flagged", color="#e5e8dd"),
                    dict(value=1, label="Flagged", color="#b94e39"),
                ],
                interpretation="Provider quality flag; missing flags remain unknown. Positive flags exclude mapped depths.",
            )
        )
    source = dict(
        id="jrc-flood",
        name="JRC / CEMS-GloFAS global river flood hazard",
        url=FLOOD + "README.txt",
        version="2.1.2 · 2026-01-12",
        licence="Free and open Copernicus product; attribution required",
        description="Official depth and exclusion-flag tiles selected by intersection with the uploaded AOI: "
        + ", ".join(tiles),
        resolution="3 arc seconds (approximately 90 m)",
    )
    ctx.write(
        "flood",
        arrays,
        names,
        transform,
        4326,
        area_weights(ctx.aoi, ctx.area_aoi, transform, shape),
        source,
        layers,
        [
            "HTTP range reads of official tiles; nearest-neighbour native-grid alignment. Positive depths only, excluding permanent water and spurious-depth flags.",
            "Statistics use fractional AOI area. Depth means and distributions refer to mapped valid inundation; coverage retains the entire AOI denominator.",
        ],
        [
            "Riverine hazard only; not coastal flooding, flash flooding, exposure, damage or a forecast.",
            "Raw NoData does not distinguish dry cells from unmodelled areas. Source scales cannot support property-level decisions.",
        ],
    )


def productivity_classes(values):
    if not np.isin(values[np.isfinite(values)], [1, 2, 3, 4, 5]).all():
        raise ValueError("Unexpected published productivity class.")
    result = np.where(values <= 2, -1, np.where(values <= 4, 0, 1)).astype("float32")
    result[~np.isfinite(values)] = np.nan
    return result


def carbon_classes(values):
    if np.any(values[np.isfinite(values)] < -100):
        raise ValueError("Invalid carbon percentage in source.")
    result = np.where(values < -10, -1, np.where(values > 10, 1, 0)).astype("float32")
    result[~np.isfinite(values) | (abs(values) == 10)] = np.nan
    return result


def degradation(ctx):
    header = requests.head(DEGRADATION, timeout=60)
    header.raise_for_status()
    expected = base64.b64encode(bytes.fromhex("fc5d7b747a533b8bfbd542ee86688711")).decode()
    if "md5=" + expected not in header.headers.get("x-goog-hash", ""):
        raise ValueError("The Trends.Earth source changed; a version review is needed.")
    # Retain the source grid; the global COG uses this exact angular step.
    import rasterio

    with (
        rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_HTTP_TIMEOUT="90"),
        rasterio.open("/vsicurl/" + DEGRADATION) as src,
    ):
        if src.count != 14 or src.crs.to_epsg() != 4326:
            raise ValueError("Unexpected Trends.Earth source layout.")
        t = src.transform
        from rasterio.windows import Window, from_bounds

        raw_window = from_bounds(*ctx.aoi.bounds, t)
        import math

        window = Window(
            math.floor(raw_window.col_off),
            math.floor(raw_window.row_off),
            math.ceil(raw_window.width) + 1,
            math.ceil(raw_window.height) + 1,
        )
        transform = src.window_transform(window)
        shape = (int(window.height), int(window.width))
    if np.prod(shape) * 30 > 40_000_000:
        raise ValueError("Land-degradation output is too large. Use a smaller region.")
    data = crop_cog(ctx, DEGRADATION, list(range(1, 15)), transform, shape)
    weights, sources, mask_method = mask_weights(ctx, transform, shape, 4326)
    arrays, names, layers = [], [], []
    for suffix, p, land, c, r, period in [
        ("baseline", 1, 2, 3, 0, "2000–2015; productivity 2001–2015"),
        (
            "monitoring",
            10,
            11,
            12,
            9,
            "2023 assessment; productivity 2008–2023; land cover / SOC 2015–2022",
        ),
    ]:
        first = len(arrays) + 1
        components = [productivity_classes(data[p]), data[land], carbon_classes(data[c])]
        if (
            not np.isin(data[land][np.isfinite(data[land])], [-1, 0, 1]).all()
            or not np.isin(data[r][np.isfinite(data[r])], [-1, 0, 1]).all()
        ):
            raise ValueError("Unexpected published land-condition code.")
        labels = [
            f"Productivity · {suffix}",
            f"Land-cover component · {suffix}",
            f"Soil-carbon component · {suffix}",
            f"SOC change · {suffix}",
            f"Published indicator · {suffix}",
            f"Complete component coverage · {suffix}",
        ]
        arrays.extend(
            [
                *components,
                data[c],
                data[r],
                np.isfinite(np.stack(components)).all(0).astype("float32"),
            ]
        )
        names.extend(labels)
        layers.append(
            dict(
                id=f"degradation-combined-{suffix}",
                title=f"Combined land condition · {suffix}",
                unit="class",
                period=period,
                operation="one-out-all-out",
                inputs=[dict(raster="degradation", band=first + i) for i in range(3)],
                palette="health",
                categories=CLASSES,
                interpretation="One degraded component flags degradation even if another is missing. Stable or improving requires all three components. Technical screening, not an official SDG submission.",
            )
        )
        for i in range(3):
            layers.append(
                identity(
                    "degradation",
                    first + i,
                    labels[i],
                    "class",
                    period,
                    categories=CLASSES,
                    palette="health",
                )
            )
        layers.append(
            identity(
                "degradation",
                first + 3,
                labels[3],
                "%",
                period,
                palette="diverging",
                interpretation="Published modelled SOC change to 30 cm, not measured soil sampling. Integer ±10% values are unknown in the classified component because of rounding.",
            )
        )
        layers.append(
            identity(
                "degradation",
                first + 4,
                labels[4],
                "class",
                period,
                categories=CLASSES,
                palette="health",
                interpretation="Publisher's combined indicator for comparison with local one-out-all-out results.",
            )
        )
        layers.append(
            identity(
                "degradation",
                first + 5,
                labels[5],
                "class",
                period,
                categories=[
                    dict(value=0, label="Incomplete", color="#aaa69a"),
                    dict(value=1, label="Complete", color="#3d8562"),
                ],
            )
        )
    source = dict(
        id="trendsearth",
        name="Trends.Earth published SDG 15.3.1 components",
        url="https://doi.org/10.5281/zenodo.17514520",
        version="1.2 · 2000–2023 reporting file",
        licence="CC BY 4.0",
        description="Provider productivity, land-cover and modelled SOC components. Public object MD5 fc5d7b747a533b8bfbd542ee86688711.",
        resolution="Approximately 250 m; source grid retained",
    )
    ctx.write(
        "degradation",
        arrays,
        names,
        transform,
        4326,
        weights,
        source,
        layers,
        [
            "Read the published native component grids. Productivity classes 1/2 → degraded, 3/4 → stable, 5 → improving. SOC below −10% → degraded; above +10% → improving; between → stable; exactly ±10% → unknown because source values are rounded.",
            "Combine with the one-out-all-out rule. Unknowns remain visible in coverage.",
            mask_method,
        ],
        [
            "This reproduces a screening combination of published components, not the upstream productivity and SOC modelling.",
            "Provider documentation uses 2015–2022 for land cover / SOC in the 2023 assessment; TIFF labels may say 2015–2023. Preserve that discrepancy in interpretation.",
            "Degradation causes and intervention suitability require local review.",
        ],
        extra_sources=sources,
    )


def daily_index(values, metric, thresholds):
    complete = np.isfinite(values).all(axis=0)
    if metric in ["hot", "warm", "frost", "rain"]:
        test = (
            values < 0
            if metric == "frost"
            else values > thresholds[metric]
            if metric in ["hot", "warm"]
            else values >= thresholds["rain"]
        )
        out = test.sum(0).astype("float32")
    elif metric == "temperature":
        out = values.mean(0).astype("float32")
    elif metric == "dry":
        streak = np.zeros(values.shape[1:], dtype="int32")
        out = streak.copy()
        for day in values:
            streak = np.where(day < thresholds["dry"], streak + 1, 0)
            out = np.maximum(out, streak)
        out = out.astype("float32")
    else:
        raise ValueError("Unknown climate metric")
    out[~complete] = np.nan
    return out


def climate(ctx):
    conf = ctx.config["climate"]
    transform, shape = grid_for(ctx.aoi, 0.25)
    weights = area_weights(ctx.aoi, ctx.area_aoi, transform, shape)
    labels = {
        "hot": f"Hot days (Tmax > {conf['thresholds']['hot']} °C)",
        "warm": f"Warm nights (Tmin > {conf['thresholds']['warm']} °C)",
        "frost": "Frost days (Tmin < 0 °C)",
        "temperature": "Mean daily temperature",
        "rain": f"Heavy-rain days (≥ {conf['thresholds']['rain']} mm/day)",
        "dry": f"Longest dry spell (< {conf['thresholds']['dry']} mm/day)",
    }
    variables = {
        "hot": "tasmax",
        "warm": "tasmin",
        "frost": "tasmin",
        "temperature": "tas",
        "rain": "pr",
        "dry": "pr",
    }

    def period(model, scenario, years):
        annual = {m: [] for m in conf["metrics"]}
        for year in range(years[0], years[1] + 1):
            experiment = "historical" if year <= 2014 else scenario
            for variable in dict.fromkeys(variables[m] for m in conf["metrics"]):
                metrics = [m for m in conf["metrics"] if variables[m] == variable]

                def build(experiment=experiment, variable=variable, year=year, metrics=metrics):
                    data, t = climate_daily(ctx, model, experiment, variable, year)
                    return np.stack(
                        [
                            align(daily_index(data, m, conf["thresholds"]), t, transform, shape)
                            for m in metrics
                        ]
                    )

                fields = ctx.cached_array(
                    f"climate-indices-{model}-{experiment}-{year}-{variable}-{metrics}", build
                )
                for i, m in enumerate(metrics):
                    annual[m].append(fields[i])
        return {m: finite_mean(np.stack(v), 1) for m, v in annual.items()}

    # Read one source header per selected model even when annual arrays are cached.
    for model in conf["models"]:
        climate_daily(
            ctx,
            model,
            "historical" if conf["baseline"][0] <= 2014 else "ssp245",
            variables[conf["metrics"][0]],
            conf["baseline"][0],
        )
    baselines = [period(model, "ssp245", conf["baseline"]) for model in conf["models"]]
    arrays, names, layers = [], [], []
    for m in conf["metrics"]:
        base = np.stack([b[m] for b in baselines])
        arrays.append(finite_mean(base, 1))
        names.append(labels[m] + " · baseline")
        band = len(arrays)
        unit = "°C" if m == "temperature" else "days/year"
        layers.append(
            identity(
                "climate",
                band,
                names[-1],
                unit,
                f"{conf['baseline'][0]}–{conf['baseline'][1]} ensemble mean",
            )
        )
    for scenario in conf["scenarios"]:
        futures = [period(model, scenario, conf["future"]) for model in conf["models"]]
        for j, m in enumerate(conf["metrics"]):
            future = np.stack([f[m] for f in futures])
            changes = future - np.stack([b[m] for b in baselines])
            complete = np.isfinite(changes).all(0)
            low = np.min(changes, axis=0)
            high = np.max(changes, axis=0)
            low[~complete] = np.nan
            high[~complete] = np.nan
            first = len(arrays) + 1
            arrays.extend([finite_mean(future, 1), low, high])
            names.extend(
                [
                    labels[m] + f" · {scenario}",
                    labels[m] + f" · {scenario} change minimum",
                    labels[m] + f" · {scenario} change maximum",
                ]
            )
            period_label = f"{scenario} {conf['future'][0]}–{conf['future'][1]} vs {conf['baseline'][0]}–{conf['baseline'][1]}"
            unit = "°C" if m == "temperature" else "days/year"
            layers.extend(
                [
                    identity("climate", first, names[-3], unit, period_label),
                    difference(
                        "climate",
                        j + 1,
                        first,
                        labels[m] + f" · {scenario} change",
                        unit,
                        period_label,
                    ),
                    identity(
                        "climate", first + 1, names[-2], unit, period_label, palette="diverging"
                    ),
                    identity(
                        "climate", first + 2, names[-1], unit, period_label, palette="diverging"
                    ),
                ]
            )
    source = dict(
        id="nex-gddp",
        name="NASA NEX-GDDP-CMIP6 daily downscaled projections",
        url="https://www.nccs.nasa.gov/data-collections/nex-gddp-cmip6/",
        version="v2.0 · r1i1p1f1 · " + ", ".join(conf["models"]),
        licence="; ".join(f"{model}: {ctx.climate_licences[model]}" for model in conf["models"]),
        description="Official NCCS THREDDS/NCSS spatial subsets; daily thresholds, annual indices and period/ensemble statistics computed locally.",
        resolution="0.25° (approximately 25 km); no downscaling by this toolkit",
    )
    ctx.write(
        "climate",
        arrays,
        names,
        transform,
        4326,
        weights,
        source,
        layers,
        [
            "Use historical files through 2014, SSP2-4.5 thereafter for the baseline, and the selected SSP experiments for the future.",
            "Convert K to °C and precipitation kg m−2 s−1 to mm/day. Calculate annual counts, daily mean temperature and longest within-calendar-year dry spell; missing daily values invalidate that annual pixel. Period means require every year, ensemble means every selected model.",
            "Differences are future minus baseline. Minimum/maximum changes describe the selected models, not probabilities or confidence intervals. Daily calendar length follows the provider.",
        ],
        [
            "Modelled projections, not observations or forecasts. Coarse-grid results are regional screening.",
            "Dry spells reset on 1 January. Thresholds and short reference periods require local justification.",
            "This package uses NASA v2.0; it is not numerically identical to the earlier Ganjam v1.1 preparation.",
        ],
    )


def groundwater(ctx):
    conf = ctx.config["groundwater"]
    start, end = conf["baseline"][0], conf["monitoring"][1]
    transform, shape = grid_for(ctx.aoi, 0.25)
    weights = area_weights(ctx.aoi, ctx.area_aoi, transform, shape)
    monthly, dates = [], []
    with GldasReader(ctx) as reader:
        for year in range(start, end + 1):
            for month in range(1, 13):
                if year == 2003 and month == 1:
                    continue
                ctx.log(f"Groundwater: {year}-{month:02}")

                def build(year=year, month=month):
                    count = calendar.monthrange(year, month)[1]
                    first = date(year, month, 1)
                    last = date(year, month, count)
                    items = [g for g in granules(ctx, "GLDAS_CLSM025_DA1_D", "2.2", first, last) if first <= granule_date(g) <= last]
                    days = [granule_date(g) for g in items]
                    if len(days) != len(set(days)):
                        raise ValueError("Duplicate GLDAS daily granules; source review required.")
                    daily = {}
                    for day, path in zip(days, reader.paths(items), strict=True):
                        data, t = read_daily(path, day, reader.window)
                        daily[day] = align(data, t, transform, shape)
                    if not daily:
                        raise ValueError("No GLDAS daily values for this month.")
                    values = np.stack(
                        [
                            daily.get(first + timedelta(days=i), np.full(shape, np.nan))
                            for i in range(count)
                        ]
                    )
                    return finite_mean(values, 0.9)

                monthly.append(ctx.cached_array(f"gldas-native-month-v1-{year}-{month}", build))
                dates.append(f"{year}-{month:02}")
    monthly = np.stack(monthly)
    means = []
    for a, b in [conf["baseline"], conf["monitoring"]]:
        means.append(finite_mean(monthly[[a <= int(d[:4]) <= b for d in dates]], 0.9))
    annual = np.stack(
        [
            finite_mean(monthly[[d.startswith(str(y)) for d in dates]], 0.9)
            for y in range(start, end + 1)
        ]
    )
    trend = np.full(shape, np.nan, dtype="float32")
    for row, col in zip(*np.where(weights > 0), strict=True):
        values = annual[:, row, col]
        valid = np.isfinite(values)
        if valid.sum() >= max(2, len(annual) * 0.9):
            trend[row, col] = theilslopes(values[valid], np.arange(start, end + 1)[valid]).slope
    arrays = [*means, trend]
    names = [
        "Baseline groundwater storage",
        "Monitoring groundwater storage",
        "Annual storage trend",
    ]
    layers = [
        identity(
            "groundwater",
            1,
            names[0],
            "mm",
            f"{conf['baseline'][0]}–{conf['baseline'][1]}",
            palette="water",
        ),
        identity(
            "groundwater",
            2,
            names[1],
            "mm",
            f"{conf['monitoring'][0]}–{conf['monitoring'][1]}",
            palette="water",
        ),
        difference(
            "groundwater", 1, 2, "Groundwater storage change", "mm", "Monitoring minus baseline"
        ),
        identity("groundwater", 3, names[2], "mm/year", f"{start}–{end}", palette="diverging"),
    ]
    points = [
        dict(
            date=d,
            value=statistics(v, weights)["mean"],
            coveragePct=statistics(v, weights)["coveragePct"],
        )
        for d, v in zip(dates, monthly, strict=True)
    ]
    source = dict(
        id="gldas",
        name="NASA GLDAS 2.2 Catchment / GRACE data assimilation",
        url="https://disc.gsfc.nasa.gov/datasets/GLDAS_CLSM025_DA1_D_2.2/summary",
        version="CLSM025_DA1_D 2.2",
        licence="NASA Earth Science open data",
        description="Daily GWS_tavg native-grid regional subsets from NASA OPeNDAP, authenticated with the server account for online tasks or the user's account for local tasks; kg/m² water equivalent equals mm.",
        resolution="0.25° (approximately 27 km)",
    )
    ctx.write(
        "groundwater",
        arrays,
        names,
        transform,
        4326,
        weights,
        source,
        layers,
        [
            "Acquire only the study-area GWS_tavg cells at the original 0.25° spacing; validate each daily date, coordinates and unit before calculation. No interpolation to a finer resolution.",
            "Daily storage is averaged by month with at least 90% of expected days. Baseline, monitoring and annual means require at least 90% of months. Equal-month weighting; January 2003 is unavailable and excluded explicitly.",
            "Theil–Sen slope of annual means requires at least 90% of years (and two years). No significance test is implied.",
        ],
        [
            "Modelled storage is not water-table depth, pumping volume, recharge or well yield.",
            "Long periods need many daily source requests and can take time. Regional subsets and verified caches reduce downloads without changing the source grid.",
            "Climate and model assumptions can affect storage; this analysis does not isolate a cause.",
        ],
        series=[dict(title="Monthly groundwater storage", unit="mm", points=points)],
    )


def season_dates(year, season):
    first = date(year, season["start"], 1)
    last_year = year + (season["end"] < season["start"])
    next_month = season["end"] % 12 + 1
    end = date(last_year + (season["end"] == 12), next_month, 1)
    return first, end


def composite_dates(first, end, step):
    dates = []
    for year in range(first.year, end.year + 1):
        day = date(year, 1, 1)
        while day.year == year:
            if first <= day < end:
                dates.append(day)
            day += timedelta(days=step)
    return dates


def vegetation_health(ndvi, lst, minimum):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        lo, hi = np.nanmin(ndvi, axis=0), np.nanmax(ndvi, axis=0)
        cold, hot = np.nanmin(lst, axis=0), np.nanmax(lst, axis=0)
    good = (
        (np.isfinite(ndvi).sum(0) >= minimum)
        & (np.isfinite(lst).sum(0) >= minimum)
        & (hi - lo > 1e-6)
        & (hot - cold > 1e-6)
    )
    vci = np.full(ndvi.shape, np.nan)
    tci = vci.copy()
    np.divide(100 * (ndvi - lo), hi - lo, out=vci, where=good)
    np.divide(100 * (hot - lst), hot - cold, out=tci, where=good)
    return np.clip((vci + tci) / 2, 0, 100).astype("float32")


def drought(ctx):
    conf = ctx.config["drought"]
    years = list(range(conf["reference"][0], conf["reference"][1] + 1))
    inventory = None
    if getattr(ctx, "server_mode", False):
        # Search the archive twice, then reuse that inventory across all seasons.
        # Reject oversized runs before downloading any MODIS scientific files.
        inventory = {}
        selected = []
        windows = [season_dates(y, s) for s in conf["seasons"] for y in years]
        for product, step in [("MOD13A2", 16), ("MOD11A2", 8)]:
            ctx.log(f"Checking {product} source dates and download size…")
            expected = {d for a, b in windows for d in composite_dates(a, b, step)}
            items = granules(ctx, product, "061", min(expected), max(expected))
            inventory[product] = [g for g in items if granule_date(g) in expected]
            selected.extend(inventory[product])
        check_modis_budget(ctx, selected)
    transform, shape = grid_for(ctx.aoi, 1000, 6933)
    weights, sources, mask_method = mask_weights(ctx, transform, shape, 6933, crop=True)
    arrays, names, layers, series = [], [], [], []
    health = []
    for season in conf["seasons"]:
        ndvi, lst, cover = [], [], []
        for year in years:
            first, end = season_dates(year, season)
            qualities = []
            for kind, product, step, minimum in [
                ("ndvi", "MOD13A2", 16, 0.3),
                ("lst", "MOD11A2", 8, 0.2),
            ]:
                ctx.log(f"Vegetation health: {season['name']} {year} / {kind}")

                def build(
                    first=first, end=end, step=step, product=product, kind=kind, minimum=minimum
                ):
                    expected = composite_dates(first, end, step)
                    items = inventory[product] if inventory is not None else granules(ctx, product, "061", first, end - timedelta(days=1))
                    groups = defaultdict(list)
                    for item in items:
                        day = granule_date(item)
                        if day in expected:
                            groups[day].append(item)
                    total = np.zeros(shape, dtype="float64")
                    count = np.zeros(shape, dtype="int32")
                    for tiles in groups.values():
                        mosaic = np.full(shape, np.nan, dtype="float32")
                        for tile in tiles:
                            part = modis_array(download_granule(ctx, tile), kind, transform, shape)
                            mosaic[np.isfinite(part)] = part[np.isfinite(part)]
                        total += np.nan_to_num(mosaic)
                        count += np.isfinite(mosaic)
                    mean = np.divide(
                        total,
                        count,
                        out=np.full(shape, np.nan),
                        where=count >= len(expected) * minimum,
                    )
                    return np.stack([mean, count / len(expected) * 100]).astype("float32")

                data = ctx.cached_array(
                    f"modis-season-{kind}-{year}-{season['start']}-{season['end']}", build
                )
                (ndvi if kind == "ndvi" else lst).append(data[0])
                qualities.append(data[1])
            cover.append(qualities)
        vhi = vegetation_health(np.stack(ndvi), np.stack(lst), conf["minimumYears"])
        health.append(vhi)
        pair = []
        for year in conf["compare"]:
            i = years.index(year)
            arrays.append(vhi[i])
            names.append(f"{season['name']} VHI · {year}")
            pair.append(len(arrays))
            layers.append(
                identity(
                    "drought",
                    len(arrays),
                    names[-1],
                    "VHI (0–100)",
                    str(year),
                    palette="health",
                    domain=[0, 100],
                    thresholds=[
                        dict(label="VHI < 10", max=10),
                        dict(label="10–<20", min=10, max=20),
                        dict(label="20–<30", min=20, max=30),
                        dict(label="30–<40", min=30, max=40),
                        dict(label="≥40", min=40),
                    ],
                )
            )
            for j, kind in enumerate(["NDVI", "LST"]):
                arrays.append(cover[i][j])
                names.append(f"{season['name']} {kind} valid composites · {year}")
                layers.append(
                    identity("drought", len(arrays), names[-1], "%", str(year), domain=[0, 100])
                )
        layers.append(
            difference(
                "drought",
                *pair,
                f"{season['name']} VHI change",
                "index points",
                f"{conf['compare'][1]} minus {conf['compare'][0]}",
            )
        )
        series.append(
            dict(
                title=season["name"] + " vegetation health",
                unit="VHI",
                points=[
                    dict(
                        date=str(y),
                        value=statistics(v, weights)["mean"],
                        coveragePct=statistics(v, weights)["coveragePct"],
                    )
                    for y, v in zip(years, vhi, strict=True)
                ],
            )
        )
    if len(health) == 2:
        for year in conf["compare"]:
            i = years.index(year)
            arrays.append((health[0][i] + health[1][i]) / 2)
            names.append(f"Two-season VHI · {year}")
            layers.append(
                identity(
                    "drought",
                    len(arrays),
                    names[-1],
                    "VHI (0–100)",
                    str(year),
                    palette="health",
                    domain=[0, 100],
                )
            )
        layers.append(
            difference(
                "drought",
                len(arrays) - 1,
                len(arrays),
                "Two-season VHI change",
                "index points",
                "Later minus earlier crop-start year",
            )
        )
    source = dict(
        id="modis-vhi",
        name="NASA MODIS NDVI and daytime land-surface temperature",
        url="https://doi.org/10.5067/MODIS/MOD13A2.061",
        version="MOD13A2.061 and MOD11A2.061",
        licence="NASA LP DAAC unrestricted use and redistribution",
        description="Native HDF files; NDVI doi:10.5067/MODIS/MOD13A2.061; LST doi:10.5067/MODIS/MOD11A2.061. Local QA filtering and seasonal VHI.",
        resolution="1 km MODIS; nearest-neighbour EPSG:6933 analysis grid",
    )
    ctx.write(
        "drought",
        arrays,
        names,
        transform,
        6933,
        weights,
        source,
        layers,
        [
            "NDVI pixel reliability 0/1; daytime LST mandatory QC=0 and error bits ≤1. Seasonal means require ≥30% of expected NDVI composites and ≥20% of LST composites. Dates refer to composite starts; cross-year seasons use the starting year.",
            f"VCI=100*(NDVI−min)/(max−min); TCI=100*(max−LST)/(max−min); VHI=(VCI+TCI)/2. Same-season {years[0]}–{years[-1]} reference, ≥{conf['minimumYears']} valid years per variable; flat ranges are unknown.",
            mask_method,
            "Two-season summary, when selected, requires both seasons and gives them equal weight.",
        ],
        [
            "This is seasonal MODIS vegetation-health screening, not FAO ASIS or a crop-stage-weighted drought product.",
            "Season calendars and fixed masks require local review. Clear-sky bias, irrigation, crops and pests can affect the result; drought causality is not established.",
        ],
        series=series,
        extra_sources=sources,
    )


RUNNERS = {
    "flood": flood,
    "degradation": degradation,
    "climate": climate,
    "groundwater": groundwater,
    "drought": drought,
}
