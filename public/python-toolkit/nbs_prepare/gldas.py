"""Authenticated native-grid GLDAS subsets; bounded HTTP I/O, serial NetCDF reads."""

from __future__ import annotations

import hashlib
import json
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

import numpy as np
import requests
from netCDF4 import Dataset

from .core import atomic, json_bytes, sha
from .sources import DownloadBudgetExceeded, earthdata_login, granule_date, nc_grid


class GldasDownloadBudgetExceeded(DownloadBudgetExceeded):
    code = "gldas_download_budget"


def native_window(bounds):
    """Inclusive DAP indices for all intersecting 0.25° cells, south to north."""
    west, south, east, north = bounds
    x0, x1 = max(0, math.floor((west + 180) * 4)), min(1439, math.ceil((east + 180) * 4) - 1)
    y0, y1 = max(0, math.floor((south + 60) * 4)), min(599, math.ceil((north + 60) * 4) - 1)
    if x0 > x1 or y0 > y1:
        raise ValueError("The study area is outside the GLDAS latitude coverage.")
    return y0, y1, x0, x1


def read_daily(path, day, window):
    """Reject a wrong date/grid/product response before using its values."""
    y0, y1, x0, x1 = window
    with Dataset(path) as ds:
        if set(ds.variables) != {"time", "lat", "lon", "GWS_tavg"}:
            raise ValueError("Unexpected GLDAS subset variables.")
        if ds["GWS_tavg"].dimensions != ("time", "lat", "lon"):
            raise ValueError("Unexpected GLDAS subset dimensions.")
        if not np.array_equal(ds["lat"][:], -59.875 + np.arange(y0, y1 + 1) * 0.25) or not np.array_equal(
            ds["lon"][:], -179.875 + np.arange(x0, x1 + 1) * 0.25
        ):
            raise ValueError("The GLDAS native grid changed; source review required.")
    values, dates, transform, units = nc_grid(path, "GWS_tavg")
    if len(values) != 1 or len(dates) != 1 or (dates[0].year, dates[0].month, dates[0].day) != (day.year, day.month, day.day):
        raise ValueError("GLDAS subset acquisition date does not match its daily granule.")
    if units not in ["kg m-2", "mm", "kg/m^2", "kg/m2"]:
        raise ValueError("Unrecognised GLDAS storage unit.")
    return values[0], transform


class GldasReader:
    """Four independent HTTP sessions. HDF5/netCDF is only opened by the caller."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.window = native_window(ctx.aoi.bounds)
        self.raw = ctx.cache / "gldas-subsets"
        self.raw.mkdir(exist_ok=True)
        self.lock = threading.Lock()
        self.local = threading.local()
        self.sessions = []
        self.pool = ThreadPoolExecutor(max_workers=4)

    def __enter__(self):
        earthdata_login(self.ctx)
        return self

    def __exit__(self, *args):
        self.pool.shutdown(wait=True, cancel_futures=True)
        for session in self.sessions:
            session.close()

    def paths(self, items):
        # A month contains at most 31 files, bounding both the queue and memory.
        if len(items) > 31:
            raise ValueError("Unexpected GLDAS daily inventory size.")
        return self.pool.map(self.download, items)

    def download(self, granule):
        identifier = granule["umm"]["GranuleUR"]
        day = granule_date(granule)
        if not identifier.endswith(f"GLDAS_CLSM025_DA1_D.A{day:%Y%m%d}.022.nc4"):
            raise ValueError("Unexpected GLDAS product, version or daily identifier.")
        links = list(dict.fromkeys(r["URL"] for r in granule["umm"].get("RelatedUrls", []) if r.get("Subtype") == "OPENDAP DATA"))
        if len(links) != 1:
            raise ValueError("NASA did not identify one GLDAS subset endpoint.")
        url = urlsplit(links[0])
        if url.scheme != "https" or url.netloc != "opendap.earthdata.nasa.gov" or not url.path.startswith("/collections/C1700900796-GES_DISC/granules/") or url.query or url.fragment:
            raise ValueError("The GLDAS subset endpoint changed; source review required.")
        key = sha(json_bytes(["gldas-native-v1", identifier, self.window]))
        path, meta = self.raw / (key + ".nc4"), self.raw / (key + ".json")
        if path.is_file() and meta.is_file():
            try:
                record = json.loads(meta.read_text())
                if path.stat().st_size == record["bytes"] and sha(path.read_bytes()) == record["sha256"]:
                    return path
            except (ValueError, KeyError, OSError):
                pass
        if not hasattr(self.local, "session"):
            self.local.session = self.ctx.earthdata_auth.get_session()
            with self.lock:
                self.sessions.append(self.local.session)
        y0, y1, x0, x1 = self.window
        ce = f"/GWS_tavg[0:1:0][{y0}:1:{y1}][{x0}:1:{x1}];/lat[{y0}:1:{y1}];/lon[{x0}:1:{x1}];/time[0:1:0]"
        maximum = max(1024**2, (y1 - y0 + 1) * (x1 - x0 + 1) * 8 + 65536)
        part = path.with_suffix(".part")
        for attempt in range(3):
            try:
                with self.local.session.get(links[0] + ".dap.nc4", params={"dap4.ce": ce}, stream=True, timeout=(20, 90)) as response:
                    # Do not put provider response bodies or signed redirect URLs in logs.
                    if response.status_code in [429, 500, 502, 503, 504]:
                        raise requests.ConnectionError("NASA subset service temporarily unavailable")
                    if response.status_code != 200:
                        raise ValueError(f"NASA GLDAS subset request returned HTTP {response.status_code}.")
                    size, digest = 0, hashlib.sha256()
                    with part.open("wb") as f:
                        for chunk in response.iter_content(65536):
                            with self.lock:
                                self.ctx.network_bytes += len(chunk)
                                if self.ctx.network_bytes > self.ctx.config["maxDownloadGB"] * 1e9:
                                    raise GldasDownloadBudgetExceeded("The GLDAS regional download allowance was reached. Increase this task's allowance up to the server limit or use a smaller area.")
                            size += len(chunk)
                            if size > maximum:
                                raise ValueError("The GLDAS subset is larger than its expected native window.")
                            f.write(chunk)
                            digest.update(chunk)
                    with part.open("rb") as f:
                        if f.read(8) != b"\x89HDF\r\n\x1a\n":
                            raise ValueError("NASA did not return a NetCDF4 regional subset.")
                    part.replace(path)
                    atomic(meta, json_bytes(dict(granule=identifier, date=day.isoformat(), window=self.window, bytes=size, sha256=digest.hexdigest())))
                    return path
            except (requests.RequestException, OSError):
                if attempt == 2:
                    raise RuntimeError("NASA GLDAS regional download failed after three attempts.") from None
                time.sleep(attempt + 1)
            finally:
                part.unlink(missing_ok=True)
