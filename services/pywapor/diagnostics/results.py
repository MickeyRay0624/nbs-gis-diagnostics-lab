import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import zipfile

import numpy as np
import rasterio
from rasterio.shutil import copy as copy_raster

from nbs_prepare.core import json_bytes, statistics


def sha_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda:f.read(1024*1024), b""):
            h.update(block)
    return h.hexdigest()


def calculate(spec, inputs):
    if spec["operation"] == "identity":
        return inputs[0].copy()
    if spec["operation"] == "difference":
        return (inputs[1] - inputs[0]).astype("float32")
    if spec["operation"] == "percent-change":
        out = np.full(inputs[0].shape, np.nan, dtype="float32")
        np.divide((inputs[1]-inputs[0])*100, np.abs(inputs[0]), out=out, where=np.isfinite(inputs).all(axis=0) & (inputs[0] != 0))
        return out
    if spec["operation"] == "one-out-all-out":
        v = np.stack(inputs)
        if not np.isin(v[np.isfinite(v)],[-1,0,1]).all():
            raise ValueError("Unexpected degradation class.")
        out = np.where(np.any(v == 1,axis=0),1.0,0.0).astype("float32")
        out[~np.isfinite(v).all(axis=0)] = np.nan
        out[np.any(v == -1,axis=0)] = -1
        return out
    raise ValueError("Unsupported calculation.")


