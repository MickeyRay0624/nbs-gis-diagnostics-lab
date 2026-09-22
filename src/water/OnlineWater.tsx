import { useEffect, useMemo, useRef, useState } from "react";
import type { VectorCollection } from "../analysis/model";
import { collectionBounds } from "../geo";
import { bboxBoundary, validateBoundary } from "../preparation/config";
import { MapPanel } from "../MapPanel";
import { WaterClient, prepareComputeSession, type WaterJob, type WaterRequest, type WaterResult, type Capabilities } from "./client";
import { WaterResults } from "./WaterResults";
import "./styles.css";

const ENDPOINT = import.meta.env.VITE_NBS_API_URL as string | undefined;
const SESSION = `nbs-water-access:${ENDPOINT ?? "unconfigured"}`;
const SAMPLE: WaterRequest = { mode: "sample", name: "Fayoum public sample, Egypt", bbox: [31, 28.9, 31.2, 29.1], start: "2021-07-01", end: "2021-07-31" };
const activeJob = (j: WaterJob) => j.status === "queued" || j.status === "running";

export function OnlineWater({ studyArea, studyName }: { studyArea: VectorCollection | null; studyName: string }) {
  const client = useMemo(() => ENDPOINT ? new WaterClient(ENDPOINT) : null, []);
  const [ready, setReady] = useState(false), [connectionAttempt, setConnectionAttempt] = useState(0);
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null), [jobs, setJobs] = useState<WaterJob[]>([]);
  const [error, setError] = useState<string | null>(null), [connecting, setConnecting] = useState(false), [submitting, setSubmitting] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null), [result, setResult] = useState<WaterResult | null>(null), [resultError, setResultError] = useState<string | null>(null);
  const [source, setSource] = useState<"sample" | "bbox" | "shared">("sample");
  const [name, setName] = useState("My study area"), [bounds, setBounds] = useState([85.75, 20.15, 85.95, 20.35]);
  const [start, setStart] = useState("2021-07-01"), [end, setEnd] = useState("2021-07-31");
  const [refresh, setRefresh] = useState(0);
  const pending = useRef<{ body: string; key: string } | null>(null);
  const selected = jobs.find(j => j.id === selectedId);

  const area = useMemo(() => {
    try {
      const boundary = source === "sample" ? bboxBoundary(...SAMPLE.bbox as [number, number, number, number]) : source === "shared" ? studyArea : bboxBoundary(...bounds as [number, number, number, number]);
      if (!boundary) return { boundary: null, error: "No shared study area is loaded.", areaKm2: 0 };
      const info = validateBoundary(boundary);
      return { boundary, error: null, areaKm2: info.areaKm2 };
    } catch (e) { return { boundary: null, error: e instanceof Error ? e.message : String(e), areaKm2: 0 }; }
  }, [source, studyArea, bounds]);

  useEffect(() => {
    if (!ENDPOINT || !client) return;
    let active = true;
    setConnecting(true); setError(null);
    void prepareComputeSession(ENDPOINT, sessionStorage.getItem(SESSION) ?? "").then(() => client.capabilities()).then(caps => {
      if (active) { sessionStorage.removeItem(SESSION); setCapabilities(caps); setReady(true); }
    }).catch(e => { if (active) setError(e instanceof Error ? e.message : "Could not connect to the compute service."); })
      .finally(() => { if (active) setConnecting(false); });
    return () => { active = false; };
  }, [client, connectionAttempt]);

  useEffect(() => {
    if (!client || !ready) return;
    const controller = new AbortController(); let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const [list, caps] = await Promise.all([client.jobs(controller.signal), client.capabilities(controller.signal)]);
        if (controller.signal.aborted) return;
        setJobs(list); setCapabilities(caps); setError(null);
        setSelectedId(previous => previous && list.some(j => j.id === previous) ? previous : list[0]?.id ?? null);
      } catch (e) { if (!controller.signal.aborted) setError(`${e instanceof Error ? e.message : "Connection interrupted."} Tasks continue on the server; reconnecting…`); }
      if (!controller.signal.aborted) timer = setTimeout(poll, 4000);
    };
    void poll();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [client, ready, refresh]);

  useEffect(() => {
    setResult(null); setResultError(null);
    if (!client || !selectedId || selected?.status !== "succeeded") return;
    const controller = new AbortController();
    client.result(selectedId, controller.signal).then(r => {
      if (r.schema !== "nbs-water/v1" || r.validation.status !== "passed") throw new Error("The result format or validation status is not supported.");
      if (!controller.signal.aborted) setResult(r);
    }).catch(e => { if (!controller.signal.aborted) setResultError(e.message); });
    return () => controller.abort();
  }, [client, selectedId, selected?.status, refresh]);

  const submit = async () => {
    if (!client || !area.boundary) return;
    setSubmitting(true); setError(null);
    try {
      const b = collectionBounds(area.boundary);
      const request: WaterRequest = source === "sample" ? SAMPLE : { mode: "custom", name: source === "shared" ? studyName : name, start, end, bbox: [b.west, b.south, b.east, b.north], boundary: area.boundary };
      const body = JSON.stringify(request);
      if (!pending.current || pending.current.body !== body) pending.current = { body, key: crypto.randomUUID() };
      const job = await client.submit(request, pending.current.key);
      pending.current = null;
      setJobs(previous => [job, ...previous.filter(j => j.id !== job.id)]); setSelectedId(job.id); setRefresh(x => x + 1);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not submit the task. You can retry safely."); }
    finally { setSubmitting(false); }
  };
  const cancel = async () => {
    if (!client || !selected) return;
    try { await client.cancel(selected.id); setRefresh(x => x + 1); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  };

  return <div id="online-water" className="online-water">
    <section className="card water-intro"><div><p className="step-number">ONLINE ANALYSIS · PYWAPOR</p><h2>Run your analysis online</h2><p>Choose an area and period. Submit a task, then return to explore evapotranspiration, root-zone water conditions and carbon production.</p></div><div className="water-flow"><span>1 · Submit</span><span>2 · Calculate</span><span>3 · Explore & download</span></div></section>
    {!ready || !client ? <section className="card water-connect"><h3>{connecting ? "Preparing your workspace…" : "Compute service"}</h3>{!ENDPOINT && <p>The online compute service has not been connected to this copy of the platform. Ask the platform administrator for the online workspace address.</p>}{error && <><p className="error-box" role="alert">{error}</p><button className="run-button" disabled={connecting} onClick={() => setConnectionAttempt(n => n + 1)}>Retry connection</button></>}</section> : <>
      <div className="water-connection"><span><i className={capabilities?.worker_online ? "online" : "offline"} />{capabilities?.worker_online ? "Compute service ready" : "Worker offline · submitted tasks wait in the queue"} · {capabilities?.analyst}</span></div>
      <div className="water-work-grid"><section id="water-task" className="card water-form"><p className="step-number">01 · NEW TASK</p><h3>Choose your analysis</h3>
        <label className="prep-field">Study area<select value={source} onChange={e => setSource(e.target.value as typeof source)}><option value="sample">Fayoum, Egypt · public sample</option><option value="shared" disabled={!capabilities?.custom_enabled || !studyArea}>Current NBS study area · {studyName}</option><option value="bbox" disabled={!capabilities?.custom_enabled}>Custom bounding box</option></select></label>
        {source === "sample" ? <p className="water-note">FAO satellite and weather inputs for 1–31 July 2021. The server runs pyWaPOR afresh and produces new results for this task.</p> : <><label className="prep-field">Study-area name<input value={source === "shared" ? studyName : name} disabled={source === "shared"} maxLength={80} onChange={e => setName(e.target.value)} /></label>{source === "bbox" && <div className="prep-bounds">{["West longitude", "South latitude", "East longitude", "North latitude"].map((label, i) => <label className="prep-field" key={label}>{label}<input type="number" step="0.01" value={bounds[i]} onChange={e => setBounds(b => b.map((v, j) => j === i ? Number(e.target.value) : v))} /></label>)}</div>}</>}
        <div className="water-fields"><label className="prep-field">Start date<input type="date" value={source === "sample" ? SAMPLE.start : start} disabled={source === "sample"} onChange={e => setStart(e.target.value)} /></label><label className="prep-field">End date · inclusive<input type="date" value={source === "sample" ? SAMPLE.end : end} disabled={source === "sample"} onChange={e => setEnd(e.target.value)} /></label></div>
        <p className="water-note">Pilot limit: {capabilities?.max_area_km2} km² enclosing rectangle and {capabilities?.max_days} days per task. Results remain available for {capabilities?.retention_days} days.</p>
        {!capabilities?.custom_enabled && <p className="water-note">Custom areas will become available after the administrator configures and verifies satellite and weather data access.</p>}
        {area.error && <p className="error-box" role="alert">{area.error}</p>}
        <p className="water-note">Submitting sends the selected area and dates to the compute service.</p><button className="run-button" disabled={submitting || !!area.error || (source === "sample" && !capabilities?.sample_ready)} onClick={() => void submit()}>{submitting ? "Submitting…" : "Submit calculation"}</button>
      </section><section id="water-jobs" className="card water-jobs"><p className="step-number">02 · YOUR TASKS</p><h3>Progress & recent results</h3><p className="water-note">Return in the same browser to find your tasks; clearing site data removes access to that history.</p>{!jobs.length && <p className="water-note">Your submitted tasks will appear here. Calculations continue after you close the page.</p>}
        <div className="water-job-list">{jobs.map(j => <button key={j.id} className={j.id === selectedId ? "selected" : ""} onClick={() => setSelectedId(j.id)} aria-pressed={j.id === selectedId}><span><strong>{j.request.name}</strong><small>{j.request.start} – {j.request.end}</small><small>{new Date(j.created * 1000).toLocaleString()}</small></span><em className={`water-status ${j.status}`}>{j.status}</em></button>)}</div>
        {selected && <div className="water-job-detail" role="status"><strong>{selected.stage}</strong>{activeJob(selected) && <progress aria-label="Calculation in progress" />}<small>Task {selected.id.slice(0, 8)} · updated {new Date(selected.updated * 1000).toLocaleTimeString()}</small>{selected.error && <p className="error-box">{selected.error}</p>}{selected.status === "expired" && <p>The retention period has ended. Submit again to calculate fresh results.</p>}{activeJob(selected) && <button disabled={selected.cancel_requested} onClick={() => void cancel()}>{selected.cancel_requested ? "Stopping…" : "Cancel task"}</button>}{selected.status === "succeeded" && !result && !resultError && <p>Loading results…</p>}</div>}
      </section></div>
      {error && <p className="error-box" role="alert">{error}</p>}{resultError && <p className="error-box" role="alert">{resultError} <button onClick={() => setRefresh(x => x + 1)}>Retry loading results</button></p>}
      {result && selectedId ? <section id="water-results" className="card water-result-card"><WaterResults key={selectedId} result={result} jobId={selectedId} client={client} /></section> : <section className="card water-area"><h3>{source === "sample" ? SAMPLE.name : source === "shared" ? studyName : name}</h3><MapPanel aoi={area.boundary} label={source === "sample" ? SAMPLE.name : source === "shared" ? studyName : name} loading={false} error={area.error} /></section>}
    </>}
  </div>;
}
