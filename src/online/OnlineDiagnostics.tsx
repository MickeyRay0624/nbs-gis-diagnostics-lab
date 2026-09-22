import { useEffect, useMemo, useRef, useState } from "react";
import type { VectorCollection } from "../analysis/model";
import { MODULE_IDS, type ModuleId } from "../step2/model";
import { PreparationWizard } from "../preparation/PreparationWizard";
import { DiagnosticClient, type DiagnosticCapabilities, type DiagnosticJob, type DiagnosticRequest, type DiagnosticResult } from "./client";
import { DiagnosticResults } from "./DiagnosticResults";
import { prepareComputeSession } from "../water/client";
import "../water/styles.css";
import "./styles.css";

const ENDPOINT=import.meta.env.VITE_NBS_API_URL as string|undefined;
const SESSION=`nbs-water-access:${ENDPOINT??"unconfigured"}`;
const titles=["Land-cover change","Forest fragmentation","Groundwater storage","Drought & vegetation","Climate extremes","River flood hazard","Land degradation"];

export function OnlineDiagnostics({ganjam}:{ganjam:VectorCollection|null}){
  const client=useMemo(()=>ENDPOINT?new DiagnosticClient(ENDPOINT):null,[]);
  const [ready,setReady]=useState(false),[connectionAttempt,setConnectionAttempt]=useState(0);
  const [caps,setCaps]=useState<DiagnosticCapabilities|null>(null),[jobs,setJobs]=useState<DiagnosticJob[]>([]),[selectedId,setSelectedId]=useState<string|null>(null);
  const [result,setResult]=useState<DiagnosticResult|null>(null),[error,setError]=useState<string|null>(null),[resultError,setResultError]=useState<string|null>(null),[pollError,setPollError]=useState<string|null>(null),[connecting,setConnecting]=useState(false),[busy,setBusy]=useState(false);
  const [mode,setMode]=useState("ganjam"),[modules,setModules]=useState<ModuleId[]>([...MODULE_IDS]),[refresh,setRefresh]=useState(0);
  const pending=useRef<{body:string;key:string}|null>(null);
  const selected=jobs.find(j=>j.id===selectedId);
  useEffect(()=>{
    if(!ENDPOINT||!client)return;
    let active=true;
    setConnecting(true);setError(null);
    void prepareComputeSession(ENDPOINT,sessionStorage.getItem(SESSION)??"").then(()=>client.capabilities()).then(c=>{
      if(active){sessionStorage.removeItem(SESSION);setCaps(c);setReady(true);}
    }).catch(e=>{if(active)setError((e as Error).message);}).finally(()=>{if(active)setConnecting(false);});
    return()=>{active=false;};
  },[client,connectionAttempt]);
  useEffect(()=>{
    if(!client||!ready)return;
    const controller=new AbortController();let timer:ReturnType<typeof setTimeout>;
    async function poll(){
      try{const [j,c]=await Promise.all([client!.jobs(controller.signal),client!.capabilities(controller.signal)]);if(controller.signal.aborted)return;setJobs(j);setCaps(c);setPollError(null);setSelectedId(id=>id&&j.some(v=>v.id===id)?id:j[0]?.id??null);}
      catch(e){if(!controller.signal.aborted)setPollError((e as Error).message);}
      if(!controller.signal.aborted)timer=setTimeout(poll,4000);
    }
    void poll();return()=>{controller.abort();clearTimeout(timer);};
  },[client,ready,refresh]);
  useEffect(()=>{
    setResult(null);setResultError(null);
    if(!client||!selectedId||!["succeeded","partial"].includes(selected?.status??""))return;
    const controller=new AbortController();
    client.result(selectedId,controller.signal).then(r=>{if(r.schema!=="nbs-online-diagnostics/v1"||r.validation.status!=="passed")throw new Error("The server result format or validation status is unsupported.");if(!controller.signal.aborted)setResult(r);}).catch(e=>{if(!controller.signal.aborted)setResultError(e.message);});
    return()=>controller.abort();
  },[client,selectedId,selected?.status,refresh]);
  async function submit(request:DiagnosticRequest){
    if(!client)throw new Error("Connect to the compute service first.");
    setBusy(true);setError(null);
    try{
      const body=JSON.stringify(request);if(!pending.current||pending.current.body!==body)pending.current={body,key:crypto.randomUUID()};
      const job=await client.submit(request,pending.current.key);pending.current=null;setJobs(j=>[job,...j.filter(x=>x.id!==job.id)]);setSelectedId(job.id);setRefresh(n=>n+1);
    }catch(e){setError((e as Error).message);throw e;}finally{setBusy(false);}
  }
  async function cancel(){try{if(client&&selected){await client.cancel(selected.id);setRefresh(n=>n+1);}}catch(e){setError((e as Error).message);}}
  return <div id="online-diagnostics" className="online-water">
    <section className="card water-intro"><div><p className="step-number">SEVEN DIAGNOSTICS · ONLINE</p><h2>Run your landscape analysis</h2><p>Choose a study area and diagnostics. The server prepares data, calculates results and keeps your maps ready to explore.</p></div><div className="water-flow"><span>1 · Choose & submit</span><span>2 · Server calculates</span><span>3 · Explore & download</span></div></section>
    {!ready||!client?<section className="card water-connect"><h3>{connecting?"Preparing your workspace…":"Compute service"}</h3>{!ENDPOINT&&<p>The compute service has not been connected to this copy of the platform.</p>}{error&&<><p role="alert" className="error-box">{error}</p><button className="run-button" disabled={connecting} onClick={()=>setConnectionAttempt(n=>n+1)}>Retry connection</button></>}</section>:<>
      <div className="water-connection"><span><i className={caps?.worker_online?"online":"offline"}/>{caps?.worker_online?"Compute service ready":"Worker offline · tasks remain queued"} · {caps?.analyst}</span></div>
      <section id="diagnostic-task" className="card water-form"><p className="step-number">01 · NEW ANALYSIS</p><h3>Choose your workflow</h3><label className="prep-field">Analysis input<select value={mode} onChange={e=>setMode(e.target.value)}><option value="ganjam">Ganjam · existing verified inputs</option><option value="custom">New study area · server downloads data</option></select></label>
      {mode==="ganjam"?<><p className="water-note">Recalculate the platform's existing Ganjam inputs on the server. Source periods remain fixed and are documented in each result. This does not download a new NASA time series.</p><div className="prep-module-options">{MODULE_IDS.map((id,i)=><label key={id} className={modules.includes(id)?"selected":""}><input type="checkbox" checked={modules.includes(id)} onChange={()=>setModules(m=>m.includes(id)?m.filter(x=>x!==id):[...m,id])}/><span><strong>{titles[i]}</strong><small>Existing Ganjam inputs · fresh calculation</small></span></label>)}</div><button className="run-button" disabled={busy||!modules.length||!caps?.sample_ready} onClick={()=>void submit({mode:"ganjam",name:"Ganjam District, Odisha",modules}).catch(()=>{})}>{busy?"Submitting…":"Submit calculation"}</button></>:<PreparationWizard ganjam={ganjam} online={{onSubmit:submit,enabledModules:caps?.modules.filter(m=>m.custom_enabled).map(m=>m.id)??[],maxClimateRequests:caps?.max_climate_requests??240}}/>}
      <p className="water-note">Heavy tasks share one compute slot with Water & productivity. Up to two pending tasks per workspace. Return in the same browser to find your tasks; clearing site data removes access to that history. Results remain available for {caps?.retention_days??30} days.</p></section>
      <section id="diagnostic-jobs" className="card water-jobs"><p className="step-number">02 · YOUR TASKS</p><h3>Progress & recent results</h3>{!jobs.length&&<p>Your submitted tasks will appear here.</p>}<div className="water-job-list">{jobs.map(j=><button key={j.id} className={j.id===selectedId?"selected":""} aria-pressed={j.id===selectedId} onClick={()=>setSelectedId(j.id)}><span><strong>{j.request.name}</strong><small>{j.request.modules.length} diagnostics · {new Date(j.created*1000).toLocaleString()}</small></span><em className={`water-status ${j.status}`}>{j.status}</em></button>)}</div>
      {selected&&<div className="water-job-detail" role="status"><strong>{selected.stage}</strong><small>Task {selected.id.slice(0,8)} · updated {new Date(selected.updated*1000).toLocaleTimeString()}</small>{["queued","running"].includes(selected.status)&&<><progress aria-label="Calculation in progress"/><button disabled={selected.cancel_requested} onClick={()=>void cancel()}>{selected.cancel_requested?"Stopping…":"Cancel task"}</button></>}{selected.error&&<p className="error-box">{selected.error}</p>}{selected.status==="expired"&&<p>The result retention period has ended. Submit a new calculation.</p>}</div>}</section>
      {error&&<p role="alert" className="error-box">{error}</p>}{pollError&&<p role="alert" className="error-box">{pollError}</p>}{resultError&&<p role="alert" className="error-box">{resultError}<button onClick={()=>setRefresh(n=>n+1)}>Retry loading results</button></p>}
      {result&&selectedId&&<DiagnosticResults key={selectedId} result={result} jobId={selectedId} client={client}/>}
    </>}
  </div>;
}
