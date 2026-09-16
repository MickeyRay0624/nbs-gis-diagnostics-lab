"""Public MODIS seasonal vegetation-health screening, explicitly not FAO ASIS."""

import hashlib
import json
import warnings
import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling
from step2_package import CACHE, OUT, area_weights, identity, update_catalog, write_asset


def vegetation_health(ndvi, lst, min_years=15):
    """Same-season min/max climatology; flat/insufficient series remain unknown."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        nmin, nmax = np.nanmin(ndvi, axis=0), np.nanmax(ndvi, axis=0)
        tmin, tmax = np.nanmin(lst, axis=0), np.nanmax(lst, axis=0)
    good = (
        (np.isfinite(ndvi).sum(0) >= min_years)
        & (np.isfinite(lst).sum(0) >= min_years)
        & ((nmax - nmin) > 1e-6)
        & ((tmax - tmin) > 1e-6)
    )
    vci = np.full(ndvi.shape, np.nan)
    tci = np.full(lst.shape, np.nan)
    np.divide(100 * (ndvi - nmin), nmax - nmin, out=vci, where=good)
    np.divide(100 * (tmax - lst), tmax - tmin, out=tci, where=good)
    return np.clip((vci + tci) / 2, 0, 100).astype("float32")


def main():
    series = []
    hashes = {}
    for year in range(2001, 2024):
        path = CACHE / f"modisqa-{year}.tif"
        hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        with rasterio.open(path) as s:
            if s.count != 8 or s.crs.to_epsg() != 6933:
                raise ValueError("Expected eight MODIS value/coverage bands in equal-area CRS")
            d = s.read().astype("float64")
            d[d == -9999] = np.nan
            if series and (s.transform != transform or s.shape != series[0].shape[1:]):
                raise ValueError("MODIS grids differ")
            transform = s.transform
            series.append(d)
    quality = np.stack(series)
    shape = quality.shape[-2:]
    raw = quality[:, [0, 2, 4, 6]].copy()
    # Minimum 30% of NDVI composites and 20% of LST composites in a season.
    # Monsoon cloud gaps make 50% LST availability unattainable in this AOI.
    for b, minimum in enumerate([30, 20, 30, 20]):
        raw[:, b][quality[:, b * 2 + 1] < minimum] = np.nan
    # Aggregate fine-grid crop area, including exact AOI boundary intersections.
    with rasterio.open(CACHE / "glcfcs-2002-2012-2022.tif") as s:
        fine = area_weights(s.transform, s.width, s.height, 6933)
        crop = np.isin(s.read(3), [10, 11, 12, 20])
        weights = np.zeros(shape, dtype="float32")
        reproject(
            np.where(crop, fine, 0).astype("float32"),
            weights,
            src_transform=s.transform,
            src_crs=s.crs,
            dst_transform=transform,
            dst_crs=6933,
            resampling=Resampling.sum,
        )
    kh = vegetation_health(raw[:, 0], raw[:, 1])
    ra = vegetation_health(raw[:, 2], raw[:, 3])
    annual = (kh + ra) / 2
    arrays = [kh[12], kh[22], ra[12], ra[22], annual[12], annual[22]]
    names = [
        "Kharif 2013 VHI",
        "Kharif 2023 VHI",
        "Rabi 2013–2014 VHI",
        "Rabi 2023–2024 VHI",
        "Two-season 2013 VHI",
        "Two-season 2023 VHI",
    ]
    sid = "modis-vhi"
    aid = "modis-drought"
    source = dict(
        id=sid,
        name="NASA MODIS seasonal NDVI and land-surface temperature",
        url="https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD13A2",
        version="MOD13A2.061 + MOD11A2.061; crop-start years 2001–2023",
        licence="NASA LP DAAC: unrestricted use and redistribution",
        description="NDVI: doi:10.5067/MODIS/MOD13A2.061. Daytime LST: doi:10.5067/MODIS/MOD11A2.061. Seasonal means of quality-filtered 16-day NDVI and 8-day LST, nearest-neighbour extraction at 1 km. Land mask: GLC-FCS30D 2022 cropland.",
    )
    processing = [
        "Kharif = June–October; Rabi = November–March of the following year. Calendar assumptions require local review.",
        "NDVI SummaryQA≤1 (good or marginal); LST mandatory QC bits=0 and LST error bits <=1 (<=2 K). Each season requires >=30% of NDVI composites and >=20% of LST composites valid. Observation percentages are separate map outputs.",
        "VCI=100*(NDVI-min)/(max-min); TCI=100*(max-LST)/(max-min); VHI=0.5*VCI+0.5*TCI. Same-season 2001–2023 climatology, >=15 valid years per variable; zero ranges are NoData.",
        "Fixed 2022 cropland codes 10/11/12/20, including orchards. Crop area is aggregated from 50 m equal-area pixels with fractional AOI intersections. Climate pixels retain their 1 km scale.",
        "Two-season annual summary requires both seasons and gives equal weight to each. No FAO crop-stage coefficients are applied.",
    ]
    for year_index, year in [(12, 2013), (22, 2023)]:
        for band, label in [
            (1, "Kharif NDVI"),
            (3, "Kharif LST"),
            (5, "Rabi NDVI"),
            (7, "Rabi LST"),
        ]:
            arrays.append(quality[year_index, band])
            names.append(f"{label} valid observations {year}")
    asset, reference = write_asset(
        aid,
        arrays,
        names,
        transform,
        sid,
        "1 km MODIS; 30 m land cover sampled at 50 m for crop-area weights",
        processing,
        crs=6933,
        weights=weights,
    )
    asset["sourceHashes"] = hashes
    bins = [
        dict(label="VHI < 10", max=10),
        dict(label="VHI 10–<20", min=10, max=20),
        dict(label="VHI 20–<30", min=20, max=30),
        dict(label="VHI 30–<40", min=30, max=40),
        dict(label="VHI ≥40", min=40),
    ]
    layers = [
        identity(
            aid,
            i + 1,
            n,
            "index (0–100)",
            n.removesuffix(" VHI"),
            "health",
            domain=[0, 100],
            thresholds=bins,
            interpretation="Lower vegetation health indicates relative vegetation/temperature stress, not a confirmed drought event. Class area is mapped cropland area with valid MODIS observations.",
        )
        for i, n in enumerate(names[:6])
    ]
    for start, end, title in [
        (1, 2, "Kharif VHI change"),
        (3, 4, "Rabi VHI change"),
        (5, 6, "Two-season VHI change"),
    ]:
        layers.append(
            dict(
                id=f"{aid}-change-{start}",
                title=title,
                unit="index points",
                period="2023 crop-start year minus 2013",
                operation="difference",
                inputs=[dict(raster=aid, band=start), dict(raster=aid, band=end)],
                palette="diverging",
                interpretation="Negative values indicate lower vegetation health. Only jointly valid pixels enter the comparison.",
            )
        )
    for i, n in enumerate(names[6:], 7):
        layers.append(
            identity(
                aid,
                i,
                n,
                "%",
                n[-4:],
                "sequential",
                domain=[0, 100],
                interpretation="Percentage of source composites passing quality flags during this season. This quantifies observation availability, not confidence in a drought attribution.",
            )
        )
    time_series = []
    for title, values in [
        ("Kharif crop-weighted VHI", kh),
        ("Rabi crop-weighted VHI", ra),
        ("Two-season crop-weighted VHI", annual),
    ]:
        points = []
        for y, a in zip(range(2001, 2024), values):
            valid = np.isfinite(a) & (weights > 0)
            area = weights[valid].astype("float64").sum()
            points.append(
                dict(
                    date=str(y),
                    value=float(np.sum(a[valid] * weights[valid].astype("float64")) / area)
                    if area
                    else None,
                    coveragePct=float(area / weights.astype("float64").sum() * 100),
                )
            )
        time_series.append(dict(title=title, unit="VHI (0–100)", points=points))
    module = dict(
        id="drought",
        title="Drought & vegetation stress",
        question="How did seasonal vegetation health change on mapped cropland?",
        status="available",
        sources=[sid, "glcfcs"],
        method=processing,
        limitations=[
            "This is a MODIS seasonal screening alternative, not FAO ASIS or its crop-stage-weighted VHI. The ASIS asset was unavailable to the registered project.",
            "Min/max VHI is sensitive to reference years and outliers. Seasonal means do not reproduce a dekadal agricultural drought product. At least 15 of 23 seasonal years per variable must support the reference range. Clear-sky sampling can bias the monsoon signal; inspect missing area and each time-series coverage value.",
            "Vegetation and thermal stress can arise from crop choice, fallow land, pests or management. The fixed 2022 cropland mask does not establish historical cropping or irrigation.",
        ],
        fieldChecks=[
            "Are June–October and November–March appropriate for the local crops and planting dates?",
            "Do low-VHI years correspond to farmer reports, rainfall deficits or irrigation interruptions?",
        ],
        layers=layers,
        series=time_series,
        missing=[],
    )
    update_catalog(asset, module, source, reference)
    print("Prepared drought; mapped crop area km²:", weights.astype("float64").sum(), flush=True)
    print([(r["name"], r["validAreaKm2"], r["mean"]) for r in reference], flush=True)


if __name__ == "__main__":
    main()
