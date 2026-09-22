import { useMemo, useRef, useState } from 'react';
import { MapPanel } from '../MapPanel';
import type { VectorCollection } from '../analysis/model';
import { bboxBoundary, defaultJob, validateBoundary, type Job } from '../preparation/config';
import type { Capabilities } from '../water/client';
import type { DiagnosticCapabilities, DiagnosticRequest } from './client';
import { DiagnosticOptions } from './DiagnosticOptions';
import { ModuleIcon } from './ModuleIcon';
import { buildAnalysis, FAYOUM, fayoumBoundary, MODULES, type AnalysisModule, type AnalysisRequest, type Preset } from './workflow';

export function AnalysisWizard({ganjam,diagnostics,water,onSubmit,initialPreset='ganjam'}:{ganjam:VectorCollection|null;diagnostics:DiagnosticCapabilities;water:Capabilities;onSubmit:(r:AnalysisRequest)=>Promise<void>;initialPreset?:Preset}){
  const [step,setStep]=useState(0),[preset,setPreset]=useState<Preset>(initialPreset),[name,setName]=useState(initialPreset==='fayoum'?'Fayoum, Egypt':'Ganjam District, Odisha');
  const [boundaryMode,setBoundaryMode]=useState('rectangle'),[uploaded,setUploaded]=useState<VectorCollection|null>(null),[filename,setFilename]=useState('');
  const [bounds,setBounds]=useState([85.75,20.15,85.95,20.35]);
  const [modules,setModules]=useState<AnalysisModule[]>(initialPreset==='fayoum'?['water']:MODULES.filter(m=>m.id!=='water').map(m=>m.id));
  const [job,setJob]=useState<Job>(()=>{const j=defaultJob();return {...j,maxDownloadGB:10,climate:{...j.climate,models:['ACCESS-CM2'],scenarios:['ssp245'],metrics:['hot','rain','dry']}};});
  const [land,setLand]=useState<NonNullable<DiagnosticRequest['land_cover']>>({resolution:50,edge_width_m:50,include_mangroves:true,count_boundary_as_edge:false});
  const [waterDates,setWaterDates]=useState({start:FAYOUM.start,end:FAYOUM.end});
  const [error,setError]=useState<string|null>(null),[busy,setBusy]=useState(false);
  const top=useRef<HTMLDivElement>(null);
  const region=useMemo(()=>{
    try{
      const boundary=preset==='ganjam'?ganjam:preset==='fayoum'?fayoumBoundary():boundaryMode==='upload'?uploaded:bboxBoundary(...bounds as [number,number,number,number]);
      if(!boundary)return {boundary:null,area:null,error:preset==='ganjam'?'Loading the Ganjam boundary…':'Choose a boundary to continue.'};
      return {boundary,area:validateBoundary(boundary).areaKm2,error:null};
    }catch(e){return {boundary:null,area:null,error:(e as Error).message};}
  },[preset,ganjam,boundaryMode,uploaded,bounds]);
  const patch=<K extends keyof Job>(key:K,value:Job[K])=>{setJob(j=>({...j,[key]:value}));setError(null);};
  function usePreset(next:Preset){
    setPreset(next);setError(null);
    setName(next==='ganjam'?'Ganjam District, Odisha':next==='fayoum'?'Fayoum, Egypt':'My study area');
    setModules(next==='ganjam'?MODULES.filter(m=>m.id!=='water').map(m=>m.id):next==='fayoum'?['water']:['flood','degradation']);
  }
  function unavailable(id:AnalysisModule){
    if(id==='water')return preset==='fayoum'?water.sample_ready?null:'Sample inputs are being prepared':preset==='ganjam'||!water.custom_enabled?'Choose the Fayoum sample to run this module':null;
    if(preset==='ganjam')return diagnostics.sample_ready?null:'Reference inputs are being prepared';
    return diagnostics.modules.find(m=>m.id===id)?.custom_enabled?null:'Source access is awaiting verification';
  }
  const selected=MODULES.filter(m=>modules.includes(m.id));
  const config={...job,modules:job.modules.filter(m=>modules.includes(m))};
  config.modules=modules.filter(m=>m!=='water'&&m!=='lulc'&&m!=='fragmentation') as Job['modules'];
  function payload(){
    const blocked=modules.find(id=>unavailable(id));
    if(blocked)throw new Error(`${MODULES.find(m=>m.id===blocked)!.title}: ${unavailable(blocked)}.`);
    return buildAnalysis({preset,name,boundary:region.boundary,modules,config,land,waterDates,waterCustom:water.custom_enabled,waterReady:water.sample_ready,maxClimateRequests:diagnostics.max_climate_requests});
  }
  function go(next:number){
    try{
      if(next>0&&(!region.boundary||!name.trim()))throw new Error(region.error||'Enter a study-area name.');
      if(next>1)payload();
      setStep(next);setError(null);top.current?.scrollIntoView({behavior:'smooth',block:'start'});
    }catch(e){setError((e as Error).message);}
  }
  async function submit(){setBusy(true);setError(null);try{await onSubmit(payload());}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  return <div className="analysis-builder" ref={top}>
    <div className="builder-heading"><div><span className="lab-kicker">BUILD YOUR ANALYSIS</span><h2>Start with a place.</h2><p>One study area. The diagnostics that matter to you.</p></div><span className="builder-step-count">STEP <b>{step+1}</b> / 3</span></div>
    <div className="builder-layout">
      <section className="builder-panel" aria-label="Analysis setup">
        <nav className="builder-steps" aria-label="Analysis steps">{['Study area','Diagnostics','Review & run'].map((label,i)=><button key={label} aria-current={step===i?'step':undefined} disabled={busy} onClick={()=>go(i)}><span>{step>i?'✓':`0${i+1}`}</span><div><small>{['WHERE','WHAT','READY'][i]}</small>{label}</div></button>)}</nav>
        <div className="builder-content">
          {step===0&&<>
            <div className="builder-section-title"><h3>Choose your study area</h3><p>Bring a boundary, or begin with a prepared example.</p></div>
            <div className="region-presets" aria-label="Study-area presets">{([
              ['custom','Your study area','Upload a boundary or enter coordinates','⌖'],['ganjam','Ganjam, India','Seven diagnostics · verified source inputs','01'],['fayoum','Fayoum, Egypt','Includes water & productivity · July 2021','02'],
            ] as const).map(([id,title,description,icon])=><button key={id} aria-pressed={preset===id} onClick={()=>usePreset(id)}><span className="region-symbol" aria-hidden="true">{icon}</span><span><strong>{title}</strong><small>{description}</small></span><i aria-hidden="true">{preset===id?'✓':'↗'}</i></button>)}</div>
            <label className="prep-field">Study-area name<input maxLength={80} value={name} onChange={e=>setName(e.target.value)}/></label>
            {preset==='custom'&&<>
              <div className="boundary-switch" role="group" aria-label="Boundary input"><button aria-pressed={boundaryMode==='rectangle'} onClick={()=>setBoundaryMode('rectangle')}>Enter coordinates</button><button aria-pressed={boundaryMode==='upload'} onClick={()=>setBoundaryMode('upload')}>Upload GeoJSON</button></div>
              {boundaryMode==='rectangle'?<div className="prep-bounds">{['West longitude','South latitude','East longitude','North latitude'].map((label,i)=><label className="prep-field" key={label}>{label}<input type="number" step="0.01" value={bounds[i]} onChange={e=>setBounds(b=>b.map((v,n)=>n===i?Number(e.target.value):v))}/></label>)}</div>:<label className="boundary-upload"><span aria-hidden="true">↥</span><strong>{filename||'Choose a GeoJSON boundary'}</strong><small>WGS84 polygon or multipolygon · up to 190 KB</small><input aria-label="Boundary GeoJSON" type="file" accept=".geojson,.json" onChange={async e=>{const file=e.target.files?.[0];if(!file)return;try{if(file.size>190000)throw new Error('Simplify the boundary to under 190 KB.');const b=validateBoundary(JSON.parse(await file.text()));setUploaded(b.boundary);setFilename(file.name);setError(null);}catch(err){setUploaded(null);setError((err as Error).message);}e.target.value='';}}/></label>}
            </>}
            <div className="builder-map"><MapPanel aoi={region.boundary} label={name||'Study-area preview'} loading={preset==='ganjam'&&!ganjam} error={region.error} showMarker={false}/><div className="map-caption"><span>STUDY-AREA PREVIEW</span><strong>{region.area!==null?`${region.area.toLocaleString('en',{maximumFractionDigits:1})} km²`:'No boundary selected'}</strong></div></div>
            {preset==='ganjam'&&<p className="builder-note">The server recalculates verified Ganjam inputs using their recorded source periods. Water modelling is available through the Fayoum sample.</p>}
            {preset==='fayoum'&&<p className="builder-note">All selected modules will use this Fayoum boundary. Water modelling uses verified inputs for July 2021; other diagnostics keep their own source periods.</p>}
          </>}
          {step===1&&<>
            <div className="builder-section-title row"><div><h3>Choose your diagnostics</h3><p>Select one or combine several in the same analysis.</p></div><span className="selection-count">{modules.length} of 8 selected</span></div>
            <div className="eight-modules">{MODULES.map((m,i)=>{const reason=unavailable(m.id),checked=modules.includes(m.id);return <label key={m.id} className={`diagnostic-choice ${checked?'is-selected':''} ${reason?'is-unavailable':''}`}><div className="choice-top"><span className={`module-glyph glyph-${m.id}`}><ModuleIcon id={m.id}/></span><span className="module-index">{String(i+1).padStart(2,'0')}</span><input type="checkbox" aria-label={m.title} checked={checked} disabled={!!reason} onChange={()=>{setModules(v=>checked?v.filter(id=>id!==m.id):[...v,m.id]);setError(null);}}/></div><strong>{m.title}</strong><p>{m.description}</p><small>{reason||((preset==='ganjam'?'Verified Ganjam inputs':m.source)+(m.id==='water'&&preset==='fayoum'?' · July 2021':''))}</small></label>;})}</div>
            {preset!=='fayoum'&&!water.custom_enabled&&<div className="water-sample-note"><span className="module-glyph glyph-water"><ModuleIcon id="water"/></span><p><strong>Try the eighth diagnostic.</strong> Water & productivity is ready for the Fayoum example area.</p><button onClick={()=>{usePreset('fayoum');go(0);}}>Use Fayoum sample <span aria-hidden="true">↗</span></button></div>}
            {preset==='ganjam'?<div className="source-period-note"><strong>Reference periods are fixed</strong><p>Each Ganjam diagnostic keeps its documented dates and source resolution. Review these alongside the results.</p></div>:<>
              {!!modules.filter(id=>id!=='water').length&&<details className="module-settings" open><summary>Diagnostic settings <span>Periods, scenarios & methods</span></summary><DiagnosticOptions job={config} patch={patch} land={land} setLand={setLand} landModules={modules.filter((m):m is 'lulc'|'fragmentation'=>m==='lulc'||m==='fragmentation')}/></details>}
              {modules.includes('water')&&<fieldset className="prep-options water-date-settings"><legend>Water & productivity period</legend><div className="water-fields"><label className="prep-field">Start date<input type="date" value={preset==='fayoum'?FAYOUM.start:waterDates.start} disabled={preset==='fayoum'} onChange={e=>setWaterDates(v=>({...v,start:e.target.value}))}/></label><label className="prep-field">End date<input type="date" value={preset==='fayoum'?FAYOUM.end:waterDates.end} disabled={preset==='fayoum'} onChange={e=>setWaterDates(v=>({...v,end:e.target.value}))}/></label></div><p>{preset==='fayoum'?'The verified sample covers 1–31 July 2021. The server computes new pyWaPOR results for every submitted analysis.':'Up to 31 days and a 500 km² enclosing rectangle. Select completed dates from 2018 onwards.'}</p></fieldset>}
            </>}
          </>}
          {step===2&&<>
            <div className="builder-section-title"><h3>Your analysis is ready to run.</h3><p>Check your selections, then let the server do the work.</p></div>
            <div className="review-area"><span className="review-coordinate" aria-hidden="true">⌖</span><div><small>STUDY AREA</small><h4>{name}</h4><p>{region.area?.toLocaleString('en',{maximumFractionDigits:1})} km² · {preset==='ganjam'?'Ganjam reference inputs':preset==='fayoum'?'Fayoum example boundary':'Your selected boundary'}</p></div><button onClick={()=>go(0)}>Edit area</button></div>
            <div className="review-modules">{selected.map(m=><div key={m.id}><ModuleIcon id={m.id}/><span><strong>{m.title}</strong><small>{m.id==='water'?preset==='fayoum'?'1–31 July 2021':`${waterDates.start} to ${waterDates.end}`:preset==='ganjam'?'Recorded Ganjam source periods':m.source}</small></span><span className="review-check" aria-label="Selected">✓</span></div>)}</div>
            <div className="submit-explanation"><strong>One submission. All your selected diagnostics.</strong><p>Calculations run in a queue on the server. You can close this page and return to My tasks in the same browser. Completed maps and downloads remain available for {water.retention_days} days.</p><small>Source coverage and limits can leave partial results; completed modules stay available.</small></div>
          </>}
          {error&&<p className="error-box" role="alert">{error}</p>}
        </div>
        <div className="builder-bottom"><span>{step===0?'Define the place you want to understand.':step===1?'Every module keeps its own source and method.':'No installation. No access code.'}</span><div>{step>0&&<button className="lab-secondary" disabled={busy} onClick={()=>go(step-1)}>Back</button>}{step<2?<button className="lab-primary" onClick={()=>go(step+1)}>{step===0?'Choose diagnostics':'Review analysis'} <span aria-hidden="true">→</span></button>:<button className="lab-primary" disabled={busy} onClick={()=>void submit()}>{busy?'Submitting…':'Run analysis'} <span aria-hidden="true">↗</span></button>}</div></div>
      </section>
      <aside className="analysis-summary"><div className="summary-label"><span className="live-dot"/>YOUR ANALYSIS</div><h3>{name||'Your study area'}</h3><p>{preset==='ganjam'?'Odisha, India':preset==='fayoum'?'Fayoum, Egypt':'Custom study area'}</p><div className="summary-stats"><div><strong>{region.area!==null?region.area.toLocaleString('en',{maximumFractionDigits:1}):'—'}</strong><small>km² selected</small></div><div><strong>{modules.length.toString().padStart(2,'0')}</strong><small>diagnostics</small></div></div><div className="summary-divider"/><ul>{selected.map(m=><li key={m.id}><ModuleIcon id={m.id}/><span>{m.title}</span></li>)}</ul>{!selected.length&&<p>Choose diagnostics in the next step.</p>}<div className="summary-divider"/><div className="summary-delivery"><span aria-hidden="true">↙</span><div><strong>Maps, insights & data</strong><p>Interactive maps · GeoTIFF<br/>Statistics · CSV · source details</p></div></div><p className="summary-footnote">Public observations for environmental screening. Review source scale and coverage before interpretation.</p></aside>
    </div>
  </div>;
}
