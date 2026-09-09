from nbs_gis.cli import main


def test_cli_preflight_exit_codes(fixture_project, capsys):
    ready = fixture_project()
    assert main(["preflight", "--config", str(ready)]) == 0
    assert "Preflight status: READY" in capsys.readouterr().out

    blocked = fixture_project(missing_raster=True)
    assert main(["preflight", "--config", str(blocked)]) == 2
    assert "Preflight status: BLOCKED" in capsys.readouterr().out


def test_cli_run_lulc(fixture_project, capsys):
    config = fixture_project()
    assert main(["run-lulc", "--config", str(config), "--run-id", "cli-run"]) == 0
    output = config.parent / "outputs" / "cli-run"
    assert (output / "run_manifest.json").is_file()
    assert (output / "tables" / "transition_2002_2012_matrix.csv").is_file()
    assert "Run completed:" in capsys.readouterr().out
