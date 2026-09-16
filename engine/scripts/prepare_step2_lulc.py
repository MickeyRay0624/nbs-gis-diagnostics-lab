"""Prepare consistent GLC-FCS30D browser inputs and independent Python results.

Acquire the cropped source with gee_lulc.js first. Fine source codes are retained
in the public GeoTIFFs; the explicit ten-class crosswalk remains user-editable.
"""

import csv
import hashlib
import json
from pathlib import Path
import numpy as np
import rasterio
from rasterio.features import rasterize
from shapely.geometry import mapping
from nbs_gis.config import load_config
from nbs_gis.pipeline import run_lulc
from step2_package import AOI_AREA, AOI_PATH, ROOT, CACHE, OUT

GROUPS = [
    (1, "Cropland", "#deb85b", [10, 11, 12, 20]),
    (2, "Forest (including mangroves)", "#246445", [51, 52, 61, 62, 71, 72, 81, 82, 91, 92, 185]),
    (3, "Shrubland", "#b6ac51", [120, 121, 122]),
    (4, "Grassland", "#98bd61", [130]),
    (5, "Wetland", "#63b6a4", [181, 182, 183, 184, 186, 187]),
    (6, "Built-up", "#cf7058", [190]),
    (7, "Bare land", "#b2aaa0", [200, 201, 202]),
    (8, "Water", "#589dc4", [210]),
    (9, "Snow and ice", "#d7e9ed", [220]),
    (10, "Other / sparse vegetation", "#c5bca1", [140, 150, 152, 153]),
]


def main():
    output = ROOT / "public/data/glcfcs"
    output.mkdir(parents=True, exist_ok=True)
    config_dir = ROOT / "engine/examples/ganjam-glcfcs-demo"
    config_dir.mkdir(parents=True, exist_ok=True)
    rows = [
        dict(source_code=s, target_code=c, target_name=n, color=color)
        for c, n, color, codes in GROUPS
        for s in codes
    ]
    for path in [config_dir / "crosswalk.csv", output / "crosswalk.csv"]:
        with path.open("w") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
    inputs = []
    raw = CACHE / "glcfcs-2002-2012-2022.tif"
    with rasterio.open(raw) as src:
        inside = rasterize([(mapping(AOI_AREA), 1)], out_shape=src.shape, transform=src.transform)
        grid = dict(
            crs="EPSG:6933",
            width=src.width,
            height=src.height,
            cell=50,
            left=src.transform.c,
            top=src.transform.f,
        )
        for band, year in enumerate([2002, 2012, 2022], 1):
            data = src.read(band)
            data[inside == 0] = 0
            if set(np.unique(data)) - {0, *[r["source_code"] for r in rows]}:
                raise ValueError("Unexpected source class")
            target = output / f"ganjam_{year}_50m.tif"
            profile = src.profile.copy()
            profile.update(count=1, nodata=0)
            with rasterio.open(target, "w", **profile) as dst:
                dst.write(data, 1)
                dst.set_band_description(1, f"GLC-FCS30D {year} source classes")
            inputs.append(
                dict(
                    year=year,
                    file=target.name,
                    sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                )
            )
    config_path = config_dir / "config.yml"
    config_path.write_text("""project:
  name: Ganjam GLC-FCS30D Step 2
  aoi: ../../../public/data/ganjam-aoi.geojson
analysis:
  target_crs: EPSG:6933
  target_resolution: 50
  max_output_pixels: 8000000
  output_nodata: 0
  unmapped_class_policy: error
  rasters:
    2002: ../../../public/data/glcfcs/ganjam_2002_50m.tif
    2012: ../../../public/data/glcfcs/ganjam_2012_50m.tif
    2022: ../../../public/data/glcfcs/ganjam_2022_50m.tif
  crosswalk: crosswalk.csv
  transitions: [[2002, 2012], [2012, 2022], [2002, 2022]]
fragmentation:
  enabled: true
  forest_codes: [2]
  edge_width_m: 50
  count_boundary_as_edge: false
output:
  directory: ../../outputs/glcfcs-validation
  write_maps: false
""")
    run = run_lulc(load_config(config_path))
    summary = json.loads((run / "summary.json").read_text())
    reference = dict(
        grid=grid,
        class_area_by_year=summary["class_area_by_year"],
        transitions=summary["transitions"],
        fragmentation=summary["fragmentation"],
        qa=json.loads((run / "qa_report.json").read_text()),
        fragmentation_pixel_sha256={},
    )
    for year in [2002, 2012, 2022]:
        with rasterio.open(run / f"rasters/fragmentation_{year}.tif") as s:
            reference["fragmentation_pixel_sha256"][str(year)] = hashlib.sha256(
                s.read(1).tobytes()
            ).hexdigest()
    source = dict(
        id="glcfcs",
        name="GLC-FCS30D annual land cover",
        url="https://essd.copernicus.org/articles/16/1353/2024/",
        version="1985–2022 release; annual bands 2002, 2012, 2022",
        licence="CC BY 4.0",
        description="30 m source; Google Earth Engine community-hosted collection projects/sat-io/open-datasets/GLC-FCS30D/annual. Four tiles E80N20, E80N25, E85N20 and E85N25. Dataset DOI: 10.5281/zenodo.8239305.",
    )
    metadata = dict(
        name="GLC-FCS30D · Ganjam",
        grid=grid,
        inputs=inputs,
        source_url=source["url"],
        license=source["licence"],
        boundary="geoBoundaries gbOpen IND ADM2, 2021; ODbL 1.0",
        attribution="Zhang et al. (2024), GLC-FCS30D; community Earth Engine hosting by Samapriya Roy.",
        processing="Nearest-neighbour 30 m source → 50 m EPSG:6933 browser grid; cell-centre AOI mask. Fine source classes retained, editable ten-class crosswalk applied at runtime.",
        limitation="Consistent product supports screening, not verified change. Classification errors, mixed pixels and 50 m resampling can affect small patches. Orchards remain cropland; mangroves count as forest.",
        protection="Protection/OECM applicability and completeness await review.",
        source=source,
        source_export_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),
    )
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    (output / "python-reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    catalog = json.loads((OUT / "catalog.json").read_text())
    catalog["sources"] = [s for s in catalog["sources"] if s["id"] != "glcfcs"] + [source]
    for m in catalog["modules"]:
        if m["id"] in ("lulc", "fragmentation"):
            m["sources"] = ["glcfcs"]
            m["status"] = "available"
            m["missing"] = []
            if m["id"] == "lulc":
                m["method"] = [
                    "GLC-FCS30D 2002, 2012 and 2022; editable ten-class crosswalk, including orchards as cropland and mangroves as forest.",
                    "Nearest-neighbour 50 m EPSG:6933 grid; compare each pair on its common valid footprint. Report all three transition matrices, gains, losses and net change.",
                ]
                m["limitations"] = [
                    metadata["limitation"],
                    "Cell-centre area accounting differs slightly from the fractional boundary weights used for continuous indicators. Do not compare small denominator differences as environmental change.",
                ]
    (OUT / "catalog.json").write_text(json.dumps(catalog, indent=2) + "\n")
    print("Prepared three GLC-FCS30D inputs and independent reference:", run, flush=True)


if __name__ == "__main__":
    main()
