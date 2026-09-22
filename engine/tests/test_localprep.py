"""Portable toolkit arithmetic and raw-file readers, with no network or login."""

import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pytest
from netCDF4 import Dataset
from pyproj import Transformer
from rasterio.transform import from_origin

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "localprep"))
from nbs_prepare.core import (
    Context,
    area_weights,
    finite_mean,
    grid_for,
    identity,
    json_bytes,
    layer_values,
    read_boundary,
    sha,
)
from nbs_prepare.modules import (
    carbon_classes,
    composite_dates,
    daily_index,
    productivity_classes,
    season_dates,
    vegetation_health,
)
from nbs_prepare.sources import (
    DownloadBudgetExceeded,
    check_modis_budget,
    download_granule,
    modis_array,
    nc_grid,
)


def test_modis_preflight_counts_unique_payloads_against_remaining_budget(tmp_path):
    ctx = make_context(tmp_path)
    granule = {"umm": {"GranuleUR": "one-tile", "DataGranule": {
        "ArchiveAndDistributionInformation": [{"Size": 600, "SizeUnit": "MB"}]
    }}}
    check_modis_budget(ctx, [granule, granule])
    ctx.network_bytes = 400_000_000
    with pytest.raises(DownloadBudgetExceeded, match="at least 15 reference years"):
        check_modis_budget(ctx, [granule])


def test_nasa_download_ignores_browse_files_and_reuses_verified_cache(tmp_path, monkeypatch):
    from types import SimpleNamespace

    import nbs_prepare.sources as sources

    class Granule(dict):
        def data_links(self):
            return [
                "https://data.lpdaac.earthdatacloud.nasa.gov/MOD11A2.fixture.hdf",
                "https://data.lpdaac.earthdatacloud.nasa.gov/MOD11A2.fixture.hdf.xml",
                "https://data.lpdaac.earthdatacloud.nasa.gov/MOD11A2.fixture.jpg",
            ]

    calls = []

    def download(links, directory, threads):
        calls.append(links)
        path = Path(directory) / "MOD11A2.fixture.hdf"
        path.write_bytes(b"scientific payload")
        return [str(path)]

    monkeypatch.setattr(sources, "earthdata_login", lambda ctx: SimpleNamespace(download=download))
    ctx = make_context(tmp_path)
    granule = Granule(umm={"GranuleUR": "MOD11A2.fixture"})
    result = download_granule(ctx, granule)
    assert calls == [["https://data.lpdaac.earthdatacloud.nasa.gov/MOD11A2.fixture.hdf"]]
    assert result.read_bytes() == b"scientific payload"
    assert ctx.network_bytes == 18
    assert download_granule(ctx, granule) == result
    assert len(calls) == 1
    result.write_bytes(b"interrupted or corrupt cache")
    download_granule(ctx, granule)
    assert len(calls) == 2


def config():
    return dict(
        schema="nbs-local-job/v1",
        name="Analytical test",
        modules=["flood", "degradation"],
        boundarySha256="0" * 64,
        groundwater=dict(baseline=[2003, 2013], monitoring=[2014, 2023]),
        drought=dict(
            reference=[2001, 2023],
            minimumYears=15,
            compare=[2013, 2023],
            seasons=[dict(name="A", start=6, end=10), dict(name="B", start=11, end=3)],
        ),
        climate=dict(
            baseline=[1991, 2020],
            future=[2041, 2070],
            models=["ACCESS-CM2"],
            scenarios=["ssp245"],
            metrics=["hot"],
            thresholds=dict(hot=35, warm=25, rain=20, dry=1),
        ),
        flood=dict(returnPeriods=[10]),
        landMask="all-land",
        maxDownloadGB=1,
    )


def make_context(tmp):
    b = json_bytes(
        dict(
            type="Polygon",
            coordinates=[
                [[85.75, 20.15], [85.95, 20.15], [85.95, 20.35], [85.75, 20.35], [85.75, 20.15]]
            ],
        )
    )
    (tmp / "aoi.geojson").write_bytes(b)
    c = config()
    c["boundarySha256"] = sha(b)
    return Context(tmp, c)


def test_aoi_area_and_partial_cell_conservation(tmp_path):
    ctx = make_context(tmp_path)
    t, shape = grid_for(ctx.aoi, 0.25)
    weights = area_weights(ctx.aoi, ctx.area_aoi, t, shape)
    assert float(weights.sum()) == pytest.approx(ctx.area_aoi.area / 1e6, rel=1e-7)
    assert ctx.area_aoi.area / 1e6 == pytest.approx(462.672157711, abs=0.01)
    with pytest.raises(ValueError, match="valid WGS84"):
        read_boundary(
            json_bytes(dict(type="Polygon", coordinates=[[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]]))
        )


def test_daily_threshold_counts_dry_runs_and_missing_days():
    values = np.array([0, 0, 1, 0, 0, 0, 20, 21], dtype="float32")[:, None, None]
    thresholds = dict(hot=20, warm=20, rain=20, dry=1)
    assert daily_index(values, "dry", thresholds).item() == 3
    assert daily_index(values, "rain", thresholds).item() == 2
    assert daily_index(values, "hot", thresholds).item() == 1
    values[0] = np.nan
    assert np.isnan(daily_index(values, "rain", thresholds)).all()
    assert np.isnan(finite_mean(values, 1)).all()
    assert finite_mean(values, 0.8).item() == pytest.approx(6)


