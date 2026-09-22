"""One isolated job: source acquisition -> SE_ROOT -> ETLook -> checked results."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time

from .config import configure_accounts
from .providers import configure_laads


def stage(folder, title):
    path = folder / "stage.tmp"
    path.write_text(json.dumps({"stage": title}))
    path.replace(folder / "stage.json")


def main():
    folder = Path(sys.argv[1]).resolve()
    request = json.loads((folder / "request.json").read_text())
    model = folder / "model"
    model.mkdir()
    os.environ["MPLCONFIGDIR"] = str(model / "mpl-cache")
    import dask
    import pywapor
    from pywapor.collect import accounts
    from pywapor.collect.protocol import copernicus_odata

    # pyWaPOR's default getter prompts and writes keys into site-packages. A
    # server worker must use only configured secrets and must never prompt.
    configure_accounts(accounts, copernicus_odata, request["mode"])
    if request["mode"] == "custom":
        from pywapor.collect.product import VIIRSL1
        configure_laads(VIIRSL1, accounts)
    source_manifest = None
    if request["mode"] == "sample":
        stage(folder, "Verifying the FAO public source inputs")
        source = Path(os.environ["NBS_DATA_DIR"]) / "sample"
        source_manifest = json.loads((Path(__file__).parent / "sample-manifest.json").read_text())
        for item in source_manifest["files"]:
            relative = Path(item["path"]).relative_to("fayoum")
            path = source / relative
            if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
                raise ValueError("The public sample source checksum failed.")
            dest = model / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, dest)
    project = pywapor.Project(str(model), request["bbox"], [request["start"], request["end"]])
    project.load_configuration(name="WaPOR3_level_2")
    project.configuration.to_json(str(model / "configuration.json"))
    started, timings = time.monotonic(), {}
    # One task at a time; small chunks and one computational thread keep this
    # pilot compatible with a shared 2-vCPU host.
    with dask.config.set(scheduler="threads", num_workers=1):
        for key, title, fn in [
            ("download", "Collecting satellite and weather inputs", project.download_data),
            ("pre_se_root", "Preparing root-zone water inputs", project.run_pre_se_root),
            ("se_root", "Calculating root-zone relative saturation", lambda: project.run_se_root(se_root_version="v3", chunks={"time": 2, "y": 128, "x": 128})),
            ("pre_et_look", "Preparing daily energy-balance inputs", lambda: project.run_pre_et_look(bin_length=1)),
            ("et_look", "Calculating evapotranspiration and productivity", lambda: project.run_et_look(et_look_version="v3", export_vars=["e_24_mm", "t_24_mm", "aeti_24_mm", "int_mm", "et_ref_24_mm", "se_root", "npp"], chunks={"time_bins": 2, "y": 128, "x": 128})),
        ]:
            stage(folder, title)
            before = time.monotonic()
            fn()
            timings[key] = round(time.monotonic() - before, 3)
    stage(folder, "Checking model output and preparing maps and downloads")
    (folder / "model-run.json").write_text(json.dumps({"version": pywapor.__version__, "stages_seconds": timings,
        "model_seconds": round(time.monotonic() - started, 3), "source_manifest": source_manifest}))
    # Replace the process after the model has saved its output. pyWaPOR retains
    # large datasets/graphs; exporting in that same process can exceed the RAM
    # limit even though both stages fit individually. exec releases that memory
    # while preserving the PID/process group monitored by the queue worker.
    export_env = {k: v for k, v in os.environ.items() if not k.startswith(("NBS_NASA_", "NBS_CDSE_", "NBS_CDS_"))}
    os.execve(sys.executable, [sys.executable, "-m", "online.export_job", str(folder)], export_env)


if __name__ == "__main__":
    main()
