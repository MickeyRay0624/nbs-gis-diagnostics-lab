"""Public-source readers. Every analysis is performed by the local Python process."""

from __future__ import annotations

import calendar
import math
import re
import xml.etree.ElementTree as ET
from datetime import date, timedelta

import numpy as np
import rasterio
from netCDF4 import Dataset, num2date
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject
from rasterio.windows import Window, from_bounds

from .core import area_weights, grid_for, json_bytes, sha

FLOOD = "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/CEMS-GLOFAS/flood_hazard/"
DEGRADATION = "https://storage.googleapis.com/trendsearth-public/unccd_reporting/2016-2023/TrendsEarth_SDG15.3.1_2000-2023_Trends.Earth.tif"
CLIMATE = "https://ds.nccs.nasa.gov/thredds/"
WORLD_COVER = dict(
    id="worldcover-mask",
    name="ESA WorldCover 2021 land mask",
    version="2021 v200",
    licence="CC BY 4.0",
    url="https://esa-worldcover.org/en/data-access",
    description="10 m source, sampled by nearest neighbour on a documented equal-area grid for fixed cropland / water masks.",
    resolution="10 m source",
)


class DownloadBudgetExceeded(ValueError):
    """A public-safe resource error containing no account or source URL details."""

    code = "modis_download_budget"


def granule_bytes(granule):
    # CMR providers commonly report binary megabytes using the label MB.
    factors = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3}
    return sum(
        float(item.get("Size", 0)) * factors.get(item.get("SizeUnit", "MB").upper(), 0)
        for item in granule["umm"].get("DataGranule", {}).get("ArchiveAndDistributionInformation", [])
    )


def check_modis_budget(ctx, items):
    unique = {g["umm"]["GranuleUR"]: g for g in items}
    estimate = sum(granule_bytes(g) for g in unique.values())
    budget = ctx.config["maxDownloadGB"] * 1e9
    if ctx.network_bytes + estimate > budget:
        raise DownloadBudgetExceeded(
            f"The selected MODIS tiles require approximately {estimate / 1e9:.2f} GB, "
            f"exceeding the remaining {(budget - ctx.network_bytes) / 1e9:.2f} GB download allowance. "
            "Submit each growing season separately or choose a smaller area. Keep at least 15 reference years. "
            "No MODIS data files were downloaded."
        )
    ctx.log(f"MODIS source check: {len(unique)} files, approximately {estimate / 1e9:.2f} GB.")


def crop_cog(ctx, url, bands, transform, shape, crs=4326, factor=1):
    """Range-read only the AOI source window, then align without inventing resolution."""
    key = json_bytes([url, bands, list(transform), shape, crs, factor]).decode()

    def fetch():
        ctx.log("Reading a public raster window…")
        result = np.full((len(bands), *shape), np.nan, dtype="float32")
        with (
            rasterio.Env(
                GDAL_HTTP_TIMEOUT="90",
                GDAL_HTTP_MAX_RETRY="2",
                GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
                CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
            ),
            rasterio.open("/vsicurl/" + url) as src,
        ):
            if src.crs.to_epsg() != 4326:
                raise ValueError("The public raster CRS changed; source review required.")
            west, south, east, north = ctx.aoi.bounds
            b = src.bounds
            extent = (
                max(west - src.res[0], b.left),
                max(south - src.res[1], b.bottom),
                min(east + src.res[0], b.right),
                min(north + src.res[1], b.top),
            )
            if extent[0] >= extent[2] or extent[1] >= extent[3]:
                return result
            w = from_bounds(*extent, src.transform)
            window = Window(
                math.floor(w.col_off),
                math.floor(w.row_off),
                math.ceil(w.width) + 1,
                math.ceil(w.height) + 1,
            ).intersection(Window(0, 0, src.width, src.height))
            height, width = math.ceil(window.height / factor), math.ceil(window.width / factor)
            if height * width * len(bands) > 40_000_000:
                raise ValueError("Source window is too large. Choose a smaller boundary.")
            data = (
                src.read(
                    bands,
                    window=window,
                    out_shape=(len(bands), height, width),
                    resampling=Resampling.nearest,
                    masked=True,
                )
                .astype("float32")
                .filled(np.nan)
            )
            source_transform = src.window_transform(window) * src.transform.scale(
                window.width / width, window.height / height
            )
            for i, array in enumerate(data):
                reproject(
                    array,
                    result[i],
                    src_transform=source_transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs=crs,
                    src_nodata=np.nan,
                    dst_nodata=np.nan,
                    resampling=Resampling.nearest,
                )
        return result

    return ctx.cached_array(key, fetch)


