from nbs_gis.config import load_config
from nbs_gis.preflight import run_preflight


def test_preflight_ready_for_valid_fixture(fixture_project):
    report = run_preflight(load_config(fixture_project()))

    assert report["status"] == "ready"
    assert report["summary"]["errors"] == 0
    assert report["raster_metadata"]["2002"]["intersects_aoi"] is True


def test_preflight_blocks_missing_raster(fixture_project):
    report = run_preflight(load_config(fixture_project(missing_raster=True)))

    assert report["status"] == "blocked"
    assert any(item["id"] == "raster-2012-file" for item in report["checks"])
