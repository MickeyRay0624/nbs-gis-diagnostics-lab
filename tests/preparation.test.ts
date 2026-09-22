import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {strToU8,unzipSync,zipSync} from 'fflate';
import {bboxBoundary,defaultJob,validateBoundary,validateJob,climateRequests} from '../src/preparation/config';
import {buildPythonPackage,unpackResultZip,validateResultFiles} from '../src/preparation/archive';
import {digest} from '../src/step2/io';

const boundary=bboxBoundary(85.75,20.15,85.95,20.35);
test('AOI geometry has finite equal-area size and rejects invalid limits',()=>{
  assert.ok(Math.abs(validateBoundary(boundary).areaKm2-462.672157711)<.01);
  assert.throws(()=>bboxBoundary(10,10,1,11),/West/);
  assert.throws(()=>bboxBoundary(-170,10,170,11),/date line/);
  assert.throws(()=>bboxBoundary(0,0,10,10),/50,000/);
});
test('configuration validates periods, overlapping seasons and selected outputs',()=>{
  const job=defaultJob();assert.equal(climateRequests(job),1080);assert.equal(validateJob(job,false),job);
  assert.throws(()=>validateJob({...job,modules:[]},false),/module/);
  assert.throws(()=>validateJob({...job,groundwater:{baseline:[2003,2015],monitoring:[2014,2023]}},false),/follow/);
  assert.throws(()=>validateJob({...job,drought:{...job.drought,reference:[2010,2023]}},false),/15 reference/);
  assert.throws(()=>validateJob({...job,drought:{...job.drought,seasons:[{name:'A',start:11,end:3},{name:'B',start:3,end:6}]}},false),/overlap/);
  assert.throws(()=>validateJob({...job,climate:{...job.climate,models:[]}},false),/models/);
  assert.throws(()=>validateJob({...job,flood:{returnPeriods:[10,10]}},false),/return period/);
});
test('download package is standalone, checksum-linked and keeps user values out of code',async()=>{
  const original=globalThis.fetch;
  globalThis.fetch=(async(input:string|URL|Request)=>{
    const path=String(input).replace('/local/','../public/');
    return new Response(await readFile(new URL(path,import.meta.url)));
  }) as typeof fetch;
  try{
    const job=defaultJob();job.name='Study "quoted"; $(echo never-run)';
    const bytes=await buildPythonPackage(job,boundary,'/local/');const files=unzipSync(bytes);
    assert.ok(files['run.py'] && files['Start Windows.bat'] && files['Start macOS.command'] && files['nbs_prepare/modules.py']);
    const config=JSON.parse(new TextDecoder().decode(files['config.json']));
    assert.equal(config.name,job.name);assert.equal(config.boundarySha256,await digest(files['aoi.geojson'].slice().buffer));
    assert.ok(!new TextDecoder().decode(files['run.py']).includes(job.name));
    assert.match(new TextDecoder().decode(files['Start Windows.bat']),/\r\n/);
  } finally {globalThis.fetch=original;}
});
test('result ZIP rejects paths, duplicate entries, oversized data and truncation',()=>{
  assert.throws(()=>unpackResultZip(zipSync({'../catalog.json':strToU8('{}')})),/top-level/);
  const padded=zipSync({'catalog.json':new Uint8Array(2_000_001)});assert.throws(()=>unpackResultZip(padded),/too large|memory/);
  const good=zipSync({'catalog.json':strToU8('{}'),'aoi.geojson':strToU8(JSON.stringify(boundary))});
  assert.ok(unpackResultZip(good)['aoi.geojson']);
  assert.throws(()=>unpackResultZip(good.subarray(0,55)),/incomplete|damaged|catalog/);
  // Rename a second same-length local header and central entry to duplicate the catalog.
  const duplicate=zipSync({'catalog.json':strToU8('{}'),'catalog.jsom':strToU8('{}')},{level:0});
  const marker=strToU8('catalog.jsom');for(let i=0;i<=duplicate.length-marker.length;i++)if(marker.every((v,j)=>duplicate[i+j]===v))duplicate[i+marker.length-1]='n'.charCodeAt(0);
  assert.throws(()=>unpackResultZip(duplicate),/unique/);
});
test('imports a new boundary and verifies every file, rejecting missing or tampered bytes',async()=>{
  const catalog=JSON.parse(await readFile(new URL('../public/data/step2/catalog.json',import.meta.url),'utf8'));
  const bytes=strToU8(JSON.stringify(boundary));catalog.studyArea={name:'New region',areaKm2:462.69,boundary:'aoi.geojson',sha256:await digest(bytes.slice().buffer)};
  catalog.rasters=[];catalog.sources=[];for(const m of catalog.modules){m.status='needs-data';m.layers=[];m.sources=[];delete m.series;}
  const files={'catalog.json':strToU8(JSON.stringify(catalog)),'aoi.geojson':bytes};
  const loaded=await validateResultFiles(files);assert.equal(loaded.catalog.studyArea.name,'New region');assert.deepEqual(loaded.aoi,boundary);
  await assert.rejects(()=>validateResultFiles({...files,'aoi.geojson':strToU8('{}')}),/checksum/);
  await assert.rejects(()=>validateResultFiles({'catalog.json':files['catalog.json']}),/Include the GeoJSON/);
});
