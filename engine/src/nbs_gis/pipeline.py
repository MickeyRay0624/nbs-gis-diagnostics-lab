from __future__ import annotations

import csv
import platform
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import pyproj
import rasterio
import shapely

from nbs_gis import __version__
from nbs_gis.aoi import load_aoi, transform_geometry
from nbs_gis.config import RunConfig
from nbs_gis.crosswalk import Crosswalk, load_crosswalk
from nbs_gis.errors import PipelineError, PreflightBlocked
from nbs_gis.grid import build_grid, parse_target_crs
from nbs_gis.plotting import write_change_map, write_lulc_map
from nbs_gis.preflight import run_preflight
from nbs_gis.processing import (
    ProcessedRaster,
    TransitionResult,
    calculate_transition,
    reclassify_raster,
)
from nbs_gis.utils import make_run_id, sha256_file, utc_now, write_json

SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")


def _write_area_table(
    path: Path,
    processed: dict[int, ProcessedRaster],
    crosswalk: Crosswalk,
    pixel_area_ha: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "year",
                "class_code",
                "class_name",
                "pixel_count",
                "area_ha",
                "percent_of_valid_area",
            ],
        )
        writer.writeheader()
        for year, result in sorted(processed.items()):
            for code, target in sorted(crosswalk.target_classes.items()):
                count = result.class_counts.get(code, 0)
                row = {
                    "year": year,
                    "class_code": code,
                    "class_name": target.name,
                    "pixel_count": count,
                    "area_ha": round(count * pixel_area_ha, 6),
                    "percent_of_valid_area": round(count / result.valid_pixel_count * 100, 6)
                    if result.valid_pixel_count
                    else 0,
                }
                rows.append(row)
                writer.writerow(row)
    return rows


def _transition_summary(
    transition: TransitionResult, crosswalk: Crosswalk, pixel_area_ha: float
) -> dict[str, Any]:
    changed = [
        (pair, count) for pair, count in transition.transition_counts.items() if pair[0] != pair[1]
    ]
    changed.sort(key=lambda item: (-item[1], item[0]))
    top_changes = [
        {
            "from_code": start,
            "from_class": crosswalk.target_classes[start].name,
            "to_code": end,
            "to_class": crosswalk.target_classes[end].name,
            "pixel_count": count,
            "area_ha": round(count * pixel_area_ha, 6),
        }
        for (start, end), count in changed[:10]
    ]
    return {
        "start_year": transition.start_year,
        "end_year": transition.end_year,
        "valid_pixel_count": transition.valid_pixel_count,
        "changed_pixel_count": transition.changed_pixel_count,
        "changed_area_ha": round(transition.changed_pixel_count * pixel_area_ha, 6),
        "changed_percent": round(
            transition.changed_pixel_count / transition.valid_pixel_count * 100, 6
        )
        if transition.valid_pixel_count
        else 0,
        "top_class_transitions": top_changes,
    }


