"""Native source integrity and bounded acquisition, without external accounts."""

import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from netCDF4 import Dataset
from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "localprep"))
from nbs_prepare.gldas import GldasDownloadBudgetExceeded, GldasReader, native_window, read_daily


def test_native_window_keeps_edge_cells_and_clips_source_coverage():
    assert native_window((85.75, 20.15, 85.95, 20.35)) == (320, 321, 1063, 1063)
    assert native_window((-180, -60, -179.75, -59.75)) == (0, 0, 0, 0)
    assert native_window((-180, -65, -179.75, -59.75)) == (0, 0, 0, 0)
    assert native_window((179.75, 89.75, 180, 90)) == (599, 599, 1439, 1439)
    with pytest.raises(ValueError, match="latitude coverage"):
        native_window((1, -70, 2, -60))


def make_file(path):
    with Dataset(path, "w") as ds:
        for key, values in {"time": [0], "lat": [20.125, 20.375], "lon": [85.875]}.items():
            ds.createDimension(key, len(values))
            v = ds.createVariable(key, "f8", (key,))
            v[:] = values
            if key == "time":
                v.units = "days since 2020-02-29 00:00:00"
        v = ds.createVariable("GWS_tavg", "f4", ("time", "lat", "lon"), fill_value=-9999)
        v.units = "mm"
        v[:] = np.array([5, -9999], dtype="float32").reshape(1, 2, 1)


def test_daily_reader_preserves_missing_cells_native_grid_and_leap_day(tmp_path):
    path = tmp_path / "daily.nc4"
    make_file(path)
    values, transform = read_daily(path, date(2020, 2, 29), (320, 321, 1063, 1063))
    np.testing.assert_array_equal(values, [[np.nan], [5]])
    assert (transform.c, transform.f, transform.a, transform.e) == (85.75, 20.5, .25, -.25)
    with pytest.raises(ValueError, match="acquisition date"):
        read_daily(path, date(2020, 3, 1), (320, 321, 1063, 1063))
    with Dataset(path, "a") as ds:
        ds["GWS_tavg"].units = "m"
    with pytest.raises(ValueError, match="storage unit"):
        read_daily(path, date(2020, 2, 29), (320, 321, 1063, 1063))
    with Dataset(path, "a") as ds:
        ds["lat"][0] = 20.15
    with pytest.raises(ValueError, match="native grid"):
        read_daily(path, date(2020, 2, 29), (320, 321, 1063, 1063))


def granule(day):
    return {"umm": {"GranuleUR": f"GLDAS_CLSM025_DA1_D.A202002{day:02}.022.nc4",
        "TemporalExtent": {"SingleDateTime": f"2020-02-{day:02}T00:00:00Z"},
        "RelatedUrls": [{"Subtype": "OPENDAP DATA", "URL": f"https://opendap.earthdata.nasa.gov/collections/C1700900796-GES_DISC/granules/fixture{day}"}]}}


def fake_context(tmp_path, monkeypatch, payload):
    class Response:
        status_code = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def iter_content(self, *args):
            yield payload

    class Session:
        def get(self, *args, **kwargs):
            return Response()

        def close(self):
            pass

    ctx = SimpleNamespace(aoi=box(85.75, 20.15, 85.95, 20.35), cache=tmp_path, network_bytes=0,
        config={"maxDownloadGB": 1}, earthdata_auth=SimpleNamespace(get_session=Session))
    monkeypatch.setattr("nbs_prepare.gldas.earthdata_login", lambda _: None)
    return ctx


def test_parallel_streams_count_bytes_and_verify_cached_content(tmp_path, monkeypatch):
    payload = b"\x89HDF\r\n\x1a\n" + b"fixture" * 100
    ctx = fake_context(tmp_path, monkeypatch, payload)
    items = [granule(day) for day in range(1, 9)]
    with GldasReader(ctx) as reader:
        paths = list(reader.paths(items))
        assert len(set(paths)) == 8
        assert ctx.network_bytes == len(payload) * 8
        assert len(reader.sessions) <= 4
        assert list(reader.paths(items)) == paths
        assert ctx.network_bytes == len(payload) * 8
        paths[0].write_bytes(b"corrupt")
        list(reader.paths(items))
        assert paths[0].read_bytes() == payload
        assert ctx.network_bytes == len(payload) * 9


def test_budget_stops_download_and_never_publishes_partial_cache(tmp_path, monkeypatch):
    ctx = fake_context(tmp_path, monkeypatch, b"\x89HDF\r\n\x1a\n" + b"x" * 100)
    ctx.config["maxDownloadGB"] = 1e-9
    with GldasReader(ctx) as reader, pytest.raises(GldasDownloadBudgetExceeded):
        list(reader.paths([granule(1)]))
    assert not list(tmp_path.rglob("*.nc4"))
    assert not list(tmp_path.rglob("*.part"))


def test_wrong_endpoint_or_non_netcdf_is_rejected(tmp_path, monkeypatch):
    ctx = fake_context(tmp_path, monkeypatch, b"<html>sign in</html>")
    with GldasReader(ctx) as reader:
        with pytest.raises(ValueError, match="NetCDF4"):
            list(reader.paths([granule(1)]))
        bad = granule(2)
        bad["umm"]["RelatedUrls"][0]["URL"] = "https://untrusted.example/fixture"
        with pytest.raises(ValueError, match="endpoint changed"):
            list(reader.paths([bad]))
    assert not list(tmp_path.rglob("*.nc4"))
