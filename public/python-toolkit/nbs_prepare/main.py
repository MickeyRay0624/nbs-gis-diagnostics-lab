"""User-facing run coordinator with resumable progress and explicit partial results."""

from .core import MODULES, Context
from .modules import RUNNERS


def run(folder, check=False):
    ctx = Context(folder)
    ctx.log(f"Study area: {ctx.config['name']} ({ctx.area_aoi.area / 1e6:,.1f} km²)")
    ctx.log("Selected: " + ", ".join(MODULES[m] for m in ctx.config["modules"]))
    if check:
        ctx.log(
            "Package, boundary checksum, Python dependencies and configuration are valid. No source downloads were started."
        )
        return 0
    ctx.log(
        "Calculation runs on this computer. Keep this window open. Start again to reuse completed downloads and intermediate calculations."
    )
    ctx.log(
        "Managed-download limit excludes GDAL HTTP range reads. Source files and caches can need substantial disk space."
    )
    try:
        # Free public modules first: account problems should not block these results.
        for module in [m for m in RUNNERS if m in ctx.config["modules"]]:
            ctx.log(f"Starting {MODULES[module]}…")
            try:
                RUNNERS[module](ctx)
            except Exception as e:
                if isinstance(e, ValueError):
                    detail = str(e)[:600]
                else:
                    detail = f"{type(e).__name__}: source retrieval or decoding failed. Check internet access, available disk space and, for NASA, Earthdata authorisation; run again to reuse the cache."
                ctx.failures[module] = detail
                ctx.log(f"Could not complete {MODULES[module]}: {detail}")
            ctx.finish()
    except KeyboardInterrupt:
        ready = {m["id"] for m in ctx.catalog["modules"] if m["status"] == "available"}
        for module in ctx.config["modules"]:
            if module not in ready:
                ctx.failures.setdefault(
                    module, "Run interrupted. Start again to reuse completed work."
                )
        ctx.log("Stopped. Saving completed modules…")
    available = ctx.finish()
    ctx.log(
        f"Finished: {len(available)} of {len(ctx.config['modules'])} selected modules prepared."
    )
    if ctx.failures:
        ctx.log(
            "Read results/README.md for incomplete modules. Only completed modules can be analysed in the website."
        )
    return 2 if ctx.failures else 0