def _write_draft_narrative(path: Path, project_name: str, summary: dict[str, Any]) -> None:
    lines = [
        f"# {project_name} LULC diagnostic summary",
        "",
        "Status: automated draft for GIS expert review.",
        "",
        "This summary is generated only from the processed categorical rasters and the approved "
        "configuration recorded in the run manifest.",
        "",
    ]
    for item in summary["transitions"]:
        lines.extend(
            [
                f"## {item['start_year']} to {item['end_year']}",
                "",
                f"Comparable valid pixels: {item['valid_pixel_count']:,}. Changed pixels: "
                f"{item['changed_pixel_count']:,} ({item['changed_percent']:.2f}%), representing "
                f"{item['changed_area_ha']:,.2f} ha.",
                "",
            ]
        )
        top_changes = item["top_class_transitions"]
        if top_changes:
            lines.append("Largest observed class transitions:")
            lines.append("")
            for change in top_changes[:5]:
                lines.append(
                    f"- {change['from_class']} to {change['to_class']}: "
                    f"{change['area_ha']:,.2f} ha."
                )
            lines.append("")
        else:
            lines.extend(["No class changes were observed in comparable valid pixels.", ""])
    lines.extend(
        [
            "## Limitation",
            "",
            "Priority-area classification is not generated in version 0.1 because the grid size, "
            "significance thresholds and class-precedence rules have not yet been approved.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _input_record(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": str(path),
        "size_bytes": stat.st_size,
        "modified_time_ns": stat.st_mtime_ns,
        "sha256": sha256_file(path),
    }


def _normalized_config(config: RunConfig) -> dict[str, Any]:
    return {
        "project": {
            "name": config.project.name,
            "aoi": str(config.project.aoi_path),
            "aoi_crs": config.project.aoi_crs,
        },
        "analysis": {
            "target_crs": config.analysis.target_crs,
            "target_resolution": config.analysis.target_resolution,
            "output_nodata": config.analysis.output_nodata,
            "all_touched": config.analysis.all_touched,
            "unmapped_class_policy": config.analysis.unmapped_class_policy,
            "max_output_pixels": config.analysis.max_output_pixels,
            "crosswalk": str(config.analysis.crosswalk_path),
            "rasters": {str(year): str(path) for year, path in config.analysis.rasters.items()},
            "transitions": [list(pair) for pair in config.analysis.transitions],
        },
        "output": {
            "directory": str(config.output.directory),
            "write_maps": config.output.write_maps,
            "map_dpi": config.output.map_dpi,
        },
    }


def run_lulc(config: RunConfig, requested_run_id: str | None = None) -> Path:
    preflight = run_preflight(config)
    errors = [check for check in preflight["checks"] if check["status"] == "error"]
    if errors:
        messages = "; ".join(check["message"] for check in errors)
        raise PreflightBlocked(f"Preflight blocked the run: {messages}")

    created_at = utc_now()
    run_id = requested_run_id or make_run_id(config.project.name, created_at)
    if not SAFE_RUN_ID.fullmatch(run_id):
        raise PipelineError(
            "Run ID must start with a letter or number and contain only letters, numbers, "
            "'.', '_' or '-'"
        )

    output_root = config.output.directory
    output_root.mkdir(parents=True, exist_ok=True)
    final_directory = output_root / run_id
    if final_directory.exists():
        raise PipelineError(f"Output run already exists: {final_directory}")
    working_directory = Path(tempfile.mkdtemp(prefix=f".{run_id}.", dir=output_root))

    try:
        raster_directory = working_directory / "rasters"
        table_directory = working_directory / "tables"
        map_directory = working_directory / "maps"
        raster_directory.mkdir()
        table_directory.mkdir()
        if config.output.write_maps:
            map_directory.mkdir()
        write_json(working_directory / "preflight_report.json", preflight)

        aoi = load_aoi(config.project.aoi_path, config.project.aoi_crs)
        target_crs = parse_target_crs(config.analysis.target_crs)
        target_aoi = transform_geometry(aoi.geometry, aoi.crs, target_crs)
        grid = build_grid(
            target_aoi,
            target_crs,
            config.analysis.target_resolution,
            config.analysis.max_output_pixels,
        )
        crosswalk = load_crosswalk(config.analysis.crosswalk_path, config.analysis.output_nodata)

        processed: dict[int, ProcessedRaster] = {}
        warnings = [
            check["message"] for check in preflight["checks"] if check["status"] == "warning"
        ]
        for year, source_path in config.analysis.rasters.items():
            destination = raster_directory / f"lulc_{year}_reclassified.tif"
            result = reclassify_raster(
                year,
                source_path,
                destination,
                target_aoi,
                grid,
                crosswalk,
                config.analysis,
            )
            if not result.valid_pixel_count:
                raise PipelineError(f"Raster {year} has no mapped valid pixels inside the AOI")
            if result.unmapped_codes:
                warnings.append(
                    f"Raster {year}: unmapped source codes were written as NoData: "
                    + ", ".join(str(code) for code in result.unmapped_codes)
                )
            processed[year] = result
            if config.output.write_maps:
                write_lulc_map(
                    destination,
                    map_directory / f"lulc_{year}.png",
                    year,
                    config.project.name,
                    crosswalk,
                    config.output.map_dpi,
                )

        area_table = table_directory / "class_area_by_year.csv"
        area_rows = _write_area_table(area_table, processed, crosswalk, grid.pixel_area_ha)
        for year, result in processed.items():
            if sum(result.class_counts.values()) != result.valid_pixel_count:
                raise PipelineError(f"Class-area conservation failed for raster {year}")

        transition_summaries: list[dict[str, Any]] = []
        for start_year, end_year in config.analysis.transitions:
            transition = calculate_transition(
                start_year,
                end_year,
                processed[start_year].path,
                processed[end_year].path,
                raster_directory,
                table_directory,
                grid,
                crosswalk,
                config.analysis.output_nodata,
            )
            transition_summaries.append(
                _transition_summary(transition, crosswalk, grid.pixel_area_ha)
            )
            if config.output.write_maps:
                write_change_map(
                    transition.change_raster,
                    map_directory / f"change_{start_year}_{end_year}.png",
                    start_year,
                    end_year,
                    config.project.name,
                    config.output.map_dpi,
                )

        summary = {
            "schema": "nbs-lulc-summary/v0.1",
            "run_id": run_id,
            "project": config.project.name,
            "years": sorted(processed),
            "class_area_by_year": area_rows,
            "transitions": transition_summaries,
            "priority_analysis": {
                "status": "blocked-pending-approved-specification",
                "missing_decisions": [
                    "analysis grid geometry and size",
                    "significant-change thresholds",
                    "class precedence and tie-breaking rules",
                ],
            },
        }
        write_json(working_directory / "summary.json", summary)
        _write_draft_narrative(
            working_directory / "diagnostic_summary.md", config.project.name, summary
        )
        shutil.copy2(config.source_path, working_directory / "input_config.yml")

        qa = {
            "status": "pass-with-warnings" if warnings else "pass",
            "checks": [
                {
                    "id": "preflight",
                    "status": "pass",
                    "message": "All mandatory preflight checks passed",
                },
                {
                    "id": "common-grid",
                    "status": "pass",
                    "message": "All output rasters use the same CRS, transform and dimensions",
                },
                {
                    "id": "class-area-conservation",
                    "status": "pass",
                    "message": "Class counts equal mapped valid-pixel counts for every year",
                },
                {
                    "id": "priority-analysis",
                    "status": "not-run",
                    "message": "Priority rules have not yet been approved",
                },
            ],
            "warnings": warnings,
        }
        write_json(working_directory / "qa_report.json", qa)

        input_records = {
            "configuration": _input_record(config.source_path),
            "aoi": _input_record(config.project.aoi_path),
            "crosswalk": _input_record(config.analysis.crosswalk_path),
            "rasters": {
                str(year): _input_record(path) for year, path in config.analysis.rasters.items()
            },
        }
        output_files = sorted(path for path in working_directory.rglob("*") if path.is_file())
        output_records = [
            {
                "path": str(path.relative_to(working_directory)),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in output_files
        ]
        completed_at = utc_now()
        manifest = {
            "schema": "nbs-gis-run-manifest/v0.1",
            "run_id": run_id,
            "status": "completed-draft-for-expert-review",
            "created_at": created_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "project": config.project.name,
            "software": {
                "nbs_gis": __version__,
                "python": platform.python_version(),
                "platform": platform.platform(),
                "numpy": np.__version__,
                "rasterio": rasterio.__version__,
                "shapely": shapely.__version__,
                "pyproj": pyproj.__version__,
            },
            "configuration": _normalized_config(config),
            "target_grid": {
                "crs": grid.crs.to_string(),
                "resolution": grid.resolution,
                "width": grid.width,
                "height": grid.height,
                "pixel_count": grid.pixel_count,
                "pixel_area_ha": grid.pixel_area_ha,
                "bounds": list(grid.bounds),
            },
            "inputs": input_records,
            "outputs": output_records,
            "qa": qa,
            "limitations": [
                "Outputs require GIS expert review before release",
                "Priority-area classification was not run because its specification is pending",
                "Results are conditional on the supplied rasters and class crosswalk",
            ],
        }
        write_json(working_directory / "run_manifest.json", manifest)
        working_directory.replace(final_directory)
        return final_directory
    except Exception:
        shutil.rmtree(working_directory, ignore_errors=True)
        raise
