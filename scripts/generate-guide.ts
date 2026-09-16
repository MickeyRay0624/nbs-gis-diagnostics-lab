import { writeFile, readFile } from 'node:fs/promises';
import { guideContent as c, metricDefinitions } from '../src/guideContent';
import { fileURLToPath } from 'node:url';
const root=fileURLToPath(new URL('..', import.meta.url));
const catalog=JSON.parse(await readFile(root+'/public/data/step2/catalog.json','utf8'));
const lines=['# NbS Diagnostics Lab: feature guide and calculation methods','','Version 0.4.0. Public-data Ganjam Step 2 screening. Expert review pending.','',c.lead,'','## '+c.architectureTitle,'',c.architecture,'',c.limits];
c.entries.forEach((e,i)=>lines.push('',`## ${i+1}. ${e.title}`,'','**How to use:** '+e.how,'','**How it works:** '+e.method));
lines.push('','## Forest metric definitions','','| Field | Meaning | Formula / convention |','| --- | --- | --- |');
metricDefinitions.forEach(r=>lines.push('| '+r.join(' | ')+' |'));
for(const m of catalog.modules.filter((m:any)=>!['lulc','fragmentation'].includes(m.id))) {
 lines.push('','## '+m.title,'',m.question,'','Run the diagnostic, choose a map layer, inspect coverage and source resolution, then download GeoTIFF, PNG, CSV and the manifest. Prepared time series have a selector and CSV export.','',...m.method.map((t:string)=>'- '+t),'','Limitations:','',...m.limitations.map((t:string)=>'- '+t),'','Step 3 field checks:','',...m.fieldChecks.map((t:string)=>'- '+t));
}
lines.push('','## Required outputs and acceptance','','Each module exposes maps, numeric exports, statistics, provenance and field-check questions. Download the diagnostic brief to collect the evidence available in the current session. Refreshing the page clears in-memory runs; export before closing.','',catalog.protection.detail,'',catalog.review.detail,'','The first release defers automated arbitrary-AOI data ingestion, RCP2.6 / a low-emission climate scenario, authenticated ASIS access, event forecasting, unified risk scores, additional hazard modules, intervention selection and cost-benefit analysis.','','## Sources','',...catalog.sources.map((s:any)=>`- [${s.name}](${s.url}) — ${s.version}; ${s.licence}.`));
await writeFile(root+'/public/guide.en.md',lines.join('\n')+'\n');