class Publisher:
    def __init__(self, folder, request, boundary, scope):
        self.folder = Path(folder)
        self.out = self.folder / "results"
        self.out.mkdir(exist_ok=True)
        self.request = request
        self.modules, self.layers, self.sources, self.checks, self.tables = [], [], {}, [], []
        self.boundary = boundary
        self.scope = scope
        self.rows = []
        (self.out / "boundary.geojson").write_bytes(json_bytes(boundary))

    def add(self, module, spec, values, weights, transform, crs, native_resolution):
        values = np.asarray(values,dtype="float32").copy()
        weights = np.asarray(weights,dtype="float32")
        if values.shape != weights.shape or values.size > 8_000_000 or not np.isfinite(weights).all() or (weights < 0).any():
            raise ValueError("Invalid result grid or area weights.")
        values[weights <= 0] = np.nan
        if np.isinf(values).any():
            raise ValueError("Result contains infinite values.")
        stats = statistics(values,weights)
        valid = np.isfinite(values) & (weights > 0)
        stats["cells"] = int(valid.sum())
        stats["classes"] = []
        if spec.get("categories") and not np.isin(values[valid],[c["value"] for c in spec["categories"]]).all():
            raise ValueError("Result contains an undeclared class.")
        for c in spec.get("categories",spec.get("thresholds",[])):
            selected = values == c["value"] if "value" in c else (values >= c.get("min",-np.inf)) & (values < c.get("max",np.inf))
            area = float(weights[valid & selected].sum(dtype="float64"))
            stats["classes"].append({"label":c["label"],"areaKm2":area,"percent":100*area/stats["validAreaKm2"] if stats["validAreaKm2"] else None})
        file_id = re.sub(r"[^A-Za-z0-9_-]","-",module+"-"+spec["id"])
        if any(l["id"] == file_id for l in self.layers):
            raise ValueError("Duplicate layer identifier.")
        h,w = values.shape
        profile = dict(driver="GTiff",width=w,height=h,count=2,dtype="float32",crs=crs,transform=transform,nodata=np.nan,compress="deflate",predictor=3,tiled=True)
        temp = self.out / (file_id + ".tmp.tif")
        target = self.out / (file_id + ".tif")
        with rasterio.open(temp,"w",**profile) as dst:
            dst.write(values,1);dst.write(weights,2)
            dst.descriptions = (spec["title"],"Eligible area (km2)")
        copy_raster(temp,target,driver="COG",compress="DEFLATE",blocksize=256,overview_resampling="NEAREST")
        temp.unlink()
        with rasterio.open(target) as check:
            if not np.array_equal(values,check.read(1),equal_nan=True) or not np.array_equal(weights,check.read(2)) or check.tags(ns="IMAGE_STRUCTURE").get("LAYOUT") != "COG":
                raise ValueError("Result raster round trip failed.")
        grid = dict(width=w,height=h,crs=rasterio.crs.CRS.from_user_input(crs).to_epsg(),left=transform.c,top=transform.f,dx=transform.a,dy=-transform.e)
        self.layers.append(dict(id=file_id,module=module,spec=spec,file=target.name,grid=grid,stats=stats,nativeResolution=native_resolution))
        self.checks.append({"module":module,"layer":file_id,"check":"COG values, NoData, grid and area-band round trip","passed":True})
        self.rows.append(dict(module=module,layer=spec["title"],period=spec["period"],unit=spec["unit"],**{k:v for k,v in stats.items() if k != "classes"}))

    def source(self, source):
        self.sources[source["id"]] = source

    def table(self, module, title, filename, rows):
        if not rows:
            return
        self.tables.append(dict(module=module,title=title,file=filename,rows=rows))
        with (self.out / filename).open("w",newline="") as f:
            writer = csv.DictWriter(f,fieldnames=list(rows[0]))
            writer.writeheader(); writer.writerows(rows)

    def finish(self):
        if not self.layers:
            raise RuntimeError("No diagnostic completed.")
        complete = all(m["status"] == "available" for m in self.modules)
        validation = dict(status="passed",checks=len(self.checks),complete=complete,completed_modules=[m["id"] for m in self.modules if m["status"] == "available"],checks_detail=self.checks,
                          interpretation="These checks verify data and arithmetic, not field accuracy or causal effects.")
        (self.out / "validation.json").write_bytes(json_bytes(validation))
        with (self.out / "statistics.csv").open("w",newline="") as f:
            writer=csv.DictWriter(f,fieldnames=list(self.rows[0]));writer.writeheader();writer.writerows(self.rows)
        prepared = datetime.now(timezone.utc).isoformat()
        result = dict(schema="nbs-online-diagnostics/v1",name=self.request["name"],prepared_at=prepared,complete=complete,scope=self.scope,
                      boundary=self.boundary,modules=self.modules,layers=self.layers,sources=list(self.sources.values()),tables=self.tables,validation={k:v for k,v in validation.items() if k != "checks_detail"})
        (self.out / "run-manifest.json").write_bytes(json_bytes(dict(request=self.request,prepared_at=prepared,scope=self.scope,sources=result["sources"],modules=self.modules,review="Technical screening; expert review pending.")))
        (self.out / "README.txt").write_text("NBS server-generated diagnostic results\n\n" + self.scope + "\n\nEach COG contains the result in band 1 and eligible pixel area (km2) in band 2. NoData remains unknown. Only modules marked available completed. All calculations and statistics ran on the server; the browser displays these results.\n\nSee run-manifest.json for methods, source versions and interpretation limits. Result validation does not establish environmental truth.\n")
        media={".tif":"image/tiff",".csv":"text/csv",".json":"application/json",".geojson":"application/geo+json",".txt":"text/plain",".zip":"application/zip"}
        def asset(p):
            return dict(file=p.name,bytes=p.stat().st_size,sha256=sha_file(p),media_type=media[p.suffix])
        result["assets"]=[asset(p) for p in sorted(self.out.iterdir()) if p.suffix in media and p.name not in ("result.json","results.zip")]
        (self.out / "result.json").write_bytes(json_bytes(result))
        with zipfile.ZipFile(self.out / "results.zip","w",zipfile.ZIP_DEFLATED) as z:
            for p in sorted(self.out.iterdir()):
                if p.name != "results.zip":z.write(p,p.name)
        result["assets"].append(asset(self.out / "results.zip"))
        (self.out / "result.json").write_bytes(json_bytes(result))
        return result
