from __future__ import annotations

import csv
import json

import pytest
import rasterio

from nbs_gis.config import load_config
from nbs_gis.errors import PipelineError
from nbs_gis.pipeline import run_lulc


def test_pipeline_writes_expected_statistics_and_outputs(fixture_project):
    config = load_config(fixture_project(maps=True))
    output = run_lulc(config, "fixture-run")

    assert (output / "run_manifest.json").is_file()
    assert (output / "preflight_report.json").is_file()
    assert (output / "qa_report.json").is_file()
    assert (output / "tables/transition_2002_2012_long.csv").is_file()
    assert (output / "tables/transition_2002_2012_matrix.csv").is_file()
    assert not (output / "rasters/transition_2002_2012_long.csv").exists()
    assert (output / "maps/lulc_2002.png").is_file()
    assert (output / "maps/change_2002_2012.png").is_file()

    with (output / "tables/class_area_by_year.csv").open(encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    counts = {(int(row["year"]), int(row["class_code"])): int(row["pixel_count"]) for row in rows}
    assert counts[(2002, 1)] == 4
    assert counts[(2002, 2)] == 8
    assert counts[(2002, 3)] == 4

    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["transitions"][0]["changed_pixel_count"] == 4
    assert summary["transitions"][1]["changed_pixel_count"] == 2
    assert summary["priority_analysis"]["status"].startswith("blocked")

    with (
        rasterio.open(output / "rasters/lulc_2002_reclassified.tif") as first,
        rasterio.open(output / "rasters/lulc_2022_reclassified.tif") as last,
    ):
        assert first.crs == last.crs
        assert first.transform == last.transform
        assert (first.width, first.height) == (4, 4)

    manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "completed-draft-for-expert-review"
    assert manifest["inputs"]["rasters"]["2002"]["sha256"]


def test_pipeline_rejects_unmapped_classes(fixture_project):
    config = load_config(fixture_project(unmapped=True))

    with pytest.raises(PipelineError, match="unmapped source classes"):
        run_lulc(config, "unmapped-run")