def mask_weights(ctx, transform, shape, crs, crop=False):
    weights = area_weights(ctx.aoi, ctx.area_aoi, transform, shape, crs)
    if ctx.config["landMask"] == "all-land":
        return weights, [], "Full AOI denominator; no crop or water mask applied."
    cell = 50
    while True:
        try:
            fine_transform, fine_shape = grid_for(ctx.aoi, cell, 6933)
            break
        except ValueError:
            cell *= 2
            if cell > 800:
                raise

    def build():
        fine = np.full(fine_shape, np.nan, dtype="float32")
        w, s, e, n = ctx.aoi.bounds
        for y in range(math.floor(s / 3) * 3, math.ceil(n / 3) * 3, 3):
            for x in range(math.floor(w / 3) * 3, math.ceil(e / 3) * 3, 3):
                tile = f"{'N' if y >= 0 else 'S'}{abs(y):02d}{'E' if x >= 0 else 'W'}{abs(x):03d}"
                url = f"https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"
                part = crop_cog(
                    ctx, url, [1], fine_transform, fine_shape, 6933, factor=max(1, cell // 10)
                )[0]
                fine[np.isfinite(part)] = part[np.isfinite(part)]
        fine_weights = area_weights(ctx.aoi, ctx.area_aoi, fine_transform, fine_shape, 6933)
        coverage = np.sum(fine_weights[np.isfinite(fine) & (fine > 0)], dtype="float64") / np.sum(
            fine_weights, dtype="float64"
        )
        if coverage < 0.95:
            raise ValueError(
                "WorldCover covers less than 95% of this AOI. Select the full-AOI denominator or use a smaller covered boundary."
            )
        # Unknown mask pixels are retained in the terrestrial denominator, not silently excluded.
        selected = fine == 40 if crop else fine != 80
        result = np.zeros(shape, dtype="float32")
        reproject(
            np.where(selected, fine_weights, 0),
            result,
            src_transform=fine_transform,
            src_crs=6933,
            dst_transform=transform,
            dst_crs=crs,
            resampling=Resampling.sum,
        )
        return np.minimum(result, weights)

    values = ctx.cached_array(f"mask-{crop}-{cell}-{list(transform)}-{shape}-{crs}", build)
    if values.sum() <= 0:
        raise ValueError("No mapped eligible land in this boundary for the selected mask.")
    text = f"Fixed ESA WorldCover 2021 v200 {'cropland (code 40)' if crop else 'non-water (exclude code 80)'} mask. 10 m source sampled at {cell} m in EPSG:6933; fractional AOI area aggregated to the analysis grid. This does not establish historical land use."
    return values, [WORLD_COVER], text


def climate_path(ctx, model, scenario, variable, year):
    directory = f"AMES/NEX/GDDP-CMIP6/{model}/{scenario}/r1i1p1f1/{variable}/"
    path = ctx.download(CLIMATE + "catalog/" + directory + "catalog.xml", f"catalog-{directory}")
    root = ET.fromstring(path.read_bytes())
    choices = [
        e.attrib["urlPath"]
        for e in root.iter()
        if "urlPath" in e.attrib and re.search(rf"_{year}(?:_v[\d.]+)?\.nc$", e.attrib["urlPath"])
    ]
    if not choices:
        raise ValueError(
            f"NASA has no {variable} file for {model}, {scenario}, {year} in this catalog."
        )

    def version(p):
        match = re.search(r"_v([\d.]+)\.nc$", p)
        return tuple(map(int, match[1].split("."))) if match else (1, 0)

    chosen = sorted(choices, key=version)[-1]
    if version(chosen) != (2, 0):
        raise ValueError("NASA NEX file version is not v2.0; review the dataset before continuing.")
    return chosen


def nc_grid(path, variable):
    """Read native regular lon/lat axes, preserving actual dates and masking fill values."""
    with Dataset(path) as ds:
        lat_key = next((k for k in ["lat", "latitude"] if k in ds.variables), None)
        lon_key = next((k for k in ["lon", "longitude"] if k in ds.variables), None)
        if not lat_key or not lon_key or variable not in ds.variables:
            raise ValueError("Unexpected NetCDF variables; source review required.")
        lat = np.asarray(ds[lat_key][:])
        lon = np.asarray(ds[lon_key][:])
        lon = (lon + 180) % 360 - 180
        yi, xi = np.argsort(-lat), np.argsort(lon)
        lat, lon = lat[yi], lon[xi]
        dy = abs(float(np.diff(lat)[0])) if len(lat) > 1 else 0.25
        dx = abs(float(np.diff(lon)[0])) if len(lon) > 1 else 0.25
        if (len(lat) > 1 and not np.allclose(np.diff(lat), -dy)) or (
            len(lon) > 1 and not np.allclose(np.diff(lon), dx)
        ):
            raise ValueError("Non-regular source grid; choose a boundary away from the date line.")
        raw = ds[variable][:].astype("float32")
        values = np.ma.filled(raw, np.nan)
        # Remove singleton non-spatial axes, while preserving the time axis.
        dims = list(ds[variable].dimensions)
        for axis in reversed(range(len(dims))):
            if dims[axis] not in [lat_key, lon_key, "time"]:
                if values.shape[axis] != 1:
                    raise ValueError("Unexpected additional NetCDF dimension.")
                values = np.take(values, 0, axis=axis)
                dims.pop(axis)
        if "time" not in dims:
            values = values[None]
            dims.insert(0, "time")
        values = np.transpose(values, [dims.index(k) for k in ["time", lat_key, lon_key]])[:, yi][
            :, :, xi
        ]
        dates = []
        if "time" in ds.variables:
            t = ds["time"]
            dates = list(
                num2date(
                    t[:],
                    t.units,
                    calendar=getattr(t, "calendar", "standard"),
                    only_use_cftime_datetimes=True,
                )
            )
        units = getattr(ds[variable], "units", "")
        return (
            values,
            dates,
            from_origin(float(lon[0] - dx / 2), float(lat[0] + dy / 2), dx, dy),
            units,
        )


def climate_daily(ctx, model, scenario, variable, year):
    file = climate_path(ctx, model, scenario, variable, year)
    w, s, e, n = ctx.aoi.bounds
    params = dict(
        var=variable,
        north=min(89.875, n + 0.25),
        south=max(-89.875, s - 0.25),
        west=w - 0.25,
        east=e + 0.25,
        horizStride=1,
        time_start=f"{year}-01-01T00:00:00Z",
        time_end=f"{year}-12-31T23:59:59Z",
        accept="netcdf3",
        addLatLon="true",
    )
    ctx.log(f"Climate: {model} / {scenario} / {year} / {variable}")
    path = ctx.download(CLIMATE + "ncss/grid/" + file, json_bytes([file, params]).decode(), params)
    with Dataset(path) as dataset:
        if str(getattr(dataset, "version", "")) != "2.0":
            raise ValueError("The climate file metadata is not version 2.0.")
        licence = getattr(dataset, "cmip6_license", "")
        if not licence:
            raise ValueError("The climate file is missing its CMIP6 licence metadata.")
        if not hasattr(ctx, "climate_licences"):
            ctx.climate_licences = {}
        ctx.climate_licences[model] = licence
    values, dates, transform, units = nc_grid(path, variable)
    calendar_name = getattr(dates[0], "calendar", "standard") if dates else "standard"
    expected_days = (
        360
        if calendar_name == "360_day"
        else 365
        if calendar_name in ["noleap", "365_day"]
        else 366
        if calendar_name in ["all_leap", "366_day"]
        else 365 + calendar.isleap(year)
    )
    if (
        len(dates) != len(values)
        or len(dates) != expected_days
        or len({(d.year, d.month, d.day) for d in dates}) != len(dates)
        or any(d.year != year for d in dates)
        or dates[0].month != 1
        or dates[0].day != 1
        or any(b - a != timedelta(days=1) for a, b in zip(dates, dates[1:], strict=False))
    ):
        raise ValueError("The climate source did not return a complete daily year.")
    if variable == "pr":
        if units.replace(" ", "") not in ["kgm-2s-1", "kg/m2/s", "kgm**-2s**-1"]:
            raise ValueError(f"Unrecognised precipitation unit: {units}")
        values *= 86400
    else:
        if units.lower() not in ["k", "kelvin"]:
            raise ValueError("Unrecognised temperature unit.")
        values -= 273.15
    return values, transform


def earthdata_login(ctx):
    import earthaccess

    if getattr(ctx, "earthdata", False):
        return earthaccess
    server = getattr(ctx, "server_mode", False)
    ctx.log(
        "Connecting to NASA with the server's configured Earthdata account."
        if server else
        "NASA Earthdata login is required for this module. Use your own free account; the password is hidden. No credentials are written to the results package."
    )
    auth = earthaccess.login(strategy="environment", persist=False) if getattr(ctx, "server_mode", False) else earthaccess.login(persist=False)
    if not auth.authenticated:
        raise ValueError(
            "Earthdata login failed. Register at urs.earthdata.nasa.gov, authorise the NASA data applications, then run again."
        )
    ctx.earthdata = True
    ctx.earthdata_auth = auth
    return earthaccess


def granules(ctx, short_name, version, start, end):
    earthaccess = earthdata_login(ctx)
    results = earthaccess.search_data(
        short_name=short_name,
        version=version,
        temporal=(start.isoformat(), end.isoformat()),
        bounding_box=ctx.aoi.bounds,
        count=-1,
    )
    if not results:
        raise ValueError(f"No {short_name} granules found for the selected region and period.")
    return results


def granule_date(granule):
    temporal = granule["umm"]["TemporalExtent"]
    text = temporal.get("RangeDateTime", {}).get("BeginningDateTime") or temporal.get(
        "SingleDateTime"
    )
    if not text:
        raise ValueError("NASA granule has no acquisition date.")
    return date.fromisoformat(text[:10])


def download_granule(ctx, granule):
    earthaccess = earthdata_login(ctx)
    raw = ctx.cache / "earthdata"
    raw.mkdir(exist_ok=True)
    # Reuse completed, checksum-verified local files. Never persist signed download URLs.
    key = sha(granule["umm"]["GranuleUR"].encode())
    meta = raw / (key + ".json")
    import json

    if meta.exists():
        m = json.loads(meta.read_text(encoding="utf-8"))
        path = raw / m["file"]
        if path.is_file() and sha(path.read_bytes()) == m["sha256"]:
            return path
    estimate = granule_bytes(granule)
    if ctx.network_bytes + estimate > ctx.config["maxDownloadGB"] * 1e9:
        raise ValueError(
            "The managed-download budget was reached. Run the same package again to continue from the cache; a file larger than the limit requires a new package with a higher limit."
        )
    # A granule may also advertise XML metadata and browse images. Download only
    # its scientific payload; those ancillary files are not additional tiles.
    from urllib.parse import urlsplit

    links = list(dict.fromkeys(
        link for link in granule.data_links()
        if urlsplit(link).path.lower().endswith((".hdf", ".nc4", ".nc"))
    ))
    if len(links) != 1:
        raise ValueError("NASA did not identify one unambiguous scientific source file.")
    paths = earthaccess.download(links, str(raw), threads=1)
    if len(paths) != 1:
        raise ValueError(
            "NASA did not return a complete source file; retry after authorising the data application."
        )
    path = paths[0]
    from pathlib import Path

    path = Path(path)
    ctx.network_bytes += path.stat().st_size
    from .core import atomic

    atomic(meta, json_bytes(dict(file=path.name, sha256=sha(path.read_bytes()))))
    if ctx.network_bytes > ctx.config["maxDownloadGB"] * 1e9:
        raise ValueError("The managed-download budget was reached. Completed files are cached.")
    return path


def modis_array(path, kind, transform, shape):
    from pyhdf.SD import SD, SDC

    hdf = SD(str(path), SDC.READ)
    try:
        metadata = hdf.attributes().get("StructMetadata.0", "")
        match = re.search(r"UpperLeftPointMtrs=\(([^,]+),([^\)]+)\)", metadata)
        lower = re.search(r"LowerRightMtrs=\(([^,]+),([^\)]+)\)", metadata)
        if not match or not lower:
            raise ValueError("MODIS HDF georeferencing is missing.")

        def read(name):
            s = hdf.select(name)
            try:
                return s[:].astype("float32")
            finally:
                s.endaccess()

        if kind == "ndvi":
            values, quality = read("1 km 16 days NDVI"), read("1 km 16 days pixel reliability")
            good = np.isin(quality, [0, 1]) & (values >= -2000) & (values <= 10000)
            values *= 0.0001
        else:
            values, quality = read("LST_Day_1km"), read("QC_Day").astype("uint8")
            good = (
                ((quality & 3) == 0)
                & (((quality >> 6) & 3) <= 1)
                & (values >= 7500)
                & (values <= 65535)
            )
            values = values * 0.02 - 273.15
        values[~good] = np.nan
        left, top = map(float, match.groups())
        right, bottom = map(float, lower.groups())
        src_transform = from_origin(
            left, top, (right - left) / values.shape[1], (top - bottom) / values.shape[0]
        )
        result = np.full(shape, np.nan, dtype="float32")
        reproject(
            values,
            result,
            src_transform=src_transform,
            src_crs="+proj=sinu +R=6371007.181 +units=m +no_defs",
            dst_transform=transform,
            dst_crs=6933,
            src_nodata=np.nan,
            dst_nodata=np.nan,
            resampling=Resampling.nearest,
        )
        return result
    finally:
        hdf.end()
