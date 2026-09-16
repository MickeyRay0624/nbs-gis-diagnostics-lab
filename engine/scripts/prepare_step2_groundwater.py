"""Build public groundwater evidence from gee_groundwater.js yearly exports."""

import json

import numpy as np
import rasterio
from scipy.stats import theilslopes

from step2_package import CACHE, OUT, area_weights, identity, update_catalog, write_asset

arrays, dates = [], []
transform = None
for year in range(2003, 2024):
    path = CACHE / f"gldas-{year}.tif"
    with rasterio.open(path) as src:
        if transform is not None and transform != src.transform:
            raise ValueError("Groundwater exports must share the native grid")
        transform = src.transform
        data = src.read().astype("float32")
        data[data <= -9999] = np.nan
        months = range(2 if year == 2003 else 1, 13)
        if len(data) != len(months) or src.crs.to_epsg() != 4326:
            raise ValueError(f"Unexpected monthly export for {year}")
        dates.extend(f"{year}-{month:02}" for month in months)
        arrays.extend(data)
monthly = np.stack(arrays)
weights = area_weights(transform, monthly.shape[2], monthly.shape[1])


def period_mean(values):
    valid = np.isfinite(values).sum(axis=0)
    total = np.nansum(values, axis=0, dtype="float64")
    return np.divide(
        total, valid, out=np.full(valid.shape, np.nan), where=(valid >= len(values) * 0.9)
    ).astype("float32")


baseline = period_mean(monthly[:131])
monitor = period_mean(monthly[131:])
annual = np.stack(
    [period_mean(monthly[[d.startswith(str(y)) for d in dates]]) for y in range(2003, 2024)]
)
trend = np.full(baseline.shape, np.nan, dtype="float32")
for y, x in zip(*np.where(weights > 0)):
    values = annual[:, y, x]
    valid = np.isfinite(values)
    if valid.sum() >= 19:
        trend[y, x] = theilslopes(values[valid], np.arange(2003, 2024)[valid]).slope
asset, reference = write_asset(
    "gldas-groundwater",
    [baseline, monitor, trend],
    [
        "Baseline monthly-mean storage mm",
        "Monitoring monthly-mean storage mm",
        "Annual Theil-Sen storage trend mm/year",
    ],
    transform,
    "gldas",
    "0.25 degrees (approximately 27 km)",
    "GLDAS 2.2 GWS_tavg. Monthly means require at least 90% daily coverage; period means require at least 90% monthly coverage. February 2003–December 2013 baseline; January 2014–December 2023 monitoring. Equal-month weighting. Native grid retained; fractional AOI intersections in EPSG:6933. Annual trend is Theil-Sen, requiring at least 19 valid years; no significance claim.",
)
module = next(
    m for m in json.loads((OUT / "catalog.json").read_text())["modules"] if m["id"] == "groundwater"
)
module.update(
    status="available",
    sources=["gldas"],
    missing=[],
    layers=[
        identity(
            asset["id"], 1, "Groundwater storage · baseline", "mm", "2003-02 to 2013-12", "water"
        ),
        identity(
            asset["id"], 2, "Groundwater storage · monitoring", "mm", "2014-01 to 2023-12", "water"
        ),
        dict(
            id="groundwater-change",
            title="Groundwater storage change",
            unit="mm",
            period="Monitoring minus baseline",
            operation="difference",
            inputs=[dict(raster=asset["id"], band=1), dict(raster=asset["id"], band=2)],
            palette="diverging",
            thresholds=[dict(label="Storage decrease", max=0), dict(label="No decrease", min=0)],
            interpretation="Negative values indicate lower modelled groundwater storage. They are not changes in water-table depth, pumping volume or well yield. Compare on the common valid footprint.",
        ),
        identity(
            asset["id"],
            3,
            "Annual storage trend",
            "mm/year",
            "2003–2023 annual means",
            "diverging",
            interpretation="Theil-Sen slope summarises annual storage direction. The shortened 2003 record begins in February. No statistical-significance or causal claim is made.",
        ),
    ],
)
series = []
for date, data in zip(dates, monthly):
    valid = np.isfinite(data) & (weights > 0)
    area = weights[valid].astype("float64").sum()
    series.append(
        dict(
            date=date,
            value=float(np.sum(data[valid].astype("float64") * weights[valid]) / area)
            if area
            else None,
            coveragePct=float(area / weights.astype("float64").sum() * 100),
        )
    )
module["series"] = [dict(title="Monthly groundwater storage", unit="mm", points=series)]
module["method"] = [
    asset["processing"],
    "Browser differences and summaries use the common valid footprint and AOI area weights.",
]
module["limitations"] += [
    "January 2003 is absent from the provider collection and has not been imputed.",
    "A storage trend can reflect climate and the model's assumptions; it does not isolate pumping or recharge mechanisms.",
]
source = dict(
    id="gldas",
    name="NASA GLDAS 2.2 Catchment / GRACE data assimilation",
    version="V022 / CLSM / G025 / DA1D",
    licence="NASA Earth Science open data",
    url="https://developers.google.com/earth-engine/datasets/catalog/NASA_GLDAS_V022_CLSM_G025_DA1D",
    description="NASA/GLDAS/V022/CLSM/G025/DA1D, GWS_tavg, millimetres. Daily modelled groundwater storage, February 2003–December 2023. Export script: engine/scripts/gee_groundwater.js.",
)
module["method"] = list(dict.fromkeys(module["method"]))
module["limitations"] = list(dict.fromkeys(module["limitations"]))
update_catalog(asset, module, source, reference)
print("Prepared", asset["id"], reference)
