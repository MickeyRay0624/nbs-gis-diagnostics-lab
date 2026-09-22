import { useState, type Dispatch, type SetStateAction } from 'react';
import { readVector } from '../analysis/io';
import { WORLDCOVER, GLCFCS, ESRI, parseCrosswalk, csv, download } from '../analysis/presets';
import { sourceCrosswalk } from './landDefinition';
import type { Crosswalk, DiagnosticClient, LandOptions, SourceUpload } from './client';
import type { Preset } from './workflow';

export const defaultLand=():LandOptions=>({resolution:50,edge_width_m:50,include_mangroves:true,count_boundary_as_edge:false});
const presetRows={WorldCover:WORLDCOVER,'GLC-FCS30D':GLCFCS,ESRI:ESRI.map(r=>r.source===10?{...r,code:0,name:'Clouds (excluded)'}:r)};
export function LandInputs({land,setLand,preset,forest,client,files,setFiles,onBusy}:{land:LandOptions;setLand:Dispatch<SetStateAction<LandOptions>>;preset:Preset;forest:boolean;client:DiagnosticClient;files:Record<string,SourceUpload>;setFiles:Dispatch<SetStateAction<Record<string,SourceUpload>>>;onBusy:(b:boolean)=>void}){
  const [busy,setBusy]=useState(''),[error,setError]=useState(''),[template,setTemplate]=useState<keyof typeof presetRows|'Custom'>('Custom');
  const uploaded=land.source==='uploaded',available=preset==='ganjam'?[2002,2012,2022]:[2020,2021];
  const rows=land.crosswalk??(preset==='ganjam'?GLCFCS:WORLDCOVER);
  const targets=[...new Map(rows.filter(r=>r.code!==0).map(r=>[r.code,r])).values()].sort((a,b)=>a.code-b.code);
  const forestCodes=land.forest_codes??(preset==='ganjam'?[2]:land.include_mangroves?[10,95]:[10]);
  const patch=(value:Partial<LandOptions>)=>setLand(v=>({...v,...value}));
  function applyRows(next:Crosswalk[],suggested=forestCodes){
    patch({crosswalk:next,forest_codes:suggested.filter(c=>next.some(r=>r.code===c))});
  }
  function edit(source:number,value:Partial<Crosswalk>){
    const current=rows.find(r=>r.source===source)!;
    let next=rows.map(r=>r.source===source?{...r,...value}:r);
    if(value.code!==undefined){const target=rows.find(r=>r.code===value.code&&r.source!==source);if(target)next=next.map(r=>r.source===source?{...r,name:target.name,color:target.color}:r);}
    if(value.name!==undefined||value.color!==undefined)next=next.map(r=>r.code===current.code?{...r,...value}:r);
    applyRows(next);
  }
  async function upload(file:File,role:'raster'|'protected'|'oecm'){
    setBusy(role);onBusy(true);setError('');
    try{
      if(role==='raster'&&file.size>100_000_000)throw new Error('GeoTIFF upload limit is 100 MB per file. Crop your source first.');
      let body:Blob=file;
      if(role!=='raster'){
        const doc=await readVector(file);doc.features.forEach(f=>{f.properties={};});
        body=new Blob([JSON.stringify(doc)]);
        if(body.size>5_000_000)throw new Error('Simplify the protection polygons to under 5 MB after conversion.');
      }
      const record=await client.upload(body,file.name,role==='raster'?'raster':'vector');setFiles(v=>({...v,[record.id]:record}));
      if(role==='raster'){
        const old=land.rasters??[],known=new Set([...(record.info.codes??[]),...old.flatMap(r=>files[r.upload_id]?.info.codes??[])]);
        const existing=land.crosswalk??[];
        const next=sourceCrosswalk([...known],existing,template!=='Custom'?presetRows[template]:[]);
        let year=2020+old.length;while(old.some(r=>r.year===year))year++;
        patch({rasters:[...old,{year,upload_id:record.id}],crosswalk:next,forest_codes:land.forest_codes??[]});
      }else{
        const key=role==='protected'?'protected_upload_id':'oecm_upload_id';
        if(land[key])await client.discard(land[key]!).catch(()=>{});
        patch({[key]:record.id});
      }
    }catch(e){setError((e as Error).message);}finally{setBusy('');onBusy(false);}
  }
  async function remove(id:string,role:'raster'|'protected'|'oecm'){
    if(role==='raster')patch({rasters:(land.rasters??[]).filter(r=>r.upload_id!==id)});
    else patch({[role==='protected'?'protected_upload_id':'oecm_upload_id']:undefined});
    await client.discard(id).catch(()=>{});
  }
  return <div className="land-inputs">
    <div className="land-settings-heading"><span className="lab-kicker">LANDSCAPE INPUTS</span><h3>Your data. Your definition.</h3><p>Use prepared observations or bring one to three categorical maps. All analysis runs on the server.</p></div>
    <fieldset disabled={!!busy} className="land-input-fieldset">
      <details className="land-step" open><summary><b>01</b><span>Data & years<small>{uploaded?`${land.rasters?.length??0} uploaded maps`:preset==='ganjam'?'GLC-FCS30D · Ganjam':'ESA WorldCover · public data'}</small></span></summary>
        <div className="land-step-body"><div className="boundary-switch"><button aria-pressed={!uploaded} onClick={()=>{if(!uploaded)return;for(const r of land.rasters??[])void client.discard(r.upload_id).catch(()=>{});patch({source:'default',rasters:[],crosswalk:undefined,forest_codes:undefined,years:undefined});setTemplate('Custom');}}>Use prepared data</button><button aria-pressed={uploaded} onClick={()=>{if(!uploaded)patch({source:'uploaded',years:undefined,crosswalk:[],forest_codes:[],rasters:[]});}}>Upload GeoTIFFs</button></div>
        {uploaded?<><label className="prep-field">Dataset name / version<input maxLength={100} value={land.source_name??'User-supplied land cover'} onChange={e=>patch({source_name:e.target.value})}/></label>
          <div className="source-files">{(land.rasters??[]).map((r,i)=><div className="source-file" key={r.upload_id}><span className="file-number">{String(i+1).padStart(2,'0')}</span><div><strong>{files[r.upload_id]?.name??'Uploaded map'}</strong><small>{files[r.upload_id]?.info.crs} · {files[r.upload_id]?.info.codes?.length} classes · verified</small></div><label>Year<input aria-label={`Year for map ${i+1}`} type="number" min={1900} max={2100} value={r.year} onChange={e=>patch({rasters:land.rasters!.map(x=>x===r?{...x,year:Number(e.target.value)}:x)})}/></label><button aria-label={`Remove map ${i+1}`} onClick={()=>void remove(r.upload_id,'raster')}>×</button></div>)}</div>
          {(land.rasters?.length??0)<3&&<label className="source-upload"><strong>＋ Add a land-cover map</strong><small>Single-band categorical GeoTIFF · ≤100 MB · ≤25 million pixels</small><input type="file" aria-label="Upload land-cover GeoTIFF" accept=".tif,.tiff" onChange={e=>{const f=e.target.files?.[0];e.target.value='';if(f)void upload(f,'raster');}}/></label>}
          <p className="builder-note">Use comparable class codes across all years. Zero, declared NoData and masked cells are excluded. Two or three maps are needed for change; a single map can describe forest structure.</p>
        </>:<><div className="year-pills" role="group" aria-label="Land-cover years">{available.map(y=><label key={y}><input type="checkbox" checked={(land.years??available).includes(y)} onChange={()=>patch({years:(land.years??available).includes(y)?(land.years??available).filter(v=>v!==y):[...(land.years??available),y].sort()})}/>{y}</label>)}</div><p className="builder-note">{preset==='ganjam'?'Prepared GLC-FCS30D maps on the existing 50 m grid. Upload your own rasters to study other periods.':'WorldCover 2020 v100 and 2021 v200 use different algorithms. Their differences are not solely land-cover change. For other years or datasets, upload GeoTIFFs.'}</p></>}
        <div className="land-fields"><label className="prep-field">Analysis grid<select value={land.resolution} onChange={e=>{const resolution=Number(e.target.value) as LandOptions['resolution'];patch({resolution,edge_width_m:Math.max(land.edge_width_m,resolution)});}}>{(preset==='ganjam'&&!uploaded?[50,100]:[30,50,100]).map(r=><option key={r} value={r}>{r} m · equal-area</option>)}</select></label>{forest&&<label className="prep-field">Forest edge width (m)<input type="number" min={land.resolution} max={1000} value={land.edge_width_m} onChange={e=>patch({edge_width_m:Number(e.target.value)})}/></label>}</div></div>
      </details>
      <details className="land-step"><summary><b>02</b><span>Class crosswalk{forest?' & forest definition':''}<small>{targets.length} target classes{forest?` · ${forestCodes.length} selected as forest`:''}</small></span></summary><div className="land-step-body">
        <p>Assign source codes to target classes. Give classes the same target code to merge them; their name and colour stay consistent. Target code 0 excludes a source class from analysis (for example clouds).</p>
        <div className="crosswalk-tools"><label className="prep-field">Start from a legend<select value={template} onChange={e=>{const t=e.target.value as typeof template;setTemplate(t);if(t==='Custom')return;const sourceCodes=uploaded?[...new Set((land.rasters??[]).flatMap(r=>files[r.upload_id]?.info.codes??[]))]:rows.map(r=>r.source);const next=sourceCrosswalk(sourceCodes,[],presetRows[t]);applyRows(next,t==='WorldCover'?[10,95]:[2]);}}><option>Custom</option>{Object.keys(presetRows).map(k=><option key={k}>{k}</option>)}</select></label><label className="lab-secondary file-action">Import CSV<input aria-label="Import crosswalk CSV" type="file" accept=".csv" onChange={async e=>{const f=e.target.files?.[0];e.target.value='';if(!f)return;try{if(f.size>100000)throw new Error('Crosswalk CSV limit is 100 KB.');applyRows(parseCrosswalk(await f.text()));setError('');}catch(err){setError((err as Error).message);}}}/></label><button className="lab-secondary" onClick={()=>download('crosswalk.csv',csv([['source_code','target_code','target_name','color'],...rows.map(r=>[r.source,r.code,r.name,r.color])]),'text/csv')}>Export CSV ↓</button></div>
        <div className="table-scroll crosswalk-table"><table><thead><tr><th>Source</th><th>Target</th><th>Class name</th><th>Colour</th></tr></thead><tbody>{rows.map(r=><tr key={r.source}><th>{r.source}</th><td><input aria-label={`Target code for source ${r.source}`} type="number" min={0} max={999} value={r.code} onChange={e=>edit(r.source,{code:Number(e.target.value)})}/></td><td><input aria-label={`Name for source ${r.source}`} maxLength={80} value={r.name} onChange={e=>edit(r.source,{name:e.target.value})}/></td><td><input aria-label={`Colour for source ${r.source}`} type="color" value={r.color} onChange={e=>edit(r.source,{color:e.target.value})}/></td></tr>)}</tbody></table></div>
        {forest&&<div className="forest-definition"><strong>What counts as forest?</strong><p>Select target classes for this run. This records your operational definition; it does not infer legal forest status.</p><div className="forest-chips">{targets.map(t=><label key={t.code}><input type="checkbox" checked={forestCodes.includes(t.code)} onChange={()=>patch({crosswalk:rows,forest_codes:forestCodes.includes(t.code)?forestCodes.filter(c=>c!==t.code):[...forestCodes,t.code]})}/><i style={{background:t.color}}/>{t.name}</label>)}</div><label className="boundary-edge"><input type="checkbox" checked={land.count_boundary_as_edge} onChange={e=>patch({count_boundary_as_edge:e.target.checked})}/>Count the study-area boundary and unknown-data edges as forest edges</label><small>Off by default: unknown data does not establish an ecological edge.</small></div>}
      </div></details>
      <details className="land-step"><summary><b>03</b><span>Protected areas & OECMs<small>Optional spatial groups · same whole-area analysis</small></span></summary><div className="land-step-body"><p>Bring polygon boundaries to compare spatial groups. Protected areas take priority where they overlap OECMs.</p><div className="protection-inputs">{(['protected','oecm'] as const).map(role=>{const id=land[role==='protected'?'protected_upload_id':'oecm_upload_id'];return <div key={role}><label className="source-upload"><strong>{role==='protected'?'Protected areas':'OECMs'}</strong><small>{id?files[id]?.name??'Uploaded polygons':'GeoJSON or one zipped Shapefile · polygons only'}</small><input type="file" accept=".geojson,.json,.zip" aria-label={`Upload ${role} polygons`} onChange={e=>{const f=e.target.files?.[0];e.target.value='';if(f)void upload(f,role);}}/></label>{id&&<button className="remove-source" onClick={()=>void remove(id,role)}>Remove polygons</button>}</div>;})}</div><label className="prep-field">Source, date & coverage note<textarea rows={2} maxLength={400} value={land.protection_note??''} placeholder="e.g. National register, release date, known coverage gaps" onChange={e=>patch({protection_note:e.target.value})}/></label><p className="builder-note">Up to 5 MB after conversion. Point locations cannot establish protected extents. Areas outside supplied polygons are labelled as such; they are not assumed to be unprotected.</p></div></details>
    </fieldset>
    {busy&&<p className="upload-status" role="status"><span className="live-dot"/>Uploading and validating {busy==='raster'?'land cover':'polygons'}… Keep this page open.</p>}
    {error&&<p className="error-box" role="alert">{error}</p>}
  </div>;
}
