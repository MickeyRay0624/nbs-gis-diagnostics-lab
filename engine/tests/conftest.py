from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pytest
import rasterio
import yaml
from rasterio.transform import from_origin


@pytest.fixture
def fixture_project(tmp_path: Path):
    case_number = 0

    def build(*, missing_raster: bool = False, unmapped: bool = False, maps: bool = False) -> Path:
        nonlocal case_number
        case_number += 1
        case_path = tmp_path / f"case-{case_number}"
        case_path.mkdir()
        aoi = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"name": "Fixture AOI"},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]]],
                    },
                }
            ],
        }
        (case_path / "aoi.geojson").write_text(json.dumps(aoi), encoding="utf-8")

        arrays = {
            2002: np.array(
                [[1, 1, 2, 2], [1, 1, 2, 2], [3, 3, 2, 2], [3, 3, 2, 2]],
                dtype=np.uint8,
            ),
            2012: np.array(
                [[1, 2, 2, 2], [1, 2, 2, 2], [3, 3, 3, 2], [3, 3, 3, 2]],
                dtype=np.uint8,
            ),
            2022: np.array(
                [[1, 2, 2, 2], [1, 2, 2, 2], [3, 3, 3, 3], [3, 3, 3, 3]],
                dtype=np.uint8,
            ),
        }
        if unmapped:
            arrays[2022][0, 0] = 9
        for year, values in arrays.items():
            if missing_raster and year == 2012:
                continue
            with rasterio.open(
                case_path / f"lulc_{year}.tif",
                "w",
                driver="GTiff",
                width=4,
                height=4,
                count=1,
                dtype="uint8",
                crs="EPSG:6933",
                transform=from_origin(0, 4, 1, 1),
                nodata=255,
            ) as dataset:
                dataset.write(values, 1)

        with (case_path / "crosswalk.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["source_code", "target_code", "target_name", "color"])
            writer.writerows(
                [
                    [1, 1, "Cropland", "#e4bf61"],
                    [2, 2, "Forest", "#2f6d45"],
                    [3, 3, "Water", "#4d91c6"],
                ]
            )

        config = {
            "project": {
                "name": "Fixture AOI",
                "aoi": "aoi.geojson",
                "aoi_crs": "EPSG:6933",
            },
            "analysis": {
                "target_crs": "EPSG:6933",
                "target_resolution": 1,
                "output_nodata": 0,
                "all_touched": False,
                "unmapped_class_policy": "error",
                "max_output_pixels": 1000,
                "rasters": {year: f"lulc_{year}.tif" for year in arrays},
                "crosswalk": "crosswalk.csv",
                "transitions": [[2002, 2012], [2012, 2022]],
            },
            "output": {
                "directory": "outputs",
                "write_maps": maps,
                "map_dpi": 80,
            },
        }
        config_path = case_path / "config.yml"
        config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
        return config_path

    return build
