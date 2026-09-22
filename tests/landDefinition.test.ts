import test from 'node:test';
import assert from 'node:assert/strict';
import { sourceCrosswalk } from '../src/online/landDefinition';

test('high source codes receive distinct targets without merging native classes',()=>{
  const rows=sourceCrosswalk([1,3,65534]);
  assert.deepEqual(rows.map(r=>r.code),[1,3,2]);
});
test('explicit legend merges persist while unmatched source classes stay separate',()=>{
  const legend=[10,11].map(source=>({source,code:1,name:'Cropland',color:'#deb85b'}));
  const rows=sourceCrosswalk([1,10,11,65534],[],legend);
  assert.equal(rows[1].code,rows[2].code);
  assert.notEqual(rows[0].code,1);
  assert.notEqual(rows[3].code,rows[0].code);
  assert.equal(rows[1].name,'Cropland');
});
