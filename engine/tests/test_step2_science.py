"""Small analytical cases independent of the public data, with no network use."""

import importlib.util
import sys
from pathlib import Path

import numpy as np

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dry_runs_threshold_units_and_missing_observations():
    climate = load("prepare_step2_climate")
    data = np.zeros((5, 4, 1, 3), dtype="float64")
    data[:, 0] = 308.15  # Exactly 35 C is not a hot day.
    data[:, 1] = 293.15  # Exactly 20 C is not a warm night.
    data[:, 2] = 273.15
    data[:, 3] = 2 / 86400
    data[:, 3, 0, 0] = np.array([0, 0, 1, 0, 100.1]) / 86400
    data[0, 0, 0, 0] = 309.15
    data[0, 1, 0, 0] = 274.15
    data[1, 1, 0, 0] = 272.15
    data[0, 2, 0, 2] = np.nan
    result = climate.annual_indices(data)
    # Three dry days in two spells (2 + 1); >100 mm means one extreme day.
    assert result[5, 0, 0] == 1.5
    assert result[5, 0, 1] == 0
    assert result[0, 0, 0] == 1
    assert result[1, 0, 0] == 0
    assert result[2, 0, 0] == 1
    assert result[4, 0, 0] == 1
    assert np.isnan(result[:, 0, 2]).all()


def test_vhi_climatology_and_unsupported_ranges():
    drought = load("prepare_step2_drought")
    ndvi = np.array([[0.2, 0.4, np.nan], [0.5, 0.4, 0.5], [0.8, 0.4, 0.8]])
    temp = np.array([[30, 30, 30], [25, 25, 25], [20, 20, 20]])
    result = drought.vegetation_health(ndvi, temp, min_years=3)
    np.testing.assert_allclose(result[:, 0], [0, 50, 100])
    assert np.isnan(result[:, 1:]).all()  # Constant NDVI and missing reference year.


def test_degradation_published_codes_rounding_and_incomplete_evidence():
    degradation = load("prepare_step2_degradation")
    np.testing.assert_equal(
        degradation.productivity_classes(np.array([1, 2, 3, 4, 5, np.nan])),
        [-1, -1, 0, 0, 1, np.nan],
    )
    np.testing.assert_equal(
        degradation.carbon_classes(np.array([-11, -10, -9, 0, 9, 10, 11, np.nan])),
        [-1, np.nan, 0, 0, 0, np.nan, 1, np.nan],
    )
    components = np.array([[-1, 0, 1, 0], [np.nan, np.nan, 0, 0], [1, 1, 0, 0]])
    np.testing.assert_equal(degradation.combine(components), [-1, np.nan, 1, 0])
