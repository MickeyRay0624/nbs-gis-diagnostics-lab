import test from 'node:test';
import assert from 'node:assert/strict';
import {analysisBrief,briefHtml} from '../src/online/brief';
import type {Analysis} from '../src/online/workflow';
test('unified brief distinguishes failed, pending and unselected modules and escapes user text',()=>{
  const analysis={id:'fixture',name:'<script>alert(1)</script>',modules:['lulc','water'],children:[{kind:'water',modules:['water'],job:{status:'failed',error:'No model output'}}],cancel_requested:false} as Analysis;
  const brief=analysisBrief(analysis,null,null),html=briefHtml(brief);
  assert.match(brief,/\| Land-cover change \| Queued \|/);
  assert.match(brief,/\| Forest fragmentation \| Not selected \|/);
  assert.match(brief,/\| Water & productivity \| failed \|/);
  assert.match(brief,/No model output/);
  assert.ok(!html.includes('<script>'));
  assert.ok(html.includes('&lt;script&gt;'));
});
