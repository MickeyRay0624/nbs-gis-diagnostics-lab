from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from nbs_gis.errors import ConfigError


@dataclass(frozen=True)
class ProjectConfig:
    name: str
    aoi_path: Path
    aoi_crs: str


@dataclass(frozen=True)
class AnalysisConfig:
    target_crs: str
    target_resolution: float
    output_nodata: int
    all_touched: bool
    unmapped_class_policy: str
    max_output_pixels: int
    rasters: dict[int, Path]
    crosswalk_path: Path
    transitions: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class OutputConfig:
    directory: Path
    write_maps: bool
    map_dpi: int


@dataclass(frozen=True)
class RunConfig:
    source_path: Path
    project: ProjectConfig
    analysis: AnalysisConfig
    output: OutputConfig


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{label} must be a mapping")
    return value


def _required(mapping: dict[str, Any], key: str, label: str) -> Any:
    if key not in mapping or mapping[key] in (None, ""):
        raise ConfigError(f"Missing required setting: {label}.{key}")
    return mapping[key]


def _resolve(base: Path, value: Any, label: str) -> Path:
    if not isinstance(value, (str, Path)) or not str(value).strip():
        raise ConfigError(f"{label} must be a non-empty path")
    path = Path(value).expanduser()
    return path if path.is_absolute() else (base / path).resolve()


def _positive_float(value: Any, label: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as error:
        raise ConfigError(f"{label} must be numeric") from error
    if parsed <= 0:
        raise ConfigError(f"{label} must be greater than zero")
    return parsed


def _positive_int(value: Any, label: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise ConfigError(f"{label} must be an integer") from error
    if parsed <= 0:
        raise ConfigError(f"{label} must be greater than zero")
    return parsed


def _boolean(value: Any, label: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1"}:
            return True
        if normalized in {"false", "no", "0"}:
            return False
    raise ConfigError(f"{label} must be true or false")


def load_config(path: str | Path) -> RunConfig:
    source_path = Path(path).expanduser().resolve()
    if not source_path.is_file():
        raise ConfigError(f"Configuration file not found: {source_path}")

    try:
        raw = yaml.safe_load(source_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise ConfigError(f"Invalid YAML in {source_path}: {error}") from error

    root = _mapping(raw, "configuration")
    project_raw = _mapping(_required(root, "project", "configuration"), "project")
    analysis_raw = _mapping(_required(root, "analysis", "configuration"), "analysis")
    output_raw = _mapping(root.get("output", {}), "output")
    base = source_path.parent

    project = ProjectConfig(
        name=str(_required(project_raw, "name", "project")).strip(),
        aoi_path=_resolve(base, _required(project_raw, "aoi", "project"), "project.aoi"),
        aoi_crs=str(project_raw.get("aoi_crs", "EPSG:4326")).strip(),
    )

    rasters_raw = _mapping(_required(analysis_raw, "rasters", "analysis"), "analysis.rasters")
    rasters: dict[int, Path] = {}
    for raw_year, raw_path in rasters_raw.items():
        try:
            year = int(raw_year)
        except (TypeError, ValueError) as error:
            raise ConfigError(f"Raster year must be an integer: {raw_year!r}") from error
        if year in rasters:
            raise ConfigError(f"Duplicate raster year: {year}")
        rasters[year] = _resolve(base, raw_path, f"analysis.rasters.{year}")
    if len(rasters) < 2:
        raise ConfigError("analysis.rasters must contain at least two years")

    transitions_raw = analysis_raw.get("transitions")
    if transitions_raw is None:
        years = sorted(rasters)
        transitions = tuple(zip(years[:-1], years[1:], strict=True))
    else:
        if not isinstance(transitions_raw, list) or not transitions_raw:
            raise ConfigError("analysis.transitions must be a non-empty list of year pairs")
        parsed: list[tuple[int, int]] = []
        for item in transitions_raw:
            if not isinstance(item, list) or len(item) != 2:
                raise ConfigError("Each transition must contain exactly two years")
            start, end = int(item[0]), int(item[1])
            if start not in rasters or end not in rasters:
                raise ConfigError(f"Transition {start}-{end} references an undefined raster")
            if start >= end:
                raise ConfigError(f"Transition must be chronological: {start}-{end}")
            parsed.append((start, end))
        if len(parsed) != len(set(parsed)):
            raise ConfigError("analysis.transitions must not contain duplicate year pairs")
        transitions = tuple(parsed)

    unmapped_policy = str(analysis_raw.get("unmapped_class_policy", "error")).lower()
    if unmapped_policy not in {"error", "nodata"}:
        raise ConfigError("analysis.unmapped_class_policy must be 'error' or 'nodata'")

    output_nodata = int(analysis_raw.get("output_nodata", 0))
    if output_nodata < 0 or output_nodata > 65_535:
        raise ConfigError("analysis.output_nodata must be between 0 and 65535")

    analysis = AnalysisConfig(
        target_crs=str(analysis_raw.get("target_crs", "EPSG:6933")).strip(),
        target_resolution=_positive_float(
            analysis_raw.get("target_resolution", 30), "analysis.target_resolution"
        ),
        output_nodata=output_nodata,
        all_touched=_boolean(analysis_raw.get("all_touched", False), "analysis.all_touched"),
        unmapped_class_policy=unmapped_policy,
        max_output_pixels=_positive_int(
            analysis_raw.get("max_output_pixels", 100_000_000),
            "analysis.max_output_pixels",
        ),
        rasters=dict(sorted(rasters.items())),
        crosswalk_path=_resolve(
            base, _required(analysis_raw, "crosswalk", "analysis"), "analysis.crosswalk"
        ),
        transitions=transitions,
    )

    output = OutputConfig(
        directory=_resolve(base, output_raw.get("directory", "outputs"), "output.directory"),
        write_maps=_boolean(output_raw.get("write_maps", True), "output.write_maps"),
        map_dpi=_positive_int(output_raw.get("map_dpi", 160), "output.map_dpi"),
    )

    return RunConfig(
        source_path=source_path,
        project=project,
        analysis=analysis,
        output=output,
    )
