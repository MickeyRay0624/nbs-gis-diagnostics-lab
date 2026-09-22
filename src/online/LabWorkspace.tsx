import { useEffect, useMemo, useRef, useState } from 'react';
import type { VectorCollection } from '../analysis/model';
import { validateVector } from '../analysis/io';
import { digest, validateCatalog } from '../step2/io';
import { prepareComputeSession, WaterClient, type Capabilities } from '../water/client';
import { DiagnosticClient, type DiagnosticCapabilities } from './client';
import { AnalysisClient, MODULES, type Analysis, type AnalysisRequest } from './workflow';
import { AnalysisWizard } from './AnalysisWizard';
import { AnalysisResults } from './AnalysisResults';
import { ModuleIcon } from './ModuleIcon';

type View='new'|'tasks'|'results';
const ENDPOINT=import.meta.env.VITE_NBS_API_URL as string|undefined;
const SESSION=`nbs-water-access:${ENDPOINT??'unconfigured'}`;
const ACTIVE=['queued','running'];
const statusLabels:Record<Analysis['status'],string>={queued:'In queue',running:'Calculating',succeeded:'Ready',partial:'Partial results',failed:'Not completed',cancelled:'Cancelled',expired:'Expired'};
function initialView():View{return /jobs|tasks/.test(location.hash)?'tasks':/results/.test(location.hash)?'results':'new';}
function Contours(){return <svg className="hero-contours" viewBox="0 0 470 250" fill="none" aria-hidden="true"><defs><clipPath id="landscape-window"><rect width="470" height="250" rx="20"/></clipPath><linearGradient id="contour-paper"><stop stopColor="#e4eddf"/><stop offset="1" stopColor="#d5e5d8"/></linearGradient></defs><g clipPath="url(#landscape-window)"><path fill="url(#contour-paper)" d="M0 0h470v250H0z"/>{Array.from({length:11},(_,i)=><path key={i} d={`M${-80+i*11} -30 C${40+i*5} ${60+i*8},${185-i*4} ${-30+i*19},${145+i*16} ${110+i*7} S${230+i*7} ${230+i*3},${220+i*22} 295`} stroke={i%3===0?'#6b9a83':'#a6bea8'} strokeWidth={i%3===0?1.2:.8}/>)}<path d="M420 -20C290 55 435 100 290 157S290 237 230 280" stroke="#fffdf8" strokeWidth="19"/><path d="M420 -20C290 55 435 100 290 157S290 237 230 280" stroke="#78a7a1" strokeWidth="9"/><path d="m209 74 83 19 28 66-103 24-41-62z" fill="#c9dcb2" fillOpacity=".65" stroke="#376c51" strokeDasharray="5 4"/><circle cx="247" cy="126" r="19" fill="#fffdf6"/><circle cx="247" cy="126" r="6" fill="#205e49"/><path d="M247 103v9m0 28v9m-23-23h9m28 0h9" stroke="#205e49"/><g fill="#315b49" fontSize="10" fontFamily="Arial,sans-serif" letterSpacing="2"><text x="23" y="29">A SHARED VIEW OF YOUR LANDSCAPE</text><text x="25" y="228">LAND / WATER / CLIMATE</text></g><path d="M427 194v27m-5-20 5-8 5 8" stroke="#315b49"/><text x="423" y="185" fill="#315b49" fontSize="10">N</text></g></svg>;}

