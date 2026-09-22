import hashlib
import json
import os
from pathlib import Path

from online.worker import main


if __name__ == "__main__":
    root = Path(os.getenv("NBS_REFERENCE_DIR", "/app/reference"))
    manifest = root.parent / "reference-manifest.json"
    records = json.loads(manifest.read_text())
    for record in records:
        path = (root / record["file"]).resolve()
        if not path.is_relative_to(root.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
            raise SystemExit("A Ganjam reference input failed its checksum.")
    data = Path(os.environ["NBS_DATA_DIR"])
    data.mkdir(parents=True,exist_ok=True,mode=0o700)
    (data / "sample-ready.json").write_text(json.dumps({"files_checked":len(records)}))
    main("diagnostics.pipeline")
