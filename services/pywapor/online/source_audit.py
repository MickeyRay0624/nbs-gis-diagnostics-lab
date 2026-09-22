"""Require the configured inputs and record the files actually supplied to the model."""
from pathlib import Path

from .results import sha256


def required_products(configuration):
    return frozenset(
        (product["source"], product["product_name"])
        for variable in configuration.values()
        for product in variable["products"]
        if not product["source"].startswith("FILE:")
    )


def acquired_manifest(model, required, datasets):
    # pyWaPOR can drop a failed source and continue. For this fixed server
    # configuration every external product is required; generated SE_ROOT
    # files are checked later by the model/export and excluded here.
    if not required or required.difference(datasets):
        raise RuntimeError("Required satellite or weather inputs could not be acquired.")
    files = []
    root = Path(model).resolve()
    for source, product in sorted(required):
        path = Path(datasets[(source, product)]).resolve()
        relative = path.relative_to(root)
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError("A required prepared provider input is empty or unavailable.")
        files.append({"source": source, "product": product, "path": relative.as_posix(),
                      "bytes": path.stat().st_size, "sha256": sha256(path)})
    return {"kind": "server-acquired prepared provider inputs", "files": files}
