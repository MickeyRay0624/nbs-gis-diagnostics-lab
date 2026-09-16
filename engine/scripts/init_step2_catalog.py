"""Initialize the catalog once; never replace a populated public package."""

import hashlib
import json
from datetime import datetime, timezone

from step2_package import AOI_AREA, AOI_PATH, OUT

definitions = [
    (
        "lulc",
        "Land-cover change",
        "Which land-cover classes are changing?",
        [
            "Compare categorical maps on a common equal-area grid and common valid footprint.",
            "Report transition matrices and gross gains, losses and net change.",
        ],
        [
            "GLC-FCS30D supports consistent comparisons, with classification and resampling uncertainty that require local review."
        ],
        [
            "Which mapped conversions can local land managers confirm?",
            "Do plantation changes represent ecosystem loss or management rotations?",
        ],
    ),
    (
        "fragmentation",
        "Forest fragmentation",
        "Where is forest becoming smaller or more exposed?",
        [
            "Use the selected forest crosswalk, eight-connected patches and Euclidean distance to known non-forest.",
            "Compute whole-landscape patches before protection stratification.",
        ],
        [
            "Scale and edge width change the result. Internal clearings are non-forest, not a perforated-forest class.",
            "Protected-area / OECM completeness and applicability need review.",
        ],
        [
            "Are narrow mapped breaks roads, seasonal gaps or actual ecological barriers?",
            "Which protected-area and OECM boundaries apply to this period?",
        ],
    ),
    (
        "groundwater",
        "Groundwater storage",
        "How has regional groundwater storage changed?",
        [
            "Use GLDAS 2.2 GWS_tavg, retaining its native 0.25-degree grid.",
            "Compare monthly means for 2003–2013 and 2014–2023; report the full monthly time series and absolute storage change.",
        ],
        [
            "Modelled water storage in millimetres is not measured groundwater-table depth.",
            "The coarse regional signal cannot locate a failing well or resolve villages.",
        ],
        [
            "Do local well hydrographs corroborate the seasonal pattern and long-term change?",
            "Have pumping, irrigation or recharge practices changed?",
        ],
    ),
    (
        "drought",
        "Drought & vegetation stress",
        "When and where are crops experiencing stress?",
        [
            "Compare two agricultural seasons and baseline/monitoring conditions using a documented vegetation-health or drought product.",
            "Keep the cropland denominator, quality flags, seasonal definition and reference climatology explicit.",
        ],
        [
            "Vegetation stress is not uniquely attributable to drought; cropping calendars and irrigation influence the signal.",
            "ASIS access may need provider permission. An alternative product must be named rather than presented as ASIS.",
        ],
        [
            "Do sowing dates and crop types match the assumed growing seasons?",
            "Do farmers report water shortages during the mapped stress periods?",
        ],
    ),
    (
        "climate",
        "Climate extremes",
        "How could heat and rainfall extremes change?",
        [
            "Compare 1991–2020 with 2040–2069 using consistent NEX-GDDP-CMIP6 models and SSP2-4.5 / SSP5-8.5.",
            "Report hot days, warm nights, frost days, heavy-rain days and dry-spell length separately, with model spread.",
        ],
        [
            "The available SSP2-4.5 and SSP5-8.5 scenarios differ from the report's RCP2.6; a low-emission scenario is deferred.",
            "Daily 0.25-degree climate projections do not resolve local microclimates or provide event forecasts.",
        ],
        [
            "Which thresholds match locally important crop, health and infrastructure impacts?",
            "Do local weather-station records reveal systematic model biases?",
        ],
    ),
    (
        "flood",
        "River flood hazard",
        "Which areas intersect modelled river flooding?",
        [
            "Read JRC/CEMS-GloFAS water depths for multiple return periods on the native 3-arc-second grid.",
            "Retain permanent-water and spurious-depth flags. Report mapped inundation extent and depth, with unknown coverage explicit.",
        ],
        [
            "Riverine hazard does not cover coastal storm surge, all small catchments or urban drainage.",
            "Return periods describe probabilities under model assumptions; they are not dates of future floods.",
        ],
        [
            "Do documented flood extents match the mapped river corridors?",
            "Where do embankments, drainage failures or storm surge change local exposure?",
        ],
    ),
    (
        "degradation",
        "Land degradation",
        "Where do land-condition indicators show deterioration?",
        [
            "Evaluate land productivity, land-cover transitions and soil organic carbon as separate subindicators.",
            "Combine -1 degraded, 0 stable and +1 improving classes using one-out-all-out. Missing components never imply stable land.",
        ],
        [
            "A SoilGrids baseline alone cannot establish soil-carbon change.",
            "A locally reviewed crosswalk and carbon-change model are required; screening outputs are not an official national SDG submission.",
        ],
        [
            "Do vegetation trends reflect degradation, crop cycles or restoration?",
            "Can soil sampling and land-management histories corroborate the carbon estimate?",
        ],
    ),
]
OUT.mkdir(parents=True, exist_ok=True)
path = OUT / "catalog.json"
if path.exists():
    raise SystemExit("Catalog already exists; update individual modules instead.")
modules = [
    dict(
        id=i,
        title=t,
        question=q,
        method=m,
        limitations=l,
        fieldChecks=f,
        status="needs-data",
        sources=[],
        layers=[],
        missing=["A source-verified Ganjam numeric package is required."],
    )
    for i, t, q, m, l, f in definitions
]
catalog = dict(
    schema="nbs-step2/v1",
    version="ganjam-2026-09-16",
    preparedAt=datetime.now(timezone.utc).isoformat(),
    studyArea=dict(
        name="Ganjam District, Odisha",
        areaKm2=AOI_AREA.area / 1e6,
        boundary="ganjam-aoi.geojson",
        sha256=hashlib.sha256(AOI_PATH.read_bytes()).hexdigest(),
    ),
    modules=modules,
    sources=[],
    rasters=[],
    protection=dict(
        status="not-assessed",
        detail="A complete protected-area / OECM overlay and applicability review have not been supplied. No absence is inferred.",
    ),
    review=dict(
        status="pending",
        detail="Technical screening for expert review. Completion requires review of all seven modules, protection applicability, uncertainties and field-check questions.",
    ),
)
path.write_text(json.dumps(catalog, indent=2) + "\n")
