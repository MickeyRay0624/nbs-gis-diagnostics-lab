from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

from nbs_gis.errors import PipelineError

REQUIRED_COLUMNS = {"source_code", "target_code", "target_name", "color"}
HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


@dataclass(frozen=True)
class TargetClass:
    code: int
    name: str
    color: str


@dataclass(frozen=True)
class Crosswalk:
    source_to_target: dict[int, int]
    target_classes: dict[int, TargetClass]
    path: Path


def load_crosswalk(path: Path, output_nodata: int) -> Crosswalk:
    if not path.is_file():
        raise PipelineError(f"Class crosswalk not found: {path}")

    try:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            headers = set(reader.fieldnames or [])
            missing = REQUIRED_COLUMNS - headers
            if missing:
                raise PipelineError(f"Crosswalk is missing columns: {', '.join(sorted(missing))}")
            rows = list(reader)
    except OSError as error:
        raise PipelineError(f"Unable to read class crosswalk: {path}: {error}") from error

    if not rows:
        raise PipelineError(f"Class crosswalk has no mapping rows: {path}")

    source_to_target: dict[int, int] = {}
    target_classes: dict[int, TargetClass] = {}
    for row_number, row in enumerate(rows, start=2):
        try:
            source_code = int(row["source_code"])
            target_code = int(row["target_code"])
        except (TypeError, ValueError) as error:
            raise PipelineError(
                f"Crosswalk row {row_number} has a non-integer source or target code"
            ) from error
        name = str(row["target_name"]).strip()
        color = str(row["color"]).strip()
        if source_code in source_to_target:
            raise PipelineError(f"Duplicate source code {source_code} in crosswalk")
        if target_code == output_nodata:
            raise PipelineError(
                f"Target class {target_code} conflicts with output_nodata={output_nodata}"
            )
        if target_code < 1 or target_code >= 1_000:
            raise PipelineError("Target class codes must be between 1 and 999")
        if not name:
            raise PipelineError(f"Crosswalk row {row_number} has an empty target_name")
        if not HEX_COLOR.fullmatch(color):
            raise PipelineError(f"Crosswalk row {row_number} color must use #RRGGBB notation")

        target_class = TargetClass(target_code, name, color.lower())
        previous = target_classes.get(target_code)
        if previous and previous != target_class:
            raise PipelineError(
                f"Target code {target_code} has conflicting names or colors in crosswalk"
            )
        source_to_target[source_code] = target_code
        target_classes[target_code] = target_class

    return Crosswalk(source_to_target, target_classes, path)
