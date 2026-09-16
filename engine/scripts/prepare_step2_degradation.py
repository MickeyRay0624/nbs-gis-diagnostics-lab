"""Crop the published Trends.Earth v1.2 three-component diagnostic.

This preserves the publisher's periods, SOC model and productivity method. It
is not an independent recreation of those upstream scientific models.
"""

import base64
import hashlib
import json
import numpy as np
import rasterio
import requests
from rasterio.windows import from_bounds
from rasterio.warp import reproject, Resampling
from step2_package import CACHE, OUT, area_weights, identity, update_catalog, write_asset

URL = "https://storage.googleapis.com/trendsearth-public/unccd_reporting/2016-2023/TrendsEarth_SDG15.3.1_2000-2023_Trends.Earth.tif"
MD5 = "fc5d7b747a533b8bfbd542ee86688711"
CATEGORIES = [
    dict(value=-1, label="Degraded", color="#ba583e"),
    dict(value=0, label="Stable", color="#e1d79f"),
    dict(value=1, label="Improving", color="#3d8562"),
]


def productivity_classes(values):
    if not np.isin(values[np.isfinite(values)], [1, 2, 3, 4, 5]).all():
        raise ValueError("Unexpected LPD code")
    out = np.where(values <= 2, -1, np.where(values <= 4, 0, 1)).astype("float32")
    out[~np.isfinite(values)] = np.nan
    return out


def carbon_classes(values):
    if np.any(values[np.isfinite(values)] < -100):
        raise ValueError("Invalid carbon percentage")
    out = np.where(values <= -10, -1, np.where(values >= 10, 1, 0)).astype("float32")
    out[~np.isfinite(values) | (np.abs(values) == 10)] = np.nan
    return out


def combine(components):
    out = np.where(np.any(components == 1, axis=0), 1, 0).astype("float32")
    out[~np.isfinite(components).all(0)] = np.nan
    out[np.any(components == -1, axis=0)] = -1
    return out


