"""Copy versioned engine code and checked reference inputs into Docker context."""
import hashlib
import json
from pathlib import Path
import shutil

service = Path(__file__).resolve().parent
repo = service.parents[1]
build = service / "build"
build.mkdir(exist_ok=True)
for name, source in {"nbs_prepare":repo / "engine/localprep/nbs_prepare", "nbs_gis":repo / "engine/src/nbs_gis", "reference":repo / "public/data"}.items():
    destination = build / name
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
shutil.copyfile(repo / "engine/examples/ganjam-glcfcs-demo/crosswalk.csv", build / "reference/glcfcs/crosswalk.csv")
records = [{"file":str(p.relative_to(build / "reference")),"sha256":hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted((build / "reference").rglob("*")) if p.is_file()]
(build / "reference-manifest.json").write_text(json.dumps(records,indent=2))
print(f"Prepared engine code and {len(records)} reference files.")
