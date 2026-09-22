import type { DiagnosticResult } from './client';
import type { WaterResult } from '../water/client';
import { MODULES, type Analysis } from './workflow';
const text=(v:unknown)=>String(v??'Not available').replaceAll('|','\\|').replaceAll('\n',' ');
const num=(v:number|null|undefined)=>v==null?'Missing':v.toLocaleString('en',{maximumFractionDigits:2});
export function analysisBrief(analysis:Analysis,d:DiagnosticResult|null,w:WaterResult|null){
  const lines=[`# ${text(analysis.name)}`,`NbS Diagnostics Lab · unified analysis brief`, `Analysis: ${analysis.id} · snapshot: ${new Date().toISOString()}`, '',
    'This brief combines the selected diagnostics without treating their dates, resolutions or indicators as interchangeable. Computational checks verify processing, not environmental accuracy or causal effects.',
    '', '| Diagnostic | Status |','| --- | --- |'];
  for(const m of MODULES){
    const selected=analysis.modules.includes(m.id),child=analysis.children.find(c=>c.kind===(m.id==='water'?'water':'diagnostics'))?.job,dm=d?.modules.find(x=>x.id===m.id);
    const state=!selected?'Not selected':m.id==='water'&&w?'Complete':dm?dm.status==='available'?'Complete':dm.missing?.join(' ')??'Not completed':child?.status==='succeeded'||child?.status==='partial'?'Result metadata not loaded':child?.status??(analysis.cancel_requested?'Cancelled':'Queued');
    lines.push(`| ${m.title} | ${text(state)} |`);
  }
  if(d?.land){
    const l=d.land;lines.push('','## Landscape definition',`Years: ${l.years.join(', ')}. Analysis grid: EPSG:6933, ${l.resolution_m} m. Nearest-neighbour sampling does not improve native source detail.`,
      `Forest target codes: ${l.forest_codes.join(', ')||'None selected'}. Edge width: ${l.edge_width_m} m. Count boundary / unknown-data edges: ${l.count_boundary_as_edge?'yes':'no'}.`,
      l.protection_method,text(l.protection_note||'No additional protection coverage note supplied.'),
      '', '| Source code | Target code | Target class | Forest |','| --- | --- | --- | --- |');
    for(const r of l.crosswalk)lines.push(`| ${r.source} | ${r.code} | ${text(r.name)} | ${l.forest_codes.includes(r.code)?'Yes':'No'} |`);
    if(l.inputs.length){lines.push('','### Input fingerprints','| Role / year | File | SHA-256 |','| --- | --- | --- |');for(const f of l.inputs)lines.push(`| ${f.role} ${f.year??''} | ${text(f.name)} | ${f.sha256} |`);}
  }
  for(const m of MODULES.filter(x=>analysis.modules.includes(x.id))){
    lines.push('',`## ${m.title}`);
    if(m.id==='water'){
      if(!w){const child=analysis.children.find(c=>c.kind==='water')?.job;lines.push(text(child?.error||`No result available; status: ${child?.status??'queued'}.`));continue;}
      lines.push(text(w.model),text(w.scope),...w.notes.map(n=>`- ${text(n)}`),'', '| Layer | Period | Mean | Unit | Coverage (%) |','| --- | --- | --- | --- | --- |');
      for(const l of w.layers){const p=w.periods.find(p=>p.id===l.period);lines.push(`| ${text(l.title)} | ${p?.start} – ${p?.end} | ${num(l.stats.mean)} | ${text(l.unit)} | ${num(l.stats.coveragePct)} |`);}
      lines.push('NPP is carbon productivity, not crop yield. Root-zone wetness is a relative model indicator, not a direct measurement of volumetric soil water.');continue;
    }
    const module=d?.modules.find(x=>x.id===m.id);
    if(!module){const child=analysis.children.find(c=>c.kind==='diagnostics')?.job;lines.push(text(child?.error||`No result metadata available; status: ${child?.status??'queued'}.`));continue;}
    if(module.status!=='available'){lines.push(...(module.missing??['Not completed.']).map(text));continue;}
    lines.push(...(module.method??[]).map(n=>`- ${text(n)}`),...(module.limitations??[]).map(n=>`- ${text(n)}`));
    for(const source of d!.sources.filter(s=>module.sources?.includes(s.id)))lines.push(`Source: ${text(source.name)} · ${text(source.version)} · ${text(source.licence)}. ${source.url??''}`);
    lines.push('','| Layer | Period | Mean / classified area | Unit | Coverage (%) | Native scale |','| --- | --- | --- | --- | --- | --- |');
    for(const l of d!.layers.filter(x=>x.module===m.id))lines.push(`| ${text(l.spec.title)} | ${text(l.spec.period)} | ${num(l.spec.categories?l.stats.validAreaKm2:l.stats.mean)} | ${l.spec.categories?'km² classified':text(l.spec.unit)} | ${num(l.stats.coveragePct)} | ${text(l.nativeResolution)} |`);
    if(m.id==='lulc'){
      const rows=d!.tables.find(t=>t.file==='land-cover-balance.csv')?.rows.filter(r=>r.stratum==='All')??[];
      if(rows.length){lines.push('','### Change on common valid coverage','| Period | Class | Gross gain (ha) | Gross loss (ha) | Net (ha) | Common area (ha) |','| --- | --- | --- | --- | --- | --- |');for(const r of rows)lines.push(`| ${r.start_year}–${r.end_year} | ${text(r.class_name)} | ${num(Number(r.gross_gain_ha))} | ${num(Number(r.gross_loss_ha))} | ${num(Number(r.net_ha))} | ${num(Number(r.common_valid_ha))} |`);}
    }
    if(m.id==='fragmentation'){
      const rows=d!.tables.find(t=>t.file==='forest-metrics.csv')?.rows??[];
      if(rows.length){lines.push('','### Forest groups','| Year | Group | Forest (ha) | Core (ha) | Patches | Total edge (km) |','| --- | --- | --- | --- | --- | --- |');for(const r of rows)lines.push(`| ${r.year} | ${text(r.stratum)} | ${num(Number(r.forest_ha))} | ${num(Number(r.core_ha))} | ${r.NP} | ${num(r.TE_km!=null?Number(r.TE_km):Number(r.TE_m)/1000)} |`);}
    }
  }
  lines.push('','## Interpretation and comparison checklist',
    '- Do not replace missing observations with zero. Compare change only over common valid coverage.',
    '- The submitted boundary, protection polygons, crosswalk, forest definition, source versions and periods control the answer. Record them before comparing another assessment.',
    '- Obtain the original AOI, rasters, class crosswalk, forest/protection definitions, GEE/ArcPy scripts, grid alignment, climate scenarios and thresholds, and expected output tables/maps. See the repository method-differences table.',
    '- This brief is a snapshot: unselected, queued, failed, expired and missing-data modules are distinguished above. It does not claim that all eight modules completed.',
    '- Download the module result ZIPs for rasters, matrices, full metrics, source records and run manifests. Keep the original uploaded input files; they are not copied into the result ZIP.',
    '',`Recorded computational checks: diagnostics ${d?.validation.checks??'not available'}; water ${w?.validation.checks??'not available'}.`);
  return lines.join('\n');
}
const escape=(s:string)=>s.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));
export function briefHtml(markdown:string){
  // A deliberately small renderer: all user strings are escaped, with no scripts or raw HTML.
  const out:string[]=[];let table=false;
  for(const line of markdown.split('\n')){
    if(line.startsWith('|')){
      if(/^\|[\s|:-]+$/.test(line))continue;
      const cells=line.slice(1,-1).split(/(?<!\\)\|/).map(s=>escape(s.trim().replaceAll('\\|','|')));
      if(!table){out.push('<div class="table"><table><thead><tr>'+cells.map(s=>`<th>${s}</th>`).join('')+'</tr></thead><tbody>');table=true;}
      else out.push('<tr>'+cells.map(s=>`<td>${s}</td>`).join('')+'</tr>');
    }else{
      if(table){out.push('</tbody></table></div>');table=false;}
      if(line.startsWith('### '))out.push(`<h3>${escape(line.slice(4))}</h3>`);
      else if(line.startsWith('## '))out.push(`<h2>${escape(line.slice(3))}</h2>`);
      else if(line.startsWith('# '))out.push(`<h1>${escape(line.slice(2))}</h1>`);
      else if(line)out.push(`<p${line.startsWith('- ')?' class="point"':''}>${escape(line)}</p>`);
    }
  }
  if(table)out.push('</tbody></table></div>');
  return `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NbS analysis brief</title><style>body{margin:0;background:#f0f3e9;color:#254438;font:14px/1.7 system-ui,sans-serif}main{max-width:1120px;margin:40px auto;padding:55px;background:#fffefa;border-top:6px solid #487c54}h1,h2{font-family:Georgia,serif;font-weight:500}h1{font-size:38px;margin:0}h2{font-size:27px;margin-top:38px;padding-top:18px;border-top:1px solid #d8e2d1}h3{font-size:17px}p{overflow-wrap:anywhere}.point{padding-left:14px;color:#4c6456}.table{overflow:auto}table{border-collapse:collapse;width:100%;font-size:11px;margin:15px 0}th,td{text-align:left;padding:9px;border-bottom:1px solid #e2e7db;overflow-wrap:anywhere}th{background:#eef3e7}tbody tr:nth-child(even){background:#fafbf6}.print-note{background:#eef3e7;padding:12px;font-size:12px}@media(max-width:700px){main{margin:0;padding:24px}}@media print{@page{size:A4 landscape;margin:12mm}body{background:white;font-size:10px}main{padding:0;margin:0;max-width:none;border:0}h1{font-size:27px}h2{font-size:21px;break-after:avoid}table{font-size:8px;table-layout:fixed}tr{break-inside:avoid}thead{display:table-header-group}.table{overflow:visible}.print-note{display:none}}</style><main><p class="print-note">Printable analysis brief · use your browser’s Print → Save as PDF to share a PDF copy.</p>${out.join('')}</main></html>`;
}
