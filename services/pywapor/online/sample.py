"""Provision the pinned public provider inputs once, outside the request path."""
import argparse
import json
from pathlib import Path
import shutil
import urllib.request
import zipfile

from .results import sha256


def provision(data: Path, source: Path | None = None):
    manifest = json.loads((Path(__file__).parent / "sample-manifest.json").read_text())
    target = data / "sample"
    target.mkdir(parents=True, exist_ok=True)
    ready = target / "ready.json"
    ready.unlink(missing_ok=True)
    archive = None
    if source is None:
        cache = data / "source-cache"
        cache.mkdir(parents=True, exist_ok=True)
        archive = cache / "fao-test-data.zip"
        if not archive.exists() or sha256(archive) != manifest["sha256"]:
            partial = archive.with_suffix(".partial")
            with urllib.request.urlopen(manifest["source_url"], timeout=120) as response, partial.open("wb") as f:
                shutil.copyfileobj(response, f)
            if sha256(partial) != manifest["sha256"]:
                raise ValueError("FAO archive checksum mismatch.")
            partial.replace(archive)
    for item in manifest["files"]:
        relative = Path(item["path"]).relative_to("fayoum")
        dest = target / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        if source:
            shutil.copyfile(source / relative, dest)
        else:
            with zipfile.ZipFile(archive) as z, z.open("test_data/" + item["path"]) as src, dest.open("wb") as f:
                shutil.copyfileobj(src, f)
        if sha256(dest) != item["sha256"]:
            raise ValueError("Public provider input checksum mismatch.")
    ready.write_text(json.dumps({"files": len(manifest["files"]), "source": manifest["source_url"]}))
    print("Verified seven FAO source products. Public sample ready.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--source", type=Path)
    args = p.parse_args()
    provision(args.data, args.source)
