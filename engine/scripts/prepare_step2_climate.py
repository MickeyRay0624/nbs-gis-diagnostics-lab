"""NEX-GDDP-CMIP6 three-model climate screening, retaining the 0.25° grid."""

import calendar
import hashlib
import json
import numpy as np
import rasterio
from step2_package import CACHE, OUT, area_weights, identity, write_asset, update_catalog

MODELS = ["ACCESS-CM2", "MIROC6", "MPI-ESM1-2-HR"]
METRICS = [
    ("hot", "Hot days (Tmax >35°C)", "days/year"),
    ("warm", "Warm nights (Tmin >20°C)", "days/year"),
    ("frost", "Frost days (Tmin <0°C)", "days/year"),
    ("temperature", "Mean temperature", "°C"),
    ("rain", "Heavy-rain days (>100 mm/day)", "days/year"),
    ("dry", "Mean dry-spell length (<1 mm/day)", "days/spell"),
]


def annual_indices(daily):
    """daily dimensions: day, [tasmax,tasmin,tas,pr], row, col."""
    complete = np.isfinite(daily).all(axis=(0, 1))
    dry = daily[:, 3] * 86400 < 1
    starts = dry[0].astype("int32") + np.sum(dry[1:] & ~dry[:-1], axis=0)
    result = np.stack(
        [
            np.sum(daily[:, 0] > 308.15, axis=0),
            np.sum(daily[:, 1] > 293.15, axis=0),
            np.sum(daily[:, 1] < 273.15, axis=0),
            np.mean(daily[:, 2], axis=0) - 273.15,
            np.sum(daily[:, 3] * 86400 > 100, axis=0),
            np.sum(dry, axis=0) / np.maximum(starts, 1),
        ]
    ).astype("float32")
    result[:, ~complete] = np.nan
    return result


