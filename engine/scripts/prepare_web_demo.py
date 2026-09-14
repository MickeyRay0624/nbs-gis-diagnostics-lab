"""Rebuild small public browser inputs and independent Python reference results.

First run examples/ganjam-worldcover-demo/download_data.sh. Raw original tiles
are retained locally; only cropped 50 m categorical inputs are copied to public/.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import rasterio

from nbs_gis.config import load_config
from nbs_gis.pipeline import run_lulc
from nbs_gis.utils import sha256_file

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "engine/examples/ganjam-worldcover-demo/web-config.yml"


def main():
    config = load_config(CONFIG)
    run = run_lulc(config)
    output = ROOT / "public/data/worldcover"
    output.mkdir(parents=True, exist_ok=True)
    inputs = []
    for year, original in config.analysis.rasters.items():
        source = run / f"rasters/lulc_{year}_reclassified.tif"
        target = output / f"ganjam_{year}_50m.tif"
        shutil.copyfile(source, target)
        with rasterio.open(target) as raster:
            grid = {"crs": raster.crs.to_string(), "width": raster.width,
                    "height": raster.height, "cell": raster.res[0],
                    "left": raster.transform.c, "top": raster.transform.f}
        version = "v100" if year == 2020 else "v200"
        inputs.append({"year": year, "file": target.name, "sha256": sha256_file(target),
                       "original_sha256": sha256_file(original),
                       "original_url": f"https://esa-worldcover.s3.eu-central-1.amazonaws.com/"
                       f"{version}/{year}/map/{original.name}"})
    summary = json.loads((run / "summary.json").read_text())
    reference = {"grid": grid, "class_area_by_year": summary["class_area_by_year"],
                 "transitions": summary["transitions"], "fragmentation": summary["fragmentation"],
                 "qa": json.loads((run / "qa_report.json").read_text())}
    reference["fragmentation_pixel_sha256"] = {}
    for year in config.analysis.rasters:
        with rasterio.open(run / f"rasters/fragmentation_{year}.tif") as raster:
            reference["fragmentation_pixel_sha256"][str(year)] = hashlib.sha256(
                raster.read(1).tobytes()).hexdigest()
    metadata = {"name": "ESA WorldCover · Ganjam", "grid": grid, "inputs": inputs,
                "source_url": "https://esa-worldcover.org/en/data-access",
                "license": "CC BY 4.0", "boundary": "geoBoundaries gbOpen IND ADM2, 2021; ODbL 1.0",
                "attribution": "© ESA WorldCover project 2020/2021 / Contains modified Copernicus "
                "Sentinel data processed by ESA WorldCover consortium.",
                "processing": "Original 10 m classes resampled by nearest neighbour to a 50 m "
                "EPSG:6933 grid and masked to the Ganjam pilot boundary.",
                "limitation": "2020 v100 and 2021 v200 use different algorithms. Differences "
                "are for software testing and are not verified land-cover change.",
                "protection": "No protected-area or OECM dataset included."}
    for name, value in (("metadata.json", metadata), ("python-reference.json", reference)):
        (output / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared {len(inputs)} public rasters and Python reference at {output}")
    print(f"Full reproducibility record retained at {run}")


if __name__ == "__main__":
    main()
