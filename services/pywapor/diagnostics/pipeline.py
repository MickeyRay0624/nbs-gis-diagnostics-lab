"""Recompute reference inputs or acquire and prepare a new area on the server."""
import csv
import gc
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import traceback

import numpy as np
import rasterio
from rasterio.features import rasterize
from shapely.geometry import mapping

from nbs_prepare.core import Context, NoValidDataError, json_bytes, atomic, read_boundary, grid_for
from nbs_prepare.modules import RUNNERS
from nbs_prepare.sources import DownloadBudgetExceeded, crop_cog
from nbs_gis.fragmentation import classify_forest

from .models import DiagnosticRequest, MODULES
from .results import Publisher, calculate, sha_file

REFERENCE = Path(os.getenv("NBS_REFERENCE_DIR","/app/reference"))
WORLD = [(10,"Tree cover","#006400"),(20,"Shrubland","#ffbb22"),(30,"Grassland","#ffff4c"),(40,"Cropland","#f096ff"),(50,"Built-up","#fa0000"),(60,"Bare / sparse vegetation","#b4b4b4"),(70,"Snow and ice","#f0f0f0"),(80,"Permanent water bodies","#0064c8"),(90,"Herbaceous wetland","#0096a0"),(95,"Mangroves","#00cf75"),(100,"Moss and lichen","#fae6a0")]
FRAGMENT = [(0,"Non-forest","#efede2"),(1,"Patch","#d64233"),(2,"Edge","#e6ab36"),(3,"Internal clearing","#b752a3"),(4,"Core","#286845")]


def stage(folder, text):
    atomic(Path(folder) / "stage.json",json_bytes({"stage":text}))
    print(text,flush=True)


def no_observations_message(module, request):
    if module == "flood":
        periods = ", ".join(f"RP{p}" for p in request["config"]["flood"]["returnPeriods"])
        return (
            f"The source files were read successfully, but no usable river-flood data overlaps this study area for {periods}. "
            "This is a data-coverage result, not an account or sign-in error. "
            "Missing data cannot establish that flood risk is zero. Check the boundary, try a broader study area, "
            "or select another return period if it suits your analysis."
        )
    return "The source files were read successfully, but no valid observations overlap the eligible study area. Check the boundary, selected period and land mask. Missing data remains unknown; it has not been replaced with zero."


def numeric(publisher, catalog, base, module_id):
    module = next(m for m in catalog["modules"] if m["id"] == module_id)
    if module["status"] != "available":
        raise ValueError("The selected diagnostic has no prepared inputs.")
    needed = {r["raster"] for l in module["layers"] for r in l["inputs"]}
    rasters = {}
    for asset in catalog["rasters"]:
        if asset["id"] not in needed:continue
        p = base / asset["file"]
        if sha_file(p) != asset["sha256"]:
            raise ValueError("Input checksum changed.")
        with rasterio.open(p) as src:
            a = src.read(masked=True).astype("float32").filled(np.nan)
            g=asset["grid"]
            if src.width!=g["width"] or src.height!=g["height"] or src.crs.to_epsg()!=g["crs"] or not np.allclose([src.transform.c,src.transform.f,src.transform.a,-src.transform.e],[g[k] for k in ("left","top","dx","dy")],rtol=0,atol=1e-7):
                raise ValueError("Input grid disagrees with its catalog.")
            rasters[asset["id"]]=(a,src.transform,src.crs,asset)
    for spec in module["layers"]:
        arrays,transform,crs,asset = rasters[spec["inputs"][0]["raster"]]
        weights=arrays[asset["areaBand"]-1]
        for ref in spec["inputs"]:
            other,ot,oc,oa=rasters[ref["raster"]]
            if ot != transform or oc != crs or not np.array_equal(other[oa["areaBand"]-1],weights):
                raise ValueError("Compared grids must use identical area weights.")
        values=calculate(spec,[rasters[i["raster"]][0][i["band"]-1] for i in spec["inputs"]])
        publisher.add(module_id,spec,values,weights,transform,crs,asset["nativeResolution"])
    publisher.modules.append(module)
    for source in catalog["sources"]:
        if source["id"] in module["sources"]:publisher.source(source)


def layer_spec(id,title,period,categories=None,interpretation=""):
    result=dict(id=id,title=title,period=str(period),unit="class",operation="identity",inputs=[],palette="sequential",interpretation=interpretation)
    if categories is not None:result["categories"]=[dict(value=c,label=n,color=color) for c,n,color in categories]
    return result


def land_cover(publisher, request, ctx=None):
    from .land import run_land
    return run_land(publisher, request, REFERENCE, ctx)


