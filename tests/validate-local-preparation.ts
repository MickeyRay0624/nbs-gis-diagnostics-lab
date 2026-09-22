import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {importResults} from '../src/preparation/archive';
import {readNumericRaster} from '../src/step2/io';
import {calculateLayer} from '../src/step2/compute';
import type {NumericRaster} from '../src/step2/model';
const folder=resolve(process.argv[2]??'engine/outputs/localprep-bhubaneswar');
const zip=await readFile(resolve(folder,'results.zip'));
const loaded=await importResults([new File([Uint8Array.from(zip).buffer],'results.zip')]);
const reference=JSON.parse(await readFile(resolve(folder,'results/validation.json'),'utf8'));
let checks=0,layers=0;const rasters=new Map<string,NumericRaster>();
for(const asset of loaded.catalog.rasters)rasters.set(asset.id,await readNumericRaster(await loaded.files[asset.file].arrayBuffer(),asset));
for(const module of loaded.catalog.modules)for(const spec of module.layers){
 const result=calculateLayer(spec,rasters);const row=reference.statistics.find((r:{module:string;layer:string})=>r.module===module.id&&r.layer===spec.title);assert.ok(row);
 for(const key of ['mean','min','max','validAreaKm2','eligibleAreaKm2','missingAreaKm2','coveragePct'] as const){
  const a=result.stats[key],b=row[key];if(a===null||b===null)assert.equal(a,b);else assert.ok(Math.abs(a-b)<=Math.max(1e-5,Math.abs(b)*2e-6),`${spec.id} ${key}: ${a} vs ${b}`);checks++;
 }
 if(spec.categories||spec.thresholds){const sum=result.stats.classes.reduce((a,v)=>a+v.areaKm2,0);assert.ok(Math.abs(sum-result.stats.validAreaKm2)<1e-5);checks++;}
 layers++;
}
const report={status:'pass',studyArea:loaded.catalog.studyArea,modules:reference.available,checks,layers,method:'Imported the ZIP through the website parser, verified input hashes and GeoTIFF grids, and compared every browser layer statistic with the independently calculated Python output.',limitations:'Arithmetic and package checks only; not field validation or expert acceptance.'};
await writeFile(resolve(folder,'browser-validation.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report,null,2));
