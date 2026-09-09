from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from nbs_gis import __version__
from nbs_gis.config import load_config
from nbs_gis.errors import NbsGisError
from nbs_gis.pipeline import run_lulc
from nbs_gis.preflight import run_preflight
from nbs_gis.utils import write_json


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nbs-gis",
        description="Reproducible GIS processing for Nature-based Solutions diagnostics",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    preflight = commands.add_parser(
        "preflight", help="Validate AOI, crosswalk, raster metadata and target grid"
    )
    preflight.add_argument("--config", required=True, type=Path, help="YAML run configuration")
    preflight.add_argument("--output", type=Path, help="Optional JSON report path")
    preflight.add_argument("--json", action="store_true", help="Print the complete JSON report")

    run = commands.add_parser("run-lulc", help="Run the deterministic LULC change pipeline")
    run.add_argument("--config", required=True, type=Path, help="YAML run configuration")
    run.add_argument("--run-id", help="Optional stable run identifier")
    return parser


def _print_preflight(report: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return
    print(f"Preflight status: {report['status'].upper()}")
    for check in report["checks"]:
        marker = {"pass": "PASS", "warning": "WARN", "error": "ERROR"}[check["status"]]
        print(f"[{marker}] {check['id']}: {check['message']}")


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        config = load_config(args.config)
        if args.command == "preflight":
            report = run_preflight(config)
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                write_json(args.output, report)
            _print_preflight(report, args.json)
            return 0 if report["status"] == "ready" else 2

        if args.command == "run-lulc":
            output_directory = run_lulc(config, args.run_id)
            print(f"Run completed: {output_directory}")
            return 0
    except NbsGisError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    return 1
