import { useEffect, useMemo, useState } from "react";
import { MapPanel } from "../MapPanel";
import { TimeSeries, number } from "../step2/NumericResults";
import { download } from "../analysis/presets";
import { rasterImage, palettes, domain } from "../step2/render";
import type { LayerResult, ModuleId } from "../step2/model";
import { readOnlineLayer, type DiagnosticClient, type DiagnosticResult } from "./client";

export function DiagnosticResults({result,jobId,client,initialModuleId,embedded=false}:{result:DiagnosticResult;jobId:string;client:DiagnosticClient;initialModuleId?:ModuleId;embedded?:boolean}){
  const [moduleId,setModuleId]=useState(initialModuleId??result.modules.find(m=>m.status==="available")?.id);
  const [layerId,setLayerId]=useState("");
  const [layer,setLayer]=useState<LayerResult|null>(null),[error,setError]=useState<string|null>(null),[busy,setBusy]=useState(false),[opacity,setOpacity]=useState(.8);
  const module=result.modules.find(m=>m.id===moduleId);
  const layers=result.layers.filter(l=>l.module===moduleId);
  const selected=layers.find(l=>l.id===layerId)??layers[0];
  const asset=result.assets.find(a=>a.file===selected?.file);
  useEffect(()=>{
    const controller=new AbortController();setLayer(null);setError(null);
    if(selected&&asset)client.asset(jobId,asset,controller.signal).then(b=>readOnlineLayer(b,selected,asset)).then(l=>{if(!controller.signal.aborted)setLayer(l);}).catch(e=>{if(!controller.signal.aborted)setError(e.message);});
    return()=>controller.abort();
  },[selected,asset,jobId,client]);
  const rendered=useMemo(()=>layer?rasterImage(layer,result.boundary):null,[layer,result.boundary]);
  const limits=layer?domain(layer):null;
  async function save(file:string){
    const a=result.assets.find(a=>a.file===file);if(!a)return;
    setBusy(true);setError(null);
    try{download(a.file,await client.asset(jobId,a),a.media_type);}catch(e){setError((e as Error).message);}finally{setBusy(false);}
  }
  return <section id="diagnostic-results" className={embedded?"water-results embedded-result":"card water-results"} aria-label="Online diagnostic results">
    {!embedded&&<><div className="section-heading"><div><p className="step-number">SERVER RESULTS · {result.validation.completed_modules.length} / {result.modules.length} COMPLETE</p><h2>{result.name}</h2><p className="section-copy">{result.validation.checks} completed checks · {new Date(result.prepared_at).toLocaleString()}</p></div><span className={`status-tag ${result.complete?"ready":"neutral"}`}>{result.complete?"Calculation complete":"Partial results"}</span></div>
    <p className="section-copy">{result.scope}</p>
    <nav className="diagnostic-results-tabs" aria-label="Completed diagnostics">{result.modules.map(m=><button key={m.id} aria-pressed={m.id===moduleId} onClick={()=>{setModuleId(m.id);setLayerId("");}}><strong>{m.title}</strong><small>{m.status==="available"?"Results available":m.reason_code==="no_valid_observations"?"No valid data in this area":"Not completed"}</small></button>)}</nav>
    </>}
    {module?.status==="needs-data"?<div className="prep-callout"><strong>{module.reason_code==="no_valid_observations"?"No usable source data for this selection.":"This diagnostic did not complete."}</strong>{module.missing?.map(m=><p key={m}>{m}</p>)}<p>Completed diagnostics remain available in the module list.</p></div>:<>
      <label className="prep-field">Map layer<select value={selected?.id??""} onChange={e=>setLayerId(e.target.value)}>{layers.map(l=><option key={l.id} value={l.id}>{l.spec.title}</option>)}</select></label>
      {selected&&<div className="water-metrics"><div><small>{selected.spec.categories?"Classified area":"Area-weighted mean"}</small><strong>{number(selected.spec.categories?selected.stats.validAreaKm2:selected.stats.mean)} <em>{selected.spec.categories?"km²":selected.spec.unit}</em></strong></div><div><small>Valid coverage</small><strong>{number(selected.stats.coveragePct,1)}<em>%</em></strong><small>{number(selected.stats.missingAreaKm2)} km² missing / excluded</small></div><div><small>Source & analysis scale</small><strong className="water-period">{selected.nativeResolution}</strong><small>{selected.spec.period}</small></div></div>}
      {!layer&&!error&&<p role="status">Loading the selected server result…</p>}
      <MapPanel aoi={result.boundary} label={result.name} loading={false} error={null} overlay={rendered?.overlay} opacity={opacity} showMarker={false}/>
      <div className="overlay-slider"><label htmlFor="diagnostic-opacity">Map opacity</label><input id="diagnostic-opacity" type="range" min={0} max={1} step={.05} value={opacity} onChange={e=>setOpacity(Number(e.target.value))}/></div>
      {layer&&limits&&<div className="numeric-legend">{layer.spec.categories?layer.spec.categories.map(c=><span key={c.value}><i style={{background:c.color}}/>{c.label}</span>):<><div className="gradient-legend" style={{background:`linear-gradient(90deg,${palettes[layer.spec.palette].join(",")})`}}/><div className="legend-endpoints"><span>{number(limits[0])}</span><span>{number(limits[1])} {layer.spec.unit}</span></div></>}<small>Transparent = missing or outside the eligible area.</small></div>}
      {selected&&<p className="interpretation">{selected.spec.interpretation}</p>}
      {!!selected?.stats.classes.length&&<div className="table-scroll"><table><thead><tr><th>Class / threshold</th><th>Area (km²)</th><th>Valid area (%)</th></tr></thead><tbody>{selected.stats.classes.map(c=><tr key={c.label}><th>{c.label}</th><td>{number(c.areaKm2)}</td><td>{number(c.percent)}</td></tr>)}</tbody></table></div>}
      {module?.series?.map(s=><TimeSeries key={s.title} {...s}/>)}
      {result.tables.filter(t=>t.module===moduleId).map(t=><details key={t.file}><summary>{t.title}</summary><div className="table-scroll"><table><thead><tr>{Object.keys(t.rows[0]??{}).map(k=><th key={k}>{k.replaceAll("_"," ")}</th>)}</tr></thead><tbody>{t.rows.map((row,i)=><tr key={i}>{Object.entries(row).map(([k,v])=><td key={k}>{typeof v==="number"?number(v):v??"No data"}</td>)}</tr>)}</tbody></table></div><button disabled={busy} onClick={()=>void save(t.file)}>Download table CSV ↓</button></details>)}
      <details className="water-methods"><summary>Methods, sources & interpretation</summary><ul>{module?.method?.map(m=><li key={m}>{m}</li>)}</ul><ul>{module?.limitations?.map(m=><li key={m}>{m}</li>)}</ul>{result.sources.filter(s=>module?.sources?.includes(s.id)).map(s=><p key={s.id}><a href={s.url} target="_blank" rel="noreferrer">{s.name} ↗</a> · {s.version}<br/>{s.licence}</p>)}</details>
    </>}
    {error&&<p role="alert" className="error-box">{error}</p>}
    <div className="output-actions">{asset&&module?.status==="available"&&<button disabled={busy} onClick={()=>void save(asset.file)}>Layer GeoTIFF ↓</button>}<button disabled={busy} onClick={()=>void save("statistics.csv")}>Statistics CSV ↓</button><button disabled={busy} onClick={()=>void save("results.zip")}>All results ↓</button><button disabled={busy} onClick={()=>void save("run-manifest.json")}>Run details ↓</button></div>
    {busy&&<p role="status">Downloading and checking the result file…</p>}
  </section>;
}