def main():
    cubes = {}
    hashes = {}
    for scenario, starts in [
        ("baseline", [1991, 2001, 2011]),
        ("ssp245", [2040, 2050, 2060]),
        ("ssp585", [2040, 2050, 2060]),
    ]:
        models = []
        for model in MODELS:
            blocks = []
            for first in starts:
                path = (
                    CACHE
                    / f"climate_{model.lower()}_{'ssp245' if scenario == 'baseline' else scenario}_{first}.tif"
                )
                hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
                with rasterio.open(path) as s:
                    if s.count != 60 or s.crs.to_epsg() != 4326 or s.res != (0.25, 0.25):
                        raise ValueError("Unexpected annual climate export")
                    d = s.read().astype("float64")
                    d[d == -9999] = np.nan
                    if blocks and s.transform != transform:
                        raise ValueError("Climate grids differ")
                    transform = s.transform
                    blocks.append(d.reshape(10, 6, *s.shape))
            models.append(np.concatenate(blocks))
        cubes[scenario] = np.stack(models)
    weights = area_weights(transform, 5, 7)
    # A complete three-model, thirty-year signal: do not average changing sets.
    means = {scenario: np.mean(values, axis=1) for scenario, values in cubes.items()}
    arrays = []
    names = []
    layers = []
    aid = "nex-climate"
    sid = "nex-gddp"
    mean_bands = {}
    for scenario in ["baseline", "ssp245", "ssp585"]:
        ensemble = np.mean(means[scenario], axis=0)
        mean_bands[scenario] = []
        for i, (key, title, unit) in enumerate(METRICS):
            arrays.append(ensemble[i])
            names.append(f"{scenario} ensemble {key}")
            band = len(arrays)
            mean_bands[scenario].append(band)
            period = (
                "1991–2020 (historical + SSP2-4.5 from 2015)"
                if scenario == "baseline"
                else f"2040–2069 · {'SSP2-4.5' if scenario == 'ssp245' else 'SSP5-8.5'}"
            )
            layers.append(
                identity(
                    aid,
                    band,
                    f"{title} · {'baseline' if scenario == 'baseline' else 'SSP2-4.5' if scenario == 'ssp245' else 'SSP5-8.5'}",
                    unit,
                    period,
                    interpretation="Equal-weight mean of three model climatologies. All 30 years and all three models must be valid. Values retain the native coarse grid; they do not forecast individual events.",
                )
            )
    for scenario in ["ssp245", "ssp585"]:
        delta = means[scenario] - means["baseline"]
        scenario_name = "SSP2-4.5" if scenario == "ssp245" else "SSP5-8.5"
        for i, (key, title, unit) in enumerate(METRICS):
            layers.append(
                dict(
                    id=f"{aid}-{scenario}-{key}-change",
                    title=f"{title} change · {scenario_name}",
                    unit=unit,
                    period="2040–2069 minus 1991–2020",
                    operation="difference",
                    inputs=[
                        dict(raster=aid, band=mean_bands["baseline"][i]),
                        dict(raster=aid, band=mean_bands[scenario][i]),
                    ],
                    palette="diverging",
                    interpretation="Change of the equal-weight three-model mean. Read alongside the minimum and maximum model changes; this range is not a confidence interval.",
                )
            )
            for bound, fn in [("minimum", np.min), ("maximum", np.max)]:
                arrays.append(fn(delta[:, i], axis=0))
                names.append(f"{scenario} {key} change model {bound}")
                layers.append(
                    identity(
                        aid,
                        len(arrays),
                        f"{title} change, model {bound} · {scenario_name}",
                        unit,
                        "2040–2069 minus 1991–2020",
                        "diverging",
                        interpretation="Extreme value across the three individual model changes, computed per cell. The maps show model spread, not probability bounds or a full CMIP6 uncertainty range.",
                    )
                )
    # Individual-model climatologies are retained in the downloadable input asset.
    for scenario in ["baseline", "ssp245", "ssp585"]:
        for m, model in enumerate(MODELS):
            for i, (key, _, _) in enumerate(METRICS):
                arrays.append(means[scenario][m, i])
                names.append(f"{model} {scenario} {key}")
    series = []
    for scenario in ["ssp245", "ssp585"]:
        for i, (key, title, unit) in enumerate(METRICS):
            points = []
            for label in ["baseline", scenario]:
                if label == scenario:
                    points.append(dict(date="2030", value=None))
                years = range(1991, 2021) if label == "baseline" else range(2040, 2070)
                for year, a in zip(years, np.mean(cubes[label], axis=0)[:, i]):
                    valid = np.isfinite(a) & (weights > 0)
                    area = weights[valid].astype("float64").sum()
                    points.append(
                        dict(
                            date=str(year),
                            value=float(np.sum(a[valid] * weights[valid]) / area) if area else None,
                            coveragePct=float(area / weights.sum(dtype="float64") * 100),
                        )
                    )
            series.append(
                dict(
                    title=f"{title} · {'SSP2-4.5' if scenario == 'ssp245' else 'SSP5-8.5'}",
                    unit=unit,
                    points=points,
                )
            )
    methods = [
        "NASA NEX-GDDP-CMIP6 version 1.1; ACCESS-CM2, MIROC6 and MPI-ESM1-2-HR. Historical 1991–2014 + SSP2-4.5 2015–2020 form the baseline; compare SSP2-4.5 and SSP5-8.5 for 2040–2069.",
        "Daily Kelvin temperatures converted to Celsius; precipitation kg m⁻² s⁻¹ multiplied by 86,400 to mm/day. Hot days Tmax>35°C, warm nights Tmin>20°C, frost days Tmin<0°C, heavy rain>100 mm/day, and daily mean temperature.",
        "Dry spells use precipitation <1 mm/day. Annual mean spell length = dry days / runs of dry days; a dry spell crossing 1 January is split at the year boundary. A year with no dry days has length zero.",
        "Annual indices require every calendar day valid. Compute each model’s 30-year mean, then the equal-weight three-model mean. Minimum/maximum changes are taken across individual model changes. Preserve leap-year day counts.",
        "Keep the 0.25° grid and weight district statistics by exact AOI-cell intersections. The individual-model climatologies remain in the source package; annual ensemble series are exported separately.",
    ]
    source = dict(
        id=sid,
        name="NASA NEX-GDDP-CMIP6",
        url="https://developers.google.com/earth-engine/datasets/catalog/NASA_GDDP-CMIP6",
        version="Earth Engine collection version 1.1 (verified image-property histogram); prepared September 2026",
        licence="CMIP6 terms; CC BY 4.0 for ACCESS-CM2, MIROC6 and MPI-ESM1-2-HR via NEX-GDDP-CMIP6",
        description="Bias-corrected spatially disaggregated daily CMIP6 projections, 0.25°; model selection and scenario chains explicitly recorded. Thrasher et al. (2022), Scientific Data, doi:10.1038/s41597-022-01393-4.",
    )
    asset, reference = write_asset(aid, arrays, names, transform, sid, "0.25° (~25–28 km)", methods)
    asset["sourceHashes"] = hashes
    module = dict(
        id="climate",
        title="Climate extremes",
        question="How could heat, rainfall extremes and dry spells change?",
        status="available",
        sources=[sid],
        method=methods,
        limitations=[
            "SSP2-4.5 and SSP5-8.5 are available public-data scenarios, not the original report’s RCP2.6. A low-emission scenario is deferred; do not interpret these outputs as RCP2.6 results.",
            "Three models are a limited ensemble. Their range is not a confidence interval and does not represent the full CMIP6 uncertainty distribution. Downscaling does not resolve village microclimates.",
            "Baseline is modelled, not station observation. The 2015–2020 historical extension follows SSP2-4.5. Thresholds need local impact review. No combined risk score or arbitrary weighting is applied.",
            "The series has an intentional gap between 2020 and 2040. Future annual points are model projections, not event forecasts.",
        ],
        fieldChecks=[
            "Which heat, rainfall and dry-spell thresholds matter for local crops, health and infrastructure?",
            "Do weather-station records reveal local model biases?",
            "How do planning decisions change between the two scenarios and across model spread?",
        ],
        layers=layers,
        series=series,
        missing=[],
    )
    update_catalog(asset, module, source, reference)
    print(
        "Prepared",
        len(layers),
        "climate layers,",
        len(arrays),
        "source bands; baseline means:",
        [(r["name"], r["mean"]) for r in reference[:6]],
        flush=True,
    )


if __name__ == "__main__":
    main()