def run(folder):
    folder=Path(folder);request=DiagnosticRequest.model_validate_json((folder / "request.json").read_text()).model_dump(mode="json")
    if request["mode"] == "ganjam":
        boundary=json.loads((REFERENCE / "ganjam-aoi.geojson").read_text())
        scope="Existing Ganjam source inputs and published periods are reused. All displayed layers, land-cover comparisons, forest structure and area statistics are recalculated on this server. No fresh authenticated NASA acquisition is claimed."
        ctx=None
    else:
        boundary=request["boundary"]
        scope="New-area source acquisition and all diagnostic calculations run on this server. Each module retains its own source dates, units, resolution and missing-data rules."
        model=folder / "model";model.mkdir(exist_ok=True)
        (model / "aoi.geojson").write_bytes(json_bytes(boundary))
        config=request["config"].copy();config["boundarySha256"]=hashlib.sha256((model / "aoi.geojson").read_bytes()).hexdigest()
        (model / "config.json").write_bytes(json_bytes(config))
        if os.getenv("NBS_NASA_USERNAME"):
            os.environ["EARTHDATA_USERNAME"]=os.environ["NBS_NASA_USERNAME"]
            os.environ["EARTHDATA_PASSWORD"]=os.environ.get("NBS_NASA_PASSWORD","")
        ctx=Context(model)
        ctx.server_mode=True
        ctx.log=lambda message:stage(folder,str(message).replace("local", "server"))
    publisher=Publisher(folder,request,boundary,scope)
    if set(request["modules"]) & {"lulc","fragmentation"}:
        stage(folder,"Calculating land-cover change and forest structure")
        try:land_cover(publisher,request,ctx)
        except Exception:
            traceback.print_exc()
            for mid in ("lulc","fragmentation"):
                if mid in request["modules"] and not any(m["id"]==mid for m in publisher.modules):
                    publisher.layers=[l for l in publisher.layers if l["module"] != mid]
                    publisher.modules.append(dict(id=mid,title=MODULES[mid],status="needs-data",missing=["This diagnostic could not complete. Ask the administrator to check source coverage and the private task log."]))
        gc.collect()
    for mid in request["modules"]:
        if mid in ("lulc","fragmentation"):continue
        stage(folder,"Calculating " + MODULES[mid])
        before=len(publisher.layers)
        try:
            if ctx is None:
                catalog=json.loads((REFERENCE / "step2/catalog.json").read_text());base=REFERENCE / "step2"
            else:
                RUNNERS[mid](ctx);catalog=ctx.catalog;base=ctx.out
            numeric(publisher,catalog,base,mid)
        except Exception as exc:
            traceback.print_exc()
            publisher.layers=publisher.layers[:before]
            no_data = isinstance(exc, NoValidDataError)
            message = no_observations_message(mid, request) if no_data else str(exc) if isinstance(exc, DownloadBudgetExceeded) else "This diagnostic could not complete. Ask the administrator to check source coverage, data access and the private task log."
            if no_data:
                atomic(folder / "source-error.json", json_bytes({"code":"no_valid_flood_observations" if mid == "flood" else "no_valid_observations"}))
            elif isinstance(exc, DownloadBudgetExceeded):
                atomic(folder / "source-error.json", json_bytes({"code":exc.code}))
            publisher.modules.append(dict(id=mid,title=MODULES[mid],status="needs-data",missing=[message],**({"reason_code":"no_valid_observations"} if no_data else {})))
        gc.collect()
    # Remove files from any failed module before publishing; retain completed modules.
    keep={l["file"] for l in publisher.layers}
    completed={m["id"] for m in publisher.modules if m["status"]=="available"}
    publisher.rows=[r for r in publisher.rows if r["module"] in completed]
    publisher.checks=[r for r in publisher.checks if r["module"] in completed]
    for table in publisher.tables:
        if table["module"] not in completed:(publisher.out / table["file"]).unlink(missing_ok=True)
    publisher.tables=[t for t in publisher.tables if t["module"] in completed]
    source_ids={s for m in publisher.modules if m["id"] in completed for s in m.get("sources",[])}
    publisher.sources={k:v for k,v in publisher.sources.items() if k in source_ids}
    publisher.modules.sort(key=lambda m:list(MODULES).index(m["id"]))
    for p in publisher.out.glob("*.tif"):
        if p.name not in keep:p.unlink()
    stage(folder,"Validating and publishing result files")
    result=publisher.finish()
    stage(folder,"Results ready" if result["complete"] else "Some diagnostics completed")


if __name__ == "__main__":run(sys.argv[1])
