#!/usr/bin/env python3
"""Double-click a launcher, or run this file. No source-code changes are needed."""

import argparse
import hashlib
import os
import subprocess
import sys
import venv
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Prepare your configured NbS diagnostics on this computer."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check the package and configuration without data downloads.",
    )
    parser.add_argument(
        "--use-current-env",
        action="store_true",
        help="Advanced: use an environment whose dependencies are already installed.",
    )
    args = parser.parse_args()
    folder = Path(__file__).resolve().parent
    os.chdir(folder)
    if not (3, 11) <= sys.version_info[:2] <= (3, 13):
        print(
            "Please install Python 3.12 (64-bit) from https://www.python.org/downloads/ and start again."
        )
        return 1
    if not args.use_current_env:
        env = folder / ".venv"
        python = env / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        requirements = folder / "requirements.txt"
        fingerprint = hashlib.sha256(requirements.read_bytes()).hexdigest()
        marker = env / ".nbs-requirements"
        if not python.exists():
            print("First run: creating a private Python environment in this folder…", flush=True)
            venv.EnvBuilder(with_pip=True).create(env)
        if not marker.exists() or marker.read_text(encoding="utf-8") != fingerprint:
            print(
                "Installing open-source dependencies. This needs an internet connection and may take several minutes…",
                flush=True,
            )
            result = subprocess.run(
                [
                    str(python),
                    "-m",
                    "pip",
                    "install",
                    "--only-binary=:all:",
                    "-r",
                    str(requirements),
                ]
            )
            if result.returncode:
                print(
                    "Dependency installation failed. Use Python 3.12, check the internet connection, and run the launcher again. No results have been marked complete."
                )
                return result.returncode
            marker.write_text(fingerprint)
        return subprocess.call(
            [
                str(python),
                str(folder / "run.py"),
                "--use-current-env",
                *(["--check"] if args.check else []),
            ]
        )
    try:
        from nbs_prepare.main import run

        return run(folder, check=args.check)
    except ImportError as e:
        print(
            f"A required Python package is unavailable: {e.name}. Run a launcher again to install the dependencies."
        )
        return 1
    except Exception as e:
        print(f"Preparation could not start: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
