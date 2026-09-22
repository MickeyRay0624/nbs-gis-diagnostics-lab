"""Export one completed model run in a fresh process with a bounded memory peak."""
import json
from pathlib import Path
import sys

from .results import export_results


if __name__ == "__main__":
    folder = Path(sys.argv[1]).resolve()
    export_results(folder / "model", folder / "results", json.loads((folder / "request.json").read_text()),
                   json.loads((folder / "model-run.json").read_text()))