export default function LabWorkspace(){
  const clients=useMemo(()=>ENDPOINT?{analysis:new AnalysisClient(ENDPOINT),diagnostics:new DiagnosticClient(ENDPOINT),water:new WaterClient(ENDPOINT)}:null,[]);
  const [view,setView]=useState<View>(initialView),[initialPreset]=useState(location.hash==='#online-water'?'fayoum' as const:'ganjam' as const);
  const [ganjam,setGanjam]=useState<VectorCollection|null>(null),[boundaryError,setBoundaryError]=useState('');
  const [caps,setCaps]=useState<{diagnostics:DiagnosticCapabilities;water:Capabilities}|null>(null),[analyses,setAnalyses]=useState<Analysis[]>([]);
  const [ready,setReady]=useState(false),[error,setError]=useState(''),[pollError,setPollError]=useState(''),[attempt,setAttempt]=useState(0),[refresh,setRefresh]=useState(0);
  const [selectedId,setSelectedId]=useState<string|null>(null),[cancelling,setCancelling]=useState<string|null>(null);
  const pending=useRef<{body:string;key:string}|null>(null);
  const selected=analyses.find(a=>a.id===selectedId)??analyses[0];
  const active=analyses.filter(a=>ACTIVE.includes(a.status)).length;
  const completed=analyses.filter(a=>a.status==='succeeded'||a.status==='partial').length;
  function navigate(next:View){setView(next);history.replaceState(null,'',next==='new'?'#online-diagnostics':next==='tasks'?'#my-tasks':'#results');window.scrollTo({top:0,behavior:'smooth'});}
  useEffect(()=>{const onHash=()=>setView(initialView());window.addEventListener('hashchange',onHash);return()=>window.removeEventListener('hashchange',onHash);},[]);
  useEffect(()=>{
    const controller=new AbortController();
    Promise.all([fetch(`${import.meta.env.BASE_URL}data/step2/catalog.json`,{signal:controller.signal}),fetch(`${import.meta.env.BASE_URL}data/ganjam-aoi.geojson`,{signal:controller.signal})]).then(async([c,a])=>{
      if(!c.ok||!a.ok)throw new Error('The Ganjam boundary could not be loaded. Reload to retry.');
      const catalog=validateCatalog(await c.json()),bytes=await a.arrayBuffer();
      if(await digest(bytes)!==catalog.studyArea.sha256)throw new Error('The Ganjam catalog and boundary do not match.');
      if(!controller.signal.aborted)setGanjam(validateVector(JSON.parse(new TextDecoder().decode(bytes))));
    }).catch(e=>{if(!controller.signal.aborted)setBoundaryError(e.message);});
    return()=>controller.abort();
  },[]);
  useEffect(()=>{
    if(!clients||!ENDPOINT)return;let live=true;setError('');setReady(false);
    let legacy='';try{legacy=sessionStorage.getItem(SESSION)??'';}catch{/* Storage may be blocked. The server cookie still works. */}
    prepareComputeSession(ENDPOINT,legacy).then(()=>Promise.all([clients.diagnostics.capabilities(),clients.water.capabilities()])).then(([diagnostics,water])=>{
      if(live){try{sessionStorage.removeItem(SESSION);}catch{/* Ignore disabled browser storage. */}setCaps({diagnostics,water});setReady(true);}
    }).catch(e=>{if(live)setError(e.message);});return()=>{live=false;};
  },[clients,attempt]);
  useEffect(()=>{
    if(!ready||!clients)return;const controller=new AbortController();let timer:ReturnType<typeof setTimeout>;
    async function poll(){
      try{const [items,diagnostics,water]=await Promise.all([clients!.analysis.analyses(controller.signal),clients!.diagnostics.capabilities(controller.signal),clients!.water.capabilities(controller.signal)]);if(controller.signal.aborted)return;setAnalyses(items);setCaps({diagnostics,water});setPollError('');setSelectedId(id=>items.some(a=>a.id===id)?id:items[0]?.id??null);}
      catch(e){if(!controller.signal.aborted)setPollError((e as Error).message);}
      if(!controller.signal.aborted)timer=setTimeout(poll,5000);
    }
    void poll();return()=>{controller.abort();clearTimeout(timer);};
  },[clients,ready,refresh]);
  async function submit(request:AnalysisRequest){
    if(!clients)throw new Error('The compute service is not connected.');
    const body=JSON.stringify(request);if(!pending.current||pending.current.body!==body)pending.current={body,key:crypto.randomUUID()};
    const a=await clients.analysis.submitAnalysis(request,pending.current.key);pending.current=null;
    setAnalyses(items=>[a,...items.filter(i=>i.id!==a.id)]);setSelectedId(a.id);setRefresh(n=>n+1);navigate('tasks');
  }
  async function cancel(id:string){if(!clients)return;setCancelling(id);setError('');try{const a=await clients.analysis.cancelAnalysis(id);setAnalyses(items=>items.map(i=>i.id===id?a:i));setRefresh(n=>n+1);}catch(e){setError((e as Error).message);}finally{setCancelling(null);}}
  const workersReady=caps?.diagnostics.worker_online&&caps?.water.worker_online;
  return <div className="lab-app">
    <a className="lab-skip" href="#lab-main">Skip to content</a>
    <header className="lab-header"><a href="#online-diagnostics" className="lab-brand" onClick={e=>{e.preventDefault();navigate('new');}}><span className="brand-mark">N<span>↗</span></span><span><strong>NbS Diagnostics Lab<span className="brand-period">.</span></strong><small>UNDERSTAND YOUR LANDSCAPE</small></span></a><nav aria-label="Main navigation">{([['new','New analysis'],['tasks','My tasks'],['results','Results']] as const).map(([id,label])=><button key={id} aria-current={view===id?'page':undefined} onClick={()=>navigate(id)}>{label}{id==='tasks'&&active>0&&<span>{active}</span>}</button>)}</nav><div className="header-service"><span className={`live-dot ${!workersReady?'muted':''}`}/>{!ready?'Connecting…':workersReady?'Compute service ready':'Compute service waiting'}</div></header>
    <main id="lab-main" className="lab-main">
      {view==='new'&&<section className="lab-hero"><div><span className="lab-kicker">ENVIRONMENTAL DIAGNOSTICS · ALL IN ONE PLACE</span><h1>One landscape.<br/><em>Eight perspectives.</em></h1><p>Turn public Earth observations into a clearer picture of your study area. Choose your diagnostics. We’ll handle the calculations.</p><div className="hero-points"><span><i>08</i> connected diagnostics</span><span><i>↗</i> entirely in your browser</span></div></div><div className="hero-art"><Contours/><div><span>FROM OBSERVATIONS TO UNDERSTANDING</span><span>NbS / 01—08</span></div></div></section>}
      {view!=='new'&&<div className="page-intro"><div><span className="lab-kicker">YOUR WORKSPACE</span><h1>{view==='tasks'?'Your work, in progress.':'A closer look at your landscape.'}</h1><p>{view==='tasks'?'All eight diagnostics, one task history. Calculations continue when you close the page.':'Explore completed maps, understand their coverage and download the data.'}</p></div><button className="lab-primary" onClick={()=>navigate('new')}>New analysis <span aria-hidden="true">+</span></button></div>}
      {(error||pollError||boundaryError)&&<div className="lab-error" role="alert"><p>{error||pollError||boundaryError}</p>{!ready&&<button className="lab-secondary" onClick={()=>setAttempt(n=>n+1)}>Retry connection</button>}</div>}
      {!ready||!caps||!clients?<div className="lab-empty connection-empty"><h2>{!ENDPOINT?'Compute service is not configured':error?'Your workspace is temporarily unavailable':'Preparing your workspace…'}</h2><p>{!ENDPOINT?'Configure the compute service before using this copy of the platform.':'Your study areas and results will be available here once connected.'}</p></div>:<>
        <div hidden={view!=='new'}><AnalysisWizard client={clients.diagnostics} ganjam={ganjam} diagnostics={caps.diagnostics} water={caps.water} onSubmit={submit} initialPreset={initialPreset}/></div>
        {view==='tasks'&&<section className="task-workspace"><div className="task-summary"><div><strong>{String(analyses.length).padStart(2,'0')}</strong><span>RECENT ANALYSES</span></div><div><strong>{String(active).padStart(2,'0')}</strong><span>IN PROGRESS</span></div><div><strong>{String(completed).padStart(2,'0')}</strong><span>WITH RESULTS</span></div><p>Saved to this browser’s workspace<br/>Results retained for {caps.water.retention_days} days</p></div><div className="task-list-heading"><h2>Recent analyses</h2><span>Updates automatically <span className="live-dot"/></span></div>{analyses.length?<div className="analysis-task-list">{analyses.map(a=><article className={`analysis-task ${a.id===selectedId?'is-current':''}`} key={a.id}><div className="task-symbol"><ModuleIcon id={a.modules.includes('water')?'water':a.modules[0]}/></div><div className="task-copy"><div className="task-name-line"><h3>{a.name}</h3><span className={`lab-status ${a.status}`}>{statusLabels[a.status]}</span></div><p>{a.modules.length} diagnostic{a.modules.length!==1?'s':''} · {new Date(a.created*1000).toLocaleString(undefined,{dateStyle:'medium',timeStyle:'short'})}</p><div className="task-module-pills">{MODULES.filter(m=>a.modules.includes(m.id)).map(m=><span key={m.id} title={m.title}><ModuleIcon id={m.id}/>{m.title}</span>)}</div>{ACTIVE.includes(a.status)&&<div className="task-progress"><progress aria-label={`${a.name} calculation in progress`}/><small>{a.stage}</small></div>}</div><div className="task-actions"><button className="lab-secondary" onClick={()=>{setSelectedId(a.id);navigate('results');}}>{ACTIVE.includes(a.status)?'View progress':'View results'} <span aria-hidden="true">↗</span></button>{ACTIVE.includes(a.status)&&<button className="cancel-link" disabled={a.cancel_requested||cancelling===a.id} onClick={()=>void cancel(a.id)}>{a.cancel_requested||cancelling===a.id?'Stopping…':'Cancel analysis'}</button>}</div></article>)}</div>:<div className="lab-empty"><h3>Your first analysis starts with a place.</h3><p>Choose a study area and the diagnostics you want to explore.</p><button className="lab-primary" onClick={()=>navigate('new')}>Create an analysis →</button></div>}</section>}
        {view==='results'&&(selected?<><div className="result-task-picker"><label htmlFor="result-analysis">Analysis</label><select id="result-analysis" value={selected.id} onChange={e=>setSelectedId(e.target.value)}>{analyses.map(a=><option key={a.id} value={a.id}>{a.name} · {statusLabels[a.status]} · {new Date(a.created*1000).toLocaleDateString()}</option>)}</select><span className={`lab-status ${selected.status}`}>{statusLabels[selected.status]}</span></div><AnalysisResults key={selected.id} analysis={selected} diagnosticClient={clients.diagnostics} waterClient={clients.water}/></>:<div className="lab-empty"><h3>A landscape waiting to be explored.</h3><p>Submit an analysis to see maps, statistics and source details here.</p><button className="lab-primary" onClick={()=>navigate('new')}>Start an analysis →</button></div>)}
      </>}
      <footer className="lab-footer"><div><strong>NbS Diagnostics Lab.</strong><span>Public data. A shared understanding. <a href={`${import.meta.env.BASE_URL}guide.en.md`} target="_blank" rel="noreferrer">User guide ↗</a></span></div><p>Environmental screening · Review source coverage and methods<br/><span>Eight diagnostics · Online workspace v0.8</span></p></footer>
    </main>
  </div>;
}