def main():
    path = CACHE / "trendsearth-v1.2.tif"
    if not path.exists():
        header = requests.head(URL, timeout=60)
        header.raise_for_status()
        if f"md5={base64.b64encode(bytes.fromhex(MD5)).decode()}" not in header.headers.get(
            "x-goog-hash", ""
        ):
            raise ValueError("The public source changed; review its version before rebuilding.")
        with rasterio.Env(
            GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
            CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
            GDAL_HTTP_TIMEOUT="120",
        ):
            with rasterio.open(URL) as src:
                window = (
                    from_bounds(84.16, 18.93, 85.19, 20.29, src.transform)
                    .round_offsets()
                    .round_lengths()
                )
                data = src.read(window=window)
                profile = src.profile.copy()
                profile.update(
                    width=data.shape[2],
                    height=data.shape[1],
                    transform=src.window_transform(window),
                    compress="deflate",
                )
                with rasterio.open(path, "w", **profile) as out:
                    out.write(data)
                    out.descriptions = src.descriptions
    with rasterio.open(path) as src:
        data = src.read().astype("float32")
        data[data == -32768] = np.nan
        transform = src.transform
        shape = src.shape
        descriptions = src.descriptions
    weights = area_weights(transform, shape[1], shape[0])
    # Keep unknown terrestrial pixels in the denominator using an independent
    # fixed water mask, rather than treating the product's missing pixels as water.
    with rasterio.open(CACHE / "glcfcs-2002-2012-2022.tif") as s:
        water_fraction = np.zeros(shape, dtype="float32")
        reproject(
            (s.read(3) == 210).astype("float32"),
            water_fraction,
            src_transform=s.transform,
            src_crs=s.crs,
            dst_transform=transform,
            dst_crs=4326,
            resampling=Resampling.average,
        )
    weights *= 1 - np.clip(water_fraction, 0, 1)
    arrays = []
    names = []
    layers = []
    validation = []
    aid = "trendsearth-degradation"
    sid = "trendsearth"
    for suffix, prod, lc, soc, ref, period, landperiod in [
        ("baseline", 1, 2, 3, 0, "2000–2015 baseline (productivity: 2001–2015)", "2000–2015"),
        (
            "monitoring",
            10,
            11,
            12,
            9,
            "2023 assessment (productivity: 2008–2023; land cover / SOC: 2015–2022)",
            "2015–2022, in 2023 assessment",
        ),
    ]:
        p = productivity_classes(data[prod])
        c = carbon_classes(data[soc])
        components = np.stack([p, data[lc], c])
        out = combine(components)
        complete = np.isfinite(components).all(0)
        both = complete & np.isfinite(data[ref]) & (weights > 0)
        mismatch = both & (out != data[ref])
        extra = (weights > 0) & np.isfinite(out) & ~complete
        validation.append(
            dict(
                period=suffix,
                comparedCompletePixels=int(both.sum()),
                mismatchedPixels=int(mismatch.sum()),
                mismatchAreaKm2=float(weights[mismatch].sum(dtype="float64")),
                partiallyObservedDegradedAreaKm2=float(weights[extra].sum(dtype="float64")),
                roundedSOCThresholdAreaKm2=float(
                    weights[np.abs(data[soc]) == 10].sum(dtype="float64")
                ),
            )
        )
        start = len(arrays) + 1
        labels = [
            f"Productivity class · {suffix}",
            f"Land-cover subindicator · {suffix}",
            f"Soil-carbon subindicator · {suffix}",
            f"SOC change (%) · {suffix}",
            f"Productivity dynamics (5 classes) · {suffix}",
            f"Published SDG indicator · {suffix}",
            f"Complete component coverage · {suffix}",
        ]
        arrays += [p, data[lc], c, data[soc], data[prod], data[ref], complete.astype("float32")]
        names += labels
        layers.append(
            dict(
                id=f"{aid}-combined-{suffix}",
                title=f"Combined land-condition screening · {suffix}",
                unit="class",
                period=period,
                operation="one-out-all-out",
                inputs=[dict(raster=aid, band=start + i) for i in range(3)],
                palette="health",
                categories=CATEGORIES,
                interpretation="One degraded component flags degradation. Stable or improving requires all three components. Check the completeness layer: a known degraded component can flag an otherwise incomplete pixel. This is technical screening, not an official SDG submission.",
            )
        )
        for i in range(3):
            layers.append(
                identity(
                    aid,
                    start + i,
                    labels[i],
                    "class",
                    period if i == 0 else landperiod,
                    "health",
                    categories=CATEGORIES,
                    interpretation=[
                        "Trends.Earth productivity dynamics: declining and moderate decline → degraded; stressed and stable → stable; increasing → improving.",
                        "Published ESA-CCI land-cover transition interpretation. Its legend, baseline and scale differ from the GLC-FCS30D land-cover module.",
                        "Modelled 0–30 cm SOC change: below −10% degraded, above +10% improving, between −10% and +10% stable. Rounded integer values exactly ±10% are NoData because their underlying precision is unknown. This is inferred from land-cover changes, not repeated soil measurements.",
                    ][i],
                )
            )
        layers += [
            identity(
                aid,
                start + 3,
                labels[3],
                "%",
                landperiod,
                "diverging",
                interpretation="Published modelled percentage change in soil organic carbon to 30 cm. The source is integer-valued; do not infer sub-percent precision.",
            ),
            identity(
                aid,
                start + 4,
                labels[4],
                "class",
                period,
                "health",
                categories=[
                    dict(value=i + 1, label=n, color=color)
                    for i, (n, color) in enumerate(
                        [
                            ("Declining", "#9e3b31"),
                            ("Moderate decline", "#d88851"),
                            ("Stressed", "#e7c971"),
                            ("Stable", "#bad0a2"),
                            ("Increasing", "#347b55"),
                        ]
                    )
                ],
            ),
            identity(
                aid,
                start + 5,
                labels[5],
                "class",
                period,
                "health",
                categories=CATEGORIES,
                interpretation="Publisher-provided indicator for comparison. Unlike the local conservative screening rule, upstream missing components produce NoData.",
            ),
            identity(
                aid,
                start + 6,
                labels[6],
                "class",
                period,
                "sequential",
                categories=[
                    dict(value=0, label="One or more components missing", color="#aaa69a"),
                    dict(value=1, label="All three components available", color="#3d8562"),
                ],
            ),
        ]
    arrays.append(data[13])
    names.append("Published land-condition status in 2023")
    layers.append(
        identity(
            aid,
            len(arrays),
            names[-1],
            "status class",
            "2023 relative to 2000–2015 baseline",
            "health",
            categories=[
                dict(value=i + 1, label=n, color=c)
                for i, (n, c) in enumerate(
                    [
                        ("Persistent degradation", "#8e342d"),
                        ("Recent degradation", "#c46541"),
                        ("Baseline degradation", "#e4a075"),
                        ("Stability", "#e7dfb7"),
                        ("Baseline improvement", "#bad1a0"),
                        ("Recent improvement", "#6d9f78"),
                        ("Persistent improvement", "#30644e"),
                    ]
                )
            ],
            interpretation="Publisher status classes compare baseline and reporting assessments. This is different from the within-period one-out-all-out map.",
        )
    )
    methods = [
        "Use the published Trends.Earth SDG 15.3.1 v1.2 product; preserve its productivity, land-cover and SOC subindicators and its native ~250 m geographic grid.",
        "Baseline: SDG 2000–2015 with productivity 2001–2015. Latest assessment: productivity 2008–2023, land-cover/SOC changes 2015–2022 as documented in the dataset record.",
        "LPD 1/2 → degraded, 3/4 → stable, 5 → improving. SOC <−10% → degraded, >10% → improving; exactly ±10% in the integer product is treated as uncertain because upstream rounding can cross the threshold. Apply one-out-all-out to the three classified subindicators in the browser.",
        "Compare the local result with the published combined indicator on complete jointly observed cells. Retain a separate three-component completeness map and the published seven-class 2023 status.",
        "Eligible area = AOI intersection minus estimated 2022 open-water fraction from GLC-FCS30D, averaged onto the source grid. This fixed terrestrial denominator is independent of product missingness; small boundary/mixed-pixel differences from national reporting are expected.",
    ]
    source = dict(
        id=sid,
        name="Trends.Earth SDG 15.3.1 public data",
        url="https://zenodo.org/records/17514520",
        version="1.2, published 3 November 2025; Trends.Earth LPD variant",
        licence="CC BY 4.0",
        description="Conservation International et al.; DOI 10.5281/zenodo.17514520. Global COG "
        + URL
        + ". Provider MD5 "
        + MD5
        + ". Uses MOD13Q1.061 productivity, ESA-CCI land cover and land-cover-based SOC modelling.",
    )
    asset, reference = write_asset(
        aid,
        arrays,
        names,
        transform,
        sid,
        "~250 m product grid; land-cover inputs ~300 m",
        methods,
        weights=weights,
    )
    asset["sourceCropSha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    asset["sourceBandDescriptions"] = descriptions
    module = dict(
        id="degradation",
        title="Land degradation",
        question="Where do productivity, land-cover and soil-carbon indicators deteriorate?",
        status="available",
        sources=[sid, "glcfcs"],
        method=methods,
        limitations=[
            "The three upstream subindicators are published model outputs. The browser recalculates their combination and area statistics; it does not rerun the publisher’s global NDVI or SOC model.",
            "Four baseline cells differed from the provider when rounded SOC=-10% was classified as degraded. Values exactly ±10% are now marked uncertain, retaining the original percentage and publisher result for inspection.",
            "SOC is modelled from land-cover change with stock-change factors; it is not measured soil-carbon loss. Local management, climate and soil samples need validation.",
            "The dataset record labels latest land-cover/SOC bands 2015–2022, whereas embedded TIFF descriptions say 2015–2023. The UI follows the published record and retains both labels in provenance. Confirm this discrepancy before formal reporting.",
            "A known negative component is retained as a conservative degradation flag even if another is missing. Such pixels are distinguishable using component completeness and are excluded from the publisher-agreement test.",
            "Fixed 2022 open-water exclusion and source differences mean percentages are a Ganjam screening estimate, not official national SDG statistics.",
        ],
        fieldChecks=[
            "Which mapped declines coincide with soil erosion, loss of cover, crop changes or restoration histories?",
            "Can soil sampling and management histories corroborate the modelled SOC change?",
            "Are the provider’s transition rules and water exclusions appropriate for Ganjam?",
        ],
        layers=layers,
        missing=[],
    )
    update_catalog(asset, module, source, reference)
    (OUT / "degradation-provider-validation.json").write_text(
        json.dumps(validation, indent=2) + "\n"
    )
    print("Provider comparison:", validation, flush=True)
    if any(v["mismatchedPixels"] for v in validation):
        raise ValueError("Provider mismatch requires investigation; do not claim agreement")


if __name__ == "__main__":
    main()
