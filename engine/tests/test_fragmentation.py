from dataclasses import replace

import numpy as np
import pytest

from nbs_gis.config import FragmentationConfig, load_config
from nbs_gis.errors import PipelineError
from nbs_gis.fragmentation import classify_forest
from nbs_gis.pipeline import run_lulc


def ring_landscape():
    a = np.full((9, 9), 20, dtype=np.uint16)
    a[1:8, 1:8] = 10
    a[4, 4] = 20
    return a


def test_known_ring_area_edges_and_clearing():
    out, rows, qa = classify_forest(ring_landscape(), [10], 10, 10)
    m = rows[0]
    assert m["forest_ha"] == pytest.approx(.48)
    assert m["core_ha"] == pytest.approx(.20)
    assert m["edge_ha"] == pytest.approx(.28)
    assert m["clearing_ha"] == pytest.approx(.01)
    assert m["patch_ha"] == 0
    assert m["NP"] == 1
    assert m["TE_m"] == 320
    assert m["MPS_ha"] == pytest.approx(.48)
    assert out[4, 4] == 3
    assert qa["class_conservation"]


def test_unknown_hole_is_not_a_clearing_or_edge():
    a = ring_landscape()
    a[4, 4] = 0
    out, rows, _ = classify_forest(a, [10], 10, 10)
    assert out[4, 4] == 255
    assert rows[0]["clearing_ha"] == 0
    assert rows[0]["clearings_intersecting"] == 0
    assert rows[0]["TE_m"] == 280
    assert rows[0]["core_ha"] == pytest.approx(.24)


def test_all_forest_and_administrative_boundary():
    a = np.full((7, 7), 10)
    _, ignored, _ = classify_forest(a, [10], 10, 10)
    _, counted, _ = classify_forest(a, [10], 10, 10, count_boundary=True)
    assert ignored[0]["core_ha"] == .49
    assert ignored[0]["TE_m"] == 0
    assert counted[0]["core_ha"] == .25
    assert counted[0]["edge_ha"] == .24
    assert counted[0]["TE_m"] == 280


def test_protection_does_not_cut_patches_or_add_edges():
    a = ring_landscape()
    strata = np.full(a.shape, 3, dtype=np.uint8)
    strata[:, :4] = 1
    strata[:2, 4:] = 2
    plain, _, _ = classify_forest(a, [10], 10, 10)
    stratified, rows, qa = classify_forest(a, [10], 10, 10, strata=strata)
    assert np.array_equal(plain, stratified)
    for key in ("landscape_ha", "forest_ha", "core_ha", "edge_ha", "TE_m", "NP"):
        assert sum(r[key] for r in rows[1:]) == pytest.approx(rows[0][key])
    assert qa["straddling_patches"] == 1
    assert all(0 <= r["LPI"] <= 100 for r in rows)
    assigned = next(r for r in rows[1:] if r["NP"])
    assert assigned["MPS_ha"] == pytest.approx(.48)


def test_eight_connected_patches_and_no_forest():
    a = np.full((3, 3), 20)
    a[0, 0] = a[1, 1] = 10
    _, rows, _ = classify_forest(a, [10], 10, 10)
    assert rows[0]["NP"] == 1
    _, rows, _ = classify_forest(a, [95], 10, 10)
    assert rows[0]["NP"] == rows[0]["forest_ha"] == 0


@pytest.mark.parametrize("edge", [0, 5, float("nan"), float("inf")])
def test_invalid_edge_rejected(edge):
    with pytest.raises(PipelineError):
        classify_forest(ring_landscape(), [10], 10, edge)


def test_pipeline_exports_fragmentation_and_gain_loss(fixture_project):
    config = load_config(fixture_project())
    config = replace(config, fragmentation=FragmentationConfig(
        enabled=True, forest_codes=(2,), edge_width_m=1))
    output = run_lulc(config, "with-forest")
    assert (output / "rasters/fragmentation_2002.tif").is_file()
    assert (output / "tables/forest_fragmentation.csv").is_file()
    assert (output / "tables/gain_loss_by_period.csv").is_file()
