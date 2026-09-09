from nbs_gis.config import load_config


def test_load_config_resolves_paths_and_transitions(fixture_project):
    config = load_config(fixture_project())

    assert config.project.name == "Fixture AOI"
    assert config.project.aoi_path.is_absolute()
    assert sorted(config.analysis.rasters) == [2002, 2012, 2022]
    assert config.analysis.transitions == ((2002, 2012), (2012, 2022))
