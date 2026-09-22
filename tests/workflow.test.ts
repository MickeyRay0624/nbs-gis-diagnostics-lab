import test from 'node:test';
import assert from 'node:assert/strict';
import { buildAnalysis, fayoumBoundary, FAYOUM, MODULES } from '../src/online/workflow';
import { defaultJob, bboxBoundary } from '../src/preparation/config';
const input=()=>({preset:'fayoum' as const,name:'Fayoum combined',boundary:fayoumBoundary(),modules:MODULES.map(m=>m.id),config:{...defaultJob(),climate:{...defaultJob().climate,models:['ACCESS-CM2'],scenarios:['ssp245'],metrics:['hot' as const,'rain' as const,'dry' as const]}},land:{resolution:50 as const,edge_width_m:50,include_mangroves:true,count_boundary_as_edge:false},waterDates:{start:'2024-01-01',end:'2024-01-02'},waterCustom:false,waterReady:true,maxClimateRequests:240});

test('all eight share the Fayoum boundary and keep verified water dates',()=>{
  const r=buildAnalysis(input());
  assert.equal(r.diagnostics?.modules.length,7);
  assert.equal(r.diagnostics?.mode,'custom');
  assert.deepEqual(r.diagnostics?.boundary,fayoumBoundary());
  assert.equal(r.water?.start,FAYOUM.start);
  assert.equal(r.water?.end,FAYOUM.end);
  assert.equal(r.water?.name,r.diagnostics?.name);
});
test('water cannot silently reuse inputs from a different study area or bypass access gates',()=>{
  assert.throws(()=>buildAnalysis({...input(),preset:'ganjam'}),/different|Ganjam/);
  assert.throws(()=>buildAnalysis({...input(),preset:'custom'}),/awaiting verification/);
  assert.throws(()=>buildAnalysis({...input(),waterReady:false}),/being prepared/);
});
test('one shared custom polygon is transmitted once and water-only runs retain it',()=>{
  const boundary=bboxBoundary(31,29,31.1,29.1),i={...input(),preset:'custom' as const,boundary,waterCustom:true};
  const all=buildAnalysis(i),waterOnly=buildAnalysis({...i,modules:['water']});
  assert.deepEqual(all.diagnostics?.boundary,boundary);
  assert.equal(all.water?.boundary,undefined);
  assert.deepEqual(waterOnly.water?.boundary,boundary);
  assert.deepEqual(waterOnly.water?.bbox,[31,29,31.1,29.1]);
});
test('invalid empty selections and water limits are rejected before submission',()=>{
  assert.throws(()=>buildAnalysis({...input(),modules:[]}),/at least one/);
  assert.throws(()=>buildAnalysis({...input(),preset:'custom',waterCustom:true,waterDates:{start:'2024-01-01',end:'2024-03-01'}}),/31 days/);
  assert.throws(()=>buildAnalysis({...input(),preset:'custom',waterCustom:true,boundary:bboxBoundary(30,28,32,30)}),/500 km/);
});

test('custom landscape definitions remain attached to Ganjam requests',()=>{
  const land={...input().land,years:[2002,2022],crosswalk:[{source:51,code:999,name:'Forest',color:'#228844'}],forest_codes:[999],protected_upload_id:'a'.repeat(32)};
  const r=buildAnalysis({...input(),preset:'ganjam',modules:['lulc','fragmentation'],land});
  assert.deepEqual(r.diagnostics?.land_cover,land);
  assert.throws(()=>buildAnalysis({...input(),preset:'ganjam',modules:['lulc'],land:{...land,years:[2012]}}),/distinct years/);
  assert.throws(()=>buildAnalysis({...input(),modules:['fragmentation'],land:{...land,forest_codes:[2]}}),/forest/);
});
