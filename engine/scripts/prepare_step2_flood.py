"""Crop official JRC public GeoTIFFs with HTTP range reads; no account required."""

import concurrent.futures
import json
import math

import numpy as np
import rasterio
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject
from rasterio.windows import from_bounds

from step2_package import AOI, CACHE, OUT, identity, update_catalog, write_asset

BASE = "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/CEMS-GLOFAS/flood_hazard/"
TILES = ["ID192_N30_E80", "ID193_N20_E80"]
CELLSIZE = 1 / 1200
west, south, east, north = AOI.bounds
left, top = math.floor(west / CELLSIZE) * CELLSIZE, math.ceil(north / CELLSIZE) * CELLSIZE
WIDTH, HEIGHT = math.ceil((east - left) / CELLSIZE), math.ceil((top - south) / CELLSIZE)
TRANSFORM = from_origin(left, top, CELLSIZE, CELLSIZE)
CACHE.mkdir(parents=True, exist_ok=True)


def crop(item):
    key, url = item
    path = CACHE / f"{key}.tif"
    if path.exists():
        with rasterio.open(path) as src:
            return key, src.read(1)
    result = np.full((HEIGHT, WIDTH), np.nan, dtype="float32")
    with rasterio.Env(
        GDAL_HTTP_TIMEOUT="45",
        GDAL_HTTP_MAX_RETRY="2",
        GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
        CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
    ):
        with rasterio.open("/vsicurl/" + url) as src:
            b = src.bounds
            extent = [
                max(west - CELLSIZE, b.left),
                max(south - CELLSIZE, b.bottom),
                min(east + CELLSIZE, b.right),
                min(north + CELLSIZE, b.top),
            ]
            window = from_bounds(*extent, transform=src.transform).round_offsets().round_lengths()
            data = src.read(1, window=window, masked=True).astype("float32").filled(np.nan)
            reproject(
                data,
                result,
                src_transform=src.window_transform(window),
                src_crs=src.crs,
                dst_transform=TRANSFORM,
                dst_crs="EPSG:4326",
                src_nodata=np.nan,
                dst_nodata=np.nan,
                resampling=Resampling.nearest,
            )
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=WIDTH,
        height=HEIGHT,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=TRANSFORM,
        nodata=np.nan,
        compress="deflate",
    ) as dst:
        dst.write(result, 1)
        dst.update_tags(source_url=url)
    print("Cropped", key, "valid cells", np.isfinite(result).sum(), flush=True)
    return key, result


jobs = []
for tile in TILES:
    for rp in [10, 100, 500]:
        jobs.append((f"{tile}-rp{rp}", f"{BASE}RP{rp}/{tile}_RP{rp}_depth.tif"))
    jobs.extend(
        [
            (f"{tile}-water", f"{BASE}Permanent_WaterBodies/{tile}_permanent_water.tif"),
            (f"{tile}-flag", f"{BASE}Spurious_Depths/{tile}_spurious_depth_areas.tif"),
        ]
    )
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    data = dict(pool.map(crop, jobs))

water = np.any([np.isfinite(data[f"{t}-water"]) & (data[f"{t}-water"] > 0) for t in TILES], axis=0)
flag = np.any([np.isfinite(data[f"{t}-flag"]) & (data[f"{t}-flag"] > 0) for t in TILES], axis=0)
arrays = []
for rp in [10, 100, 500]:
    depth = np.fmax(*[data[f"{t}-rp{rp}"] for t in TILES])
    depth[(depth <= 0) | water | flag] = np.nan
    arrays.append(depth)
arrays += [water.astype("float32"), flag.astype("float32")]
names = [
    "RP10 depth m",
    "RP100 depth m",
    "RP500 depth m",
    "Permanent water flag",
    "Spurious depth flag",
]
asset, reference = write_asset(
    "jrc-flood",
    arrays,
    names,
    TRANSFORM,
    "jrc-flood",
    "3 arc seconds (approximately 90 m)",
    "Official JRC v2.1.2 depth and flag tiles. Nearest-neighbour alignment to a common 3-arc-second WGS84 grid; no spatial downscaling. Positive mapped depths only; permanent water and provider-flagged spurious depths excluded. Dry / unmodelled NoData remains unknown. AOI intersections weighted in EPSG:6933.",
)
catalog = json.loads((OUT / "catalog.json").read_text())
module = next(m for m in catalog["modules"] if m["id"] == "flood")
module.update(
    status="available",
    sources=["jrc-flood"],
    missing=[],
    layers=[
        identity(
            "jrc-flood",
            i + 1,
            f"River flood depth · {rp}-year return period",
            "m",
            "JRC v2.1.2 · static hazard",
            "water",
            domain=[0, 5],
            thresholds=[
                dict(label="0–<1 m", min=0, max=1),
                dict(label="1–<3 m", min=1, max=3),
                dict(label="3–<10 m", min=3, max=10),
                dict(label="10 m or deeper", min=10),
            ],
            interpretation="Valid area is mapped positive inundation depth after quality exclusions. Transparent areas are outside mapped inundation or lack reliable coverage; they do not establish zero flood risk. The colour ramp saturates at 5 m; numeric exports retain full depths.",
        )
        for i, rp in enumerate([10, 100, 500])
    ],
)
for band, title in [(4, "Permanent water flag"), (5, "Spurious depth flag")]:
    module["layers"].append(
        identity(
            "jrc-flood",
            band,
            title,
            "class",
            "JRC v2.1.2 · quality flags",
            "water",
            categories=[
                dict(value=0, label="Not flagged", color="#e5e8dd"),
                dict(value=1, label="Flagged", color="#b94e39"),
            ],
            interpretation="A provider quality / exclusion flag, not a flood probability or evidence that unflagged land is hazard-free.",
        )
    )
module["method"] += [
    asset["processing"],
    "Depth distributions use mapped valid inundation as their denominator. Coverage uses the entire district AOI. Both areas are exported.",
]
module["limitations"] += [
    "NoData in the raw depth product does not distinguish dry cells from unmodelled areas. It is not replaced with zero."
]
source = dict(
    id="jrc-flood",
    name="JRC / CEMS-GloFAS global river flood hazard",
    url=BASE + "README.txt",
    version="2.1.2 · 2026-01-12",
    licence="Free and open Copernicus product; attribution required",
    description="LISFLOOD / LISFLOOD-FP modelled riverine depths. "
    + "; ".join(url for _, url in jobs),
)
module["method"] = list(dict.fromkeys(module["method"]))
module["limitations"] = list(dict.fromkeys(module["limitations"]))
update_catalog(asset, module, source, reference)
print("Prepared flood package", asset["sha256"], reference, flush=True)
