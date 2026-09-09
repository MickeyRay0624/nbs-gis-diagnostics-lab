from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.warp import Resampling, reproject
from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry

from nbs_gis.config import AnalysisConfig
from nbs_gis.crosswalk import Crosswalk
from nbs_gis.errors import PipelineError
from nbs_gis.grid import GridSpec

SOURCE_NODATA = np.iinfo(np.int32).min


@dataclass(frozen=True)
class ProcessedRaster:
    year: int
    path: Path
    source_codes: tuple[int, ...]
    unmapped_codes: tuple[int, ...]
    class_counts: dict[int, int]
    valid_pixel_count: int


@dataclass(frozen=True)
class TransitionResult:
    start_year: int
    end_year: int
    transition_raster: Path
    change_raster: Path
    long_table: Path
    matrix_table: Path
    transition_counts: dict[tuple[int, int], int]
    valid_pixel_count: int
    changed_pixel_count: int


def _raster_profile(grid: GridSpec, dtype: str, nodata: int) -> dict[str, Any]:
    return {
        "driver": "GTiff",
        "width": grid.width,
        "height": grid.height,
        "count": 1,
        "dtype": dtype,
        "crs": grid.crs,
        "transform": grid.transform,
        "nodata": nodata,
        "compress": "deflate",
        "predictor": 2,
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
        "BIGTIFF": "IF_SAFER",
    }


def reclassify_raster(
    year: int,
    source_path: Path,
    destination_path: Path,
    aoi_geometry: BaseGeometry,
    grid: GridSpec,
    crosswalk: Crosswalk,
    analysis: AnalysisConfig,
) -> ProcessedRaster:
    aligned = np.full((grid.height, grid.width), SOURCE_NODATA, dtype=np.int32)
    with rasterio.open(source_path) as source:
        reproject(
            source=rasterio.band(source, 1),
            destination=aligned,
            src_transform=source.transform,
            src_crs=source.crs,
            src_nodata=source.nodata,
            dst_transform=grid.transform,
            dst_crs=grid.crs,
            dst_nodata=SOURCE_NODATA,
            resampling=Resampling.nearest,
            init_dest_nodata=True,
        )

    inside = geometry_mask(
        [mapping(aoi_geometry)],
        out_shape=(grid.height, grid.width),
        transform=grid.transform,
        invert=True,
        all_touched=analysis.all_touched,
    )
    valid_source = inside & (aligned != SOURCE_NODATA)
    source_codes = tuple(int(value) for value in np.unique(aligned[valid_source]))
    unmapped_codes = tuple(
        sorted(code for code in source_codes if code not in crosswalk.source_to_target)
    )
    if unmapped_codes and analysis.unmapped_class_policy == "error":
        values = ", ".join(str(code) for code in unmapped_codes[:20])
        suffix = "..." if len(unmapped_codes) > 20 else ""
        raise PipelineError(f"Raster {year} contains unmapped source classes: {values}{suffix}")

    reclassified = np.full((grid.height, grid.width), analysis.output_nodata, dtype=np.uint16)
    for source_code, target_code in crosswalk.source_to_target.items():
        reclassified[valid_source & (aligned == source_code)] = target_code

    valid_target = inside & (reclassified != analysis.output_nodata)
    unique, counts = np.unique(reclassified[valid_target], return_counts=True)
    class_counts = {int(code): int(count) for code, count in zip(unique, counts, strict=True)}

    destination_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        destination_path,
        "w",
        **_raster_profile(grid, "uint16", analysis.output_nodata),
    ) as destination:
        destination.write(reclassified, 1)
        destination.set_band_description(1, f"Reclassified LULC {year}")
        destination.update_tags(
            analysis="NbS LULC change detection",
            year=str(year),
            source=str(source_path),
            crosswalk=str(crosswalk.path),
            unmapped_class_policy=analysis.unmapped_class_policy,
        )

    return ProcessedRaster(
        year=year,
        path=destination_path,
        source_codes=source_codes,
        unmapped_codes=unmapped_codes,
        class_counts=class_counts,
        valid_pixel_count=int(valid_target.sum()),
    )


