import { useEffect, useState } from 'react';
import { DiagnosticResults } from './DiagnosticResults';
import { WaterResults } from '../water/WaterResults';
import { type DiagnosticClient, type DiagnosticResult } from './client';
import { type WaterClient, type WaterResult } from '../water/client';
import { MODULES, type Analysis, type AnalysisModule } from './workflow';
import { analysisBrief, briefHtml } from './brief';
import { download } from '../analysis/presets';
import { ModuleIcon } from './ModuleIcon';

export function AnalysisResults({analysis,diagnosticClient,waterClient}:{analysis:Analysis;diagnosticClient:DiagnosticClient;waterClient:WaterClient}){
  const d=analysis.children.find(c=>c.kind==='diagnostics')?.job,w=analysis.children.find(c=>c.kind==='water')?.job;
  const [diagnostics,setDiagnostics]=useState<DiagnosticResult|null>(null),[water,setWater]=useState<WaterResult|null>(null);
  const [errors,setErrors]=useState<Record<string,string>>({}),[retry,setRetry]=useState(0);
  const [selected,setSelected]=useState<AnalysisModule>(analysis.modules[0]);
  useEffect(()=>{
    const controller=new AbortController();setDiagnostics(null);setErrors(e=>({...e,diagnostics:''}));
    if(d&&['succeeded','partial'].includes(d.status))diagnosticClient.result(d.id,controller.signal).then(r=>{
      if(r.schema!=='nbs-online-diagnostics/v1'||r.validation.status!=='passed')throw new Error('The diagnostic result format is unsupported.');
      if(!controller.signal.aborted)setDiagnostics(r);
    }).catch(e=>{if(!controller.signal.aborted)setErrors(v=>({...v,diagnostics:e.message}));});
    return()=>controller.abort();
  },[d?.id,d?.status,diagnosticClient,retry]);
  useEffect(()=>{
    const controller=new AbortController();setWater(null);setErrors(e=>({...e,water:''}));
    if(w?.status==='succeeded')waterClient.result(w.id,controller.signal).then(r=>{
      if(r.schema!=='nbs-water/v1'||r.validation.status!=='passed')throw new Error('The water result format is unsupported.');
      if(!controller.signal.aborted)setWater(r);
    }).catch(e=>{if(!controller.signal.aborted)setErrors(v=>({...v,water:e.message}));});
    return()=>controller.abort();
  },[w?.id,w?.status,waterClient,retry]);
  function moduleStatus(id:AnalysisModule){
    if(id==='water'&&water)return 'Ready to explore';
    const dm=diagnostics?.modules.find(m=>m.id===id);
    if(dm)return dm.status==='available'?'Ready to explore':dm.reason_code==='no_valid_observations'?'No valid source data':'Not completed';
    const job=id==='water'?w:d;
    if(!job&&analysis.cancel_requested)return 'Cancelled';
    return job?.status==='running'?'Calculating…':job?.status==='queued'||!job?'In queue':job?.status==='succeeded'||job?.status==='partial'?'Loading results…':job?.status==='expired'?'Results expired':job?.status==='cancelled'?'Cancelled':'Not completed';
  }
  const active=MODULES.find(m=>m.id===selected)!,child=selected==='water'?w:d,loaded=selected==='water'?!!water:!!diagnostics;
  const error=errors[selected==='water'?'water':'diagnostics'];
  const sources=diagnostics?.sources.filter(s=>diagnostics.modules.find(m=>m.id===selected)?.sources?.includes(s.id));
  const sourceLabel=selected==='water'?(water?.model??active.source):sources?.length?sources.map(s=>s.name).join(' · '):d?.request.mode==='ganjam'?'Verified Ganjam reference inputs':active.source;
  const waiting=!child&&!analysis.cancel_requested||child?.status==='queued'||child?.status==='running';
  const cancelled=child?.status==='cancelled'||!child&&analysis.cancel_requested;
  return <div className="analysis-results">
    <div className="results-context"><span className="lab-kicker">EXPLORE YOUR RESULTS</span><h2>{analysis.name}</h2><p>Each diagnostic keeps its own observation dates, source resolution and coverage. Select a module to explore its maps and downloads.</p></div>
    <div className="brief-download"><div><span className="lab-kicker">ONE ANALYSIS · ONE BRIEF</span><strong>Bring the findings together.</strong><p>Selected modules, coverage, source definitions and change summaries in a printable document.</p></div><div><button className="lab-primary" onClick={()=>download('nbs-analysis-brief.html',briefHtml(analysisBrief(analysis,diagnostics,water)),'text/html')}>Download brief ↓</button><button className="lab-secondary" onClick={()=>download('nbs-analysis-brief.md',analysisBrief(analysis,diagnostics,water),'text/markdown')}>Markdown ↓</button></div></div>
    <div className="results-layout">
      <nav className="result-module-nav" aria-label="Result diagnostics">{MODULES.filter(m=>analysis.modules.includes(m.id)).map(m=><button key={m.id} aria-pressed={selected===m.id} onClick={()=>setSelected(m.id)}><ModuleIcon id={m.id}/><span><strong>{m.title}</strong><small>{moduleStatus(m.id)}</small></span><span aria-hidden="true">↗</span></button>)}</nav>
      <section className="result-surface" aria-label={active.title+' result'}><div className="result-module-heading"><span className={`module-glyph glyph-${active.id}`}><ModuleIcon id={active.id}/></span><div><h3>{active.title}</h3><p>{sourceLabel}</p></div><span className="result-availability">{moduleStatus(selected)}</span></div>
        {error?<div className="lab-empty"><h4>Could not load this result</h4><p role="alert">{error}</p><button className="lab-secondary" onClick={()=>setRetry(n=>n+1)}>Retry loading</button></div>:loaded?selected==='water'&&water&&w?<WaterResults key={w.id} result={water} jobId={w.id} client={waterClient} embedded/>:diagnostics&&d&&selected!=='water'?<DiagnosticResults key={d.id+selected} result={diagnostics} jobId={d.id} client={diagnosticClient} initialModuleId={selected} embedded/>:null:<div className="lab-empty"><ModuleIcon id={selected}/><h4>{moduleStatus(selected)}</h4><p>{cancelled?'This calculation was cancelled. Submit a new analysis to run it again.':child?.status==='running'?child.stage:waiting?'This module will start when a compute slot is available. You can return to this page later.':child?.status==='expired'?'The retention period has ended. Submit a new analysis to generate fresh results.':child?.error||'Completed modules remain available in the menu.'}</p>{waiting&&<progress aria-label="Calculation in progress"/>}</div>}
      </section>
    </div>
  </div>;
}