def test_seasons_reset_composite_calendar_and_vhi_minimum():
    first, end = season_dates(2023, dict(start=11, end=3))
    assert (first, end) == (date(2023, 11, 1), date(2024, 4, 1))
    dates = composite_dates(first, end, 16)
    assert date(2024, 1, 1) in dates and all(first <= d < end for d in dates)
    n = np.arange(15, dtype="float32")[:, None, None]
    t = 30 - n
    vhi = vegetation_health(n, t, 15)
    assert vhi[0].item() == 0 and vhi[-1].item() == 100
    n[0] = np.nan
    assert np.isnan(vegetation_health(n, t, 15)).all()
    assert np.isnan(vegetation_health(np.ones_like(n), t, 15)).all()


def test_conservative_component_rules():
    np.testing.assert_array_equal(
        productivity_classes(np.array([1, 2, 3, 4, 5, np.nan])), [-1, -1, 0, 0, 1, np.nan]
    )
    np.testing.assert_array_equal(
        carbon_classes(np.array([-11, -10, -9, 9, 10, 11, np.nan])),
        [-1, np.nan, 0, 0, np.nan, 1, np.nan],
    )
    spec = {"operation": "one-out-all-out", "inputs": [{"band": 1}, {"band": 2}, {"band": 3}]}
    values = np.array([[-1, 0, 1], [np.nan, np.nan, 0], [0, 1, 0]])
    np.testing.assert_array_equal(layer_values(spec, values), [-1, np.nan, 1])


def test_cache_restart_and_partial_result_not_complete(tmp_path):
    ctx = make_context(tmp_path)
    calls = []
    a = ctx.cached_array("example", lambda: calls.append(1) or np.ones((1, 1)))
    ctx.cached_array("example", lambda: pytest.fail("must use cache"))
    assert len(calls) == 1 and a.item() == 1
    ctx.write(
        "flood",
        [np.array([[2]], dtype="float32")],
        ["Depth"],
        from_origin(85.75, 20.4, 0.25, 0.25),
        4326,
        np.array([[3]], dtype="float32"),
        dict(
            id="fixture",
            name="Fixture",
            url="https://example.org",
            version="test",
            licence="Test",
            description="Synthetic test only",
            resolution="Synthetic",
        ),
        [identity("flood", 1, "Depth", "m", "Test")],
        ["Synthetic test"],
        ["Not environmental evidence"],
    )
    ctx.finish()
    state = json.loads((tmp_path / "results/validation.json").read_text())
    assert state["complete"] is False and state["available"] == ["flood"]
    assert state["statistics"][0]["mean"] == 2
    import zipfile

    with zipfile.ZipFile(tmp_path / "results.zip") as z:
        assert set(z.namelist()) == {"catalog.json", "aoi.geojson", "flood.tif"}


def test_netcdf_reorients_axes_preserves_units_and_fill(tmp_path):
    p = tmp_path / "source.nc"
    with Dataset(p, "w") as ds:
        for name, n in [("time", 1), ("lat", 2), ("lon", 2)]:
            ds.createDimension(name, n)
        ds.createVariable("lat", "f4", ("lat",))[:] = [20.125, 20.375]
        ds.createVariable("lon", "f4", ("lon",))[:] = [85.875, 85.625]
        time = ds.createVariable("time", "f8", ("time",))
        time.units = "days since 2000-01-01"
        time[:] = [0]
        v = ds.createVariable("GWS_tavg", "f4", ("time", "lat", "lon"), fill_value=-9999)
        v.units = "kg m-2"
        v[:] = [[[1, 2], [3, -9999]]]
    values, dates, t, units = nc_grid(p, "GWS_tavg")
    np.testing.assert_array_equal(values, [[[np.nan, 3], [2, 1]]])
    assert (t.c, t.f, t.a, t.e) == (85.5, 20.5, 0.25, -0.25)
    assert units == "kg m-2" and dates[0].year == 2000


def test_modis_native_hdf_quality_scale_and_georeferencing(tmp_path):
    from pyhdf.SD import SD, SDC

    p = tmp_path / "modis.hdf"
    h = SD(str(p), SDC.WRITE | SDC.CREATE)
    h.attr("StructMetadata.0").set(
        SDC.CHAR8, "UpperLeftPointMtrs=(0,1000)\nLowerRightMtrs=(2000,-1000)"
    )
    s = h.create("1 km 16 days NDVI", SDC.INT16, (2, 2))
    s[:] = np.array([[5000, 2000], [3000, 4000]], dtype="int16")
    s.endaccess()
    q = h.create("1 km 16 days pixel reliability", SDC.INT16, (2, 2))
    q[:] = np.array([[0, 3], [1, -1]], dtype="int16")
    q.endaccess()
    h.end()
    transform = Transformer.from_crs(
        "+proj=sinu +R=6371007.181 +units=m +no_defs", 6933, always_xy=True
    )
    x, y = transform.transform(500, 500)
    array = modis_array(p, "ndvi", from_origin(x - 50, y + 50, 100, 100), (1, 1))
    assert array.item() == pytest.approx(0.5)
    x, y = transform.transform(1500, 500)
    assert np.isnan(modis_array(p, "ndvi", from_origin(x - 50, y + 50, 100, 100), (1, 1))).all()