def _write_transition_tables(
    result_counts: Counter[tuple[int, int]],
    long_path: Path,
    matrix_path: Path,
    crosswalk: Crosswalk,
    pixel_area_ha: float,
    valid_pixel_count: int,
) -> None:
    class_codes = sorted(crosswalk.target_classes)
    with long_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            [
                "from_code",
                "from_class",
                "to_code",
                "to_class",
                "pixel_count",
                "area_ha",
                "percent_of_valid_area",
            ]
        )
        for (from_code, to_code), count in sorted(result_counts.items()):
            writer.writerow(
                [
                    from_code,
                    crosswalk.target_classes[from_code].name,
                    to_code,
                    crosswalk.target_classes[to_code].name,
                    count,
                    f"{count * pixel_area_ha:.6f}",
                    f"{count / valid_pixel_count * 100:.6f}" if valid_pixel_count else "0.000000",
                ]
            )

    with matrix_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["from_class", *[crosswalk.target_classes[c].name for c in class_codes]])
        for from_code in class_codes:
            writer.writerow(
                [
                    crosswalk.target_classes[from_code].name,
                    *[result_counts.get((from_code, to_code), 0) for to_code in class_codes],
                ]
            )


def calculate_transition(
    start_year: int,
    end_year: int,
    start_path: Path,
    end_path: Path,
    raster_output_directory: Path,
    table_output_directory: Path,
    grid: GridSpec,
    crosswalk: Crosswalk,
    output_nodata: int,
) -> TransitionResult:
    transition_raster = raster_output_directory / f"transition_{start_year}_{end_year}.tif"
    change_raster = raster_output_directory / f"change_{start_year}_{end_year}.tif"
    long_table = table_output_directory / f"transition_{start_year}_{end_year}_long.csv"
    matrix_table = table_output_directory / f"transition_{start_year}_{end_year}_matrix.csv"
    counts: Counter[tuple[int, int]] = Counter()
    valid_pixel_count = 0
    changed_pixel_count = 0

    with (
        rasterio.open(start_path) as start,
        rasterio.open(end_path) as end,
        rasterio.open(
            transition_raster, "w", **_raster_profile(grid, "uint32", 0)
        ) as transition_destination,
        rasterio.open(
            change_raster, "w", **_raster_profile(grid, "uint8", 255)
        ) as change_destination,
    ):
        if (
            start.width != end.width
            or start.height != end.height
            or start.transform != end.transform
            or start.crs != end.crs
        ):
            raise PipelineError("Reclassified rasters are not aligned")

        for _, window in start.block_windows(1):
            start_values = start.read(1, window=window)
            end_values = end.read(1, window=window)
            valid = (start_values != output_nodata) & (end_values != output_nodata)
            encoded = np.zeros(start_values.shape, dtype=np.uint32)
            encoded[valid] = start_values[valid].astype(np.uint32) * 1_000 + end_values[
                valid
            ].astype(np.uint32)
            change = np.full(start_values.shape, 255, dtype=np.uint8)
            change[valid] = (start_values[valid] != end_values[valid]).astype(np.uint8)
            transition_destination.write(encoded, 1, window=window)
            change_destination.write(change, 1, window=window)

            values, value_counts = np.unique(encoded[valid], return_counts=True)
            for encoded_value, count in zip(values, value_counts, strict=True):
                from_code = int(encoded_value) // 1_000
                to_code = int(encoded_value) % 1_000
                counts[(from_code, to_code)] += int(count)
            valid_pixel_count += int(valid.sum())
            changed_pixel_count += int((change[valid] == 1).sum())

        if sum(counts.values()) != valid_pixel_count:
            raise PipelineError(f"Transition-count conservation failed for {start_year}-{end_year}")

        transition_destination.set_band_description(
            1, f"Transition code {start_year}-{end_year}; code = from * 1000 + to"
        )
        transition_destination.update_tags(
            start_year=str(start_year),
            end_year=str(end_year),
            encoding="from_class_code * 1000 + to_class_code",
        )
        change_destination.set_band_description(1, f"Binary LULC change {start_year}-{end_year}")
        change_destination.update_tags(
            start_year=str(start_year), end_year=str(end_year), stable="0", changed="1"
        )

    _write_transition_tables(
        counts,
        long_table,
        matrix_table,
        crosswalk,
        grid.pixel_area_ha,
        valid_pixel_count,
    )
    return TransitionResult(
        start_year=start_year,
        end_year=end_year,
        transition_raster=transition_raster,
        change_raster=change_raster,
        long_table=long_table,
        matrix_table=matrix_table,
        transition_counts=dict(counts),
        valid_pixel_count=valid_pixel_count,
        changed_pixel_count=changed_pixel_count,
    )
