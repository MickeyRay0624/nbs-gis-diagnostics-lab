import assert from "node:assert/strict";
import { readFile, writeFile } from "node:fs/promises";
import { calculateLayer } from "../src/step2/compute";
import { readNumericRaster, validateCatalog, digest } from "../src/step2/io";
import type { NumericRaster, LayerSpec } from "../src/step2/model";
const root = new URL("../public/data/step2/", import.meta.url);
const read = async (name: string) => JSON.parse(await readFile(new URL(name, root), "utf8"));
const buffer = async (name: string) => {const bytes=await readFile(new URL(name,root));return bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength) as ArrayBuffer;};
const catalog = validateCatalog(await read("catalog.json"));
const rasters = new Map<string,NumericRaster>();let checks=0;
const close = (a:number|null,b:number|null,label:string) => {if(a===null||b===null)assert.equal(a,b,label);else assert.ok(Math.abs(a-b)<=Math.max(1e-6,Math.abs(b)*2e-7),`${label}: ${a} vs ${b}`);checks++;};
for (const asset of catalog.rasters) {
  const raster=await readNumericRaster(await buffer(asset.file),asset);rasters.set(asset.id,raster);
  const ref=await read(`${asset.id}-reference.json`);
  for(let band=1;band<=ref.length;band++) {
    const spec:LayerSpec={id:"reference",title:"Reference",unit:"native",period:"source",operation:"identity",inputs:[{raster:asset.id,band}],palette:"sequential",interpretation:"Python reference comparison"};
    const layer=calculateLayer(spec,rasters);
    for(const key of ["mean","min","max","validAreaKm2"] as const)close(layer.stats[key],ref[band-1][key],`${asset.id} ${band} ${key}`);
  }
}
const report:any={status:"pass",catalog_sha256:await digest(await buffer("catalog.json")),modules:[],checks:0,limitation:"Independent arithmetic and package validation; not field validation or expert acceptance."};
for (const module of catalog.modules) {
  if(!module.layers.length)continue;
  const outputs=[];
  for(const spec of module.layers) {
    const result=calculateLayer(spec,rasters);
    assert.ok(result.stats.validAreaKm2>0,`${spec.id}: no usable data`);
    if(spec.categories||spec.thresholds)close(result.stats.classes.reduce((sum,c)=>sum+c.areaKm2,0),result.stats.validAreaKm2,`${spec.id} class-area conservation`);
    if(spec.operation==="difference") {
      const a=rasters.get(spec.inputs[0].raster)!.bands[spec.inputs[0].band-1],b=rasters.get(spec.inputs[1].raster)!.bands[spec.inputs[1].band-1];
      for(let i=0;i<result.values.length;i++)if(result.areas[i]>0) {
        const expected=Number.isFinite(a[i])&&Number.isFinite(b[i])?Math.fround(b[i]-a[i]):NaN;
        assert.ok(Object.is(result.values[i],expected),`${spec.id} common-footprint difference at ${i}`);
      }
      checks++;
    }
    outputs.push({id:spec.id,validAreaKm2:result.stats.validAreaKm2,coveragePct:result.stats.coveragePct,mean:spec.categories?null:result.stats.mean});
  }
  report.modules.push({id:module.id,layers:outputs});
}
report.checks=checks;
await writeFile(new URL("validation.json",root),JSON.stringify(report,null,2)+"\n");
console.log(JSON.stringify({status:report.status,checks,modules:report.modules.map((m:any)=>({id:m.id,layers:m.layers.length}))},null,2));
