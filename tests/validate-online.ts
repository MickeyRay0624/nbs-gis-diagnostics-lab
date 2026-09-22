import assert from "node:assert/strict";
import { readFile, writeFile } from "node:fs/promises";
import { resolve, join } from "node:path";
import { calculateLayer } from "../src/step2/compute";
import { readNumericRaster, validateCatalog, digest } from "../src/step2/io";
import { readOnlineLayer, type DiagnosticResult } from "../src/online/client";
import type { NumericRaster } from "../src/step2/model";

const folder=resolve(process.argv[2]);
const manifest:DiagnosticResult=JSON.parse(await readFile(join(folder,"result.json"),"utf8"));
const reference=process.argv.includes("--ganjam");
const buffer=async(path:string)=>{const b=await readFile(path);return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength) as ArrayBuffer;};
const catalog=validateCatalog(JSON.parse(await readFile("public/data/step2/catalog.json","utf8")));
const original=new Map<string,NumericRaster>();
const forest=JSON.parse(await readFile("public/data/glcfcs/python-reference.json","utf8"));
if(reference)for(const a of catalog.rasters)original.set(a.id,await readNumericRaster(await buffer(join("public/data/step2",a.file)),a));
let checks=0,pixels=0;
function close(a:number|null,b:number|null,label:string){
  if(a===null||b===null)assert.equal(a,b,label);
  else assert.ok(Math.abs(a-b)<=Math.max(1e-6,Math.abs(b)*3e-7),`${label}: ${a} vs ${b}`);
  checks++;
}
for(const a of manifest.assets){
  const bytes=await buffer(join(folder,a.file));
  assert.equal(bytes.byteLength,a.bytes,a.file+" size");
  assert.equal(await digest(bytes),a.sha256,a.file+" checksum");checks+=2;
}
for(const online of manifest.layers){
  const a=manifest.assets.find(a=>a.file===online.file)!;
  const layer=await readOnlineLayer(await buffer(join(folder,online.file)),online,a);
  const asset={id:"result",file:a.file,sha256:a.sha256,source:"online",grid:layer.grid,bands:["Result","Area"],areaBand:2,nativeResolution:online.nativeResolution,processing:"server"};
  const recomputed=calculateLayer({...layer.spec,operation:"identity",inputs:[{raster:"result",band:1}]},new Map([["result",{asset,grid:layer.grid,bands:[layer.values,layer.areas]}]]));
  for(const key of ["mean","min","max","validAreaKm2","eligibleAreaKm2","missingAreaKm2","coveragePct","cells"] as const)close(online.stats[key],recomputed.stats[key],online.id+" "+key);
  for(let i=0;i<online.stats.classes.length;i++)for(const key of ["areaKm2","percent"] as const)close(online.stats.classes[i][key],recomputed.stats.classes[i][key],online.id+" class "+key);
  if(reference&&!["lulc","fragmentation"].includes(online.module)){
    const spec=catalog.modules.find(m=>m.id===online.module)!.layers.find(l=>l.id===online.spec.id)!;
    const expected=calculateLayer(spec,original);
    assert.equal(layer.values.length,expected.values.length);
    for(let i=0;i<layer.values.length;i++)assert.ok(Object.is(layer.values[i],expected.values[i]),`${online.id} pixel ${i}`);
    pixels+=layer.values.length;checks++;
  }
  if(reference&&online.module==="fragmentation"){
    const year=online.spec.period;
    const categorical=Uint8Array.from(layer.values,v=>Number.isFinite(v)?v:255);
    assert.equal(await digest(categorical.buffer),forest.fragmentation_pixel_sha256[year],"Forest map "+year);
    pixels+=categorical.length;checks++;
  }
  if(reference&&online.module==="lulc"&&online.spec.id.startsWith("cover-")){
    for(const c of forest.class_area_by_year.filter((c:{year:number})=>String(c.year)===online.spec.period)){
      const position=online.spec.categories!.findIndex(x=>x.value===c.class_code);
      close(online.stats.classes[position].areaKm2,c.area_ha/100,`Land class ${c.class_code} in ${c.year}`);
    }
  }
}
if(reference){
  for(const table of manifest.tables.filter(t=>t.module==="fragmentation"))for(const row of table.rows){
    const expected=forest.fragmentation.find((r:{year:number;stratum:string})=>r.year===row.year&&r.stratum===row.stratum);
    for(const [key,value] of Object.entries(row))if(typeof value==="number")close(value,expected[key],`Forest metric ${key} in ${row.year}`);
  }
}
const report={status:"pass",checks,pixels_compared:pixels,layers:manifest.layers.length,modules:manifest.validation.completed_modules,reference_comparison:reference,limitation:"Independent file, arithmetic and pixel agreement; not field validation."};
await writeFile(join(folder,"independent-verification.json"),JSON.stringify(report,null,2)+"\n");
console.log(JSON.stringify(report,null,2));
