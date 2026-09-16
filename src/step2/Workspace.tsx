import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import LandCoverLab from "../LandCoverLab";
import { MapPanel } from "../MapPanel";
import { FRAGMENT_CLASSES } from "../analysis/model";
import { rasterImage } from "./render";
import type { Result, VectorCollection } from "../analysis/model";
import { validateVector } from "../analysis/io";
import { download } from "../analysis/presets";
import { digest, validateCatalog } from "./io";
import { NumericResults, number } from "./NumericResults";
import { MODULE_IDS } from "./model";
import type { Catalog, MapOverlay, ModuleId, ModuleResult, ModuleSpec, LayerResult } from "./model";

export type StudyAreaState = { aoi: VectorCollection | null; label: string; loading: boolean; error: string | null; extentOnly?: boolean };
const BASE = import.meta.env.BASE_URL;
const titles = ["Land-cover change", "Forest fragmentation", "Groundwater storage", "Drought & vegetation", "Climate extremes", "River flood hazard", "Land degradation"];
const symbols = ["◧", "♧", "≈", "◌", "☼", "≋", "▨"];

function Methods({ module, catalog }: { module: ModuleSpec; catalog: Catalog }) {
  return <section className="card result-section methods-card"><h2>How to use this diagnostic</h2>
    <p>{["lulc", "fragmentation"].includes(module.id) ? "Configure the land-cover inputs, choose LULC change or forest fragmentation, and run the analysis. The feature guide explains each control." : "Run the prepared Ganjam data, select a map layer, inspect coverage and the source scale, then export the numeric data and run manifest. Compare the outputs with the field-check questions before drawing conclusions."}</p>
    <details><summary>Calculation method & limitations</summary><ol>{module.method.map(m => <li key={m}>{m}</li>)}</ol><h3>Interpretation limits</h3><ul>{module.limitations.map(m => <li key={m}>{m}</li>)}</ul><h3>Sources</h3>{catalog.sources.filter(s => module.sources.includes(s.id)).map(s => <p key={s.id}><a href={s.url} target="_blank" rel="noreferrer">{s.name} ↗</a> · {s.version}<br /><small>{s.licence}</small></p>)}{!module.sources.length && <p>Land-cover input sources and versions are recorded in the analysis manifest.</p>}</details>
    <details><summary>Questions for Step 3 field checks</summary><ul>{module.fieldChecks.map(q => <li key={q}>{q}</li>)}</ul></details>
  </section>;
}

export default function Workspace() {
  const [catalog, setCatalog] = useState<Catalog | null>(null), [original, setOriginal] = useState<Catalog | null>(null);
  const [aoi, setAoi] = useState<VectorCollection | null>(null), [loadError, setLoadError] = useState<string | null>(null);
  const [selected, setSelected] = useState<ModuleId>("lulc"), [results, setResults] = useState<Partial<Record<ModuleId, ModuleResult>>>({});
  const [classic, setClassic] = useState<StudyAreaState>({ aoi: null, label: "Ganjam District, Odisha", loading: true, error: null });
  const [classicResult, setClassicResult] = useState<Result | null>(null);
  const [classicYear, setClassicYear] = useState(2022);
  const [overlay, setOverlay] = useState<MapOverlay | null>(null), [opacity, setOpacity] = useState(.8), [visible, setVisible] = useState(true);
  const [running, setRunning] = useState<ModuleId | null>(null), [status, setStatus] = useState("Choose a diagnostic to begin."), [error, setError] = useState<string | null>(null);
  const [uploaded, setUploaded] = useState<Record<string, File> | null>(null), [showSummary, setShowSummary] = useState(false);
  const worker = useRef<Worker | null>(null), token = useRef(0);
  const setStudyArea = useCallback((s: StudyAreaState) => setClassic(s), []);
  const setLandResult = useCallback((r: Result | null) => setClassicResult(r), []);
  const setMapOverlay = useCallback((value: MapOverlay | null) => setOverlay(value), []);
  const isClassic = selected === "lulc" || selected === "fragmentation";
  const active = catalog?.modules.find(m => m.id === selected), result = results[selected];
  const study = isClassic ? classic : { aoi, label: catalog?.studyArea.name ?? "Ganjam District, Odisha", loading: !aoi && !loadError, error: loadError };
  const landReady = !!classicResult?.transitions.length, forestReady = !!classicResult?.periods.some(p => p.fragmentation);
  const prepared = catalog?.modules.filter(m => m.status === "available").length ?? 0;

  const landOverlay = useMemo(() => {
    if (!classicResult || !isClassic) return null;
    const p = classicResult.periods.find(p => p.year === classicYear) ?? classicResult.periods.at(-1)!;
    const forest = selected === "fragmentation";
    if (forest && !p.fragmentation) return null;
    const g = classicResult.grid;
    const data = forest ? p.fragmentation!.data : p.data;
    const classes = forest ? FRAGMENT_CLASSES : classicResult.classes;
    const spec = { id:"land-cover-overview",title:`${forest ? "Forest fragmentation" : "Land cover"} · ${p.year}`,unit:"class",period:String(p.year),operation:"identity" as const,inputs:[],palette:"sequential" as const,interpretation:"See the land-cover analysis manifest.",categories:classes.map(c=>({value:c.code,label:c.name,color:c.color})) };
    return rasterImage({spec,grid:{width:g.width,height:g.height,crs:Number(g.crs.split(":")[1]),left:g.left,top:g.top,dx:g.cell,dy:g.cell},values:data,stats:{} as LayerResult["stats"]},classic.aoi).overlay;
  }, [classicResult, classicYear, selected, isClassic, classic.aoi]);
  const currentOverlay = isClassic ? landOverlay : overlay;

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([fetch(`${BASE}data/step2/catalog.json`, { signal: controller.signal }), fetch(`${BASE}data/ganjam-aoi.geojson`, { signal: controller.signal })])
      .then(async ([c, a]) => { if (!c.ok || !a.ok) throw new Error("The Ganjam data catalog could not be loaded. Reload to retry."); const catalog = validateCatalog(await c.json()), bytes = await a.arrayBuffer(); if (await digest(bytes) !== catalog.studyArea.sha256) throw new Error("The catalog and study-area boundary do not match."); setAoi(validateVector(JSON.parse(new TextDecoder().decode(bytes)))); setCatalog(catalog); setOriginal(catalog); })
      .catch(e => { if (e.name !== "AbortError") setLoadError(String(e.message ?? e)); });
    return () => { controller.abort(); token.current++; worker.current?.terminate(); };
  }, []);

  const run = async () => {
    if (!catalog || !active) return;
    const id = ++token.current, moduleId = active.id;
    setRunning(moduleId); setError(null); setStatus("Preparing the selected numeric inputs…");
    try {
      const files: Record<string, ArrayBuffer> | undefined = uploaded ? {} : undefined;
      if (uploaded && files) for (const rasterId of new Set(active.layers.flatMap(l => l.inputs.map(i => i.raster)))) {
        const asset = catalog.rasters.find(r => r.id === rasterId)!;
        if (!uploaded[asset.file]) throw new Error(`Select ${asset.file} together with the package catalog.`);
        files[asset.file] = await uploaded[asset.file].arrayBuffer();
      }
      if (id !== token.current) return;
      worker.current?.terminate();
      const w = new Worker(new URL("./worker.ts", import.meta.url), { type: "module" }); worker.current = w;
      w.onmessage = e => {
        if (id !== token.current) return;
        if (e.data.type === "progress") setStatus(e.data.message);
        if (e.data.type === "result") { setResults(r => ({ ...r, [moduleId]: e.data.result })); setStatus("Analysis complete. Review scale, coverage and methods below."); setRunning(null); w.terminate(); worker.current = null; }
        if (e.data.type === "error") { setError(e.data.message); setStatus("Check the input package and retry."); setRunning(null); w.terminate(); worker.current = null; }
      };
      w.onerror = () => { if (id !== token.current) return; setError("The analysis worker stopped. Try a smaller input package."); setRunning(null); w.terminate(); worker.current = null; };
      w.postMessage({ catalog, moduleId, base: new URL(`${BASE}data/step2/`, location.href).href, files }, files ? Object.values(files) : []);
    } catch (e) { if (id === token.current) { setError(String(e instanceof Error ? e.message : e)); setRunning(null); } }
  };
  const loadPackage = async (files: FileList | null) => {
    if (!files?.length || !original) return;
    setError(null);
    try {
      const list = [...files], json = list.filter(f => f.name.endsWith(".json"));
      if (json.length !== 1 || json[0].size > 2_000_000 || list.some(f => f.size > 100_000_000)) throw new Error("Select one catalog JSON (up to 2 MB) and its cropped GeoTIFFs (up to 100 MB each).");
      const c = validateCatalog(JSON.parse(await json[0].text()));
      if (c.studyArea.sha256 !== original.studyArea.sha256) throw new Error("This workspace expects the Ganjam pilot boundary. Prepare the package for the same AOI.");
      setCatalog(c); setUploaded(Object.fromEntries(list.filter(f => /\.tif$/i.test(f.name)).map(f => [f.name, f]))); setResults({}); setOverlay(null); setStatus("Local package loaded. Choose and run a module.");
    } catch (e) { setError(String(e instanceof Error ? e.message : e)); }
  };

  const report = () => {
    if (!catalog) return;
    const lines = ["# Ganjam Step 2 diagnostic review", "", `Generated: ${new Date().toISOString()}`, `Catalog: ${catalog.version}`, `Study area: ${catalog.studyArea.name} (${number(catalog.studyArea.areaKm2)} km²)`, "", "Status: technical screening; expert acceptance pending.", "", "## Protection applicability", catalog.protection.detail, "", "## Module evidence"];
    for (const id of MODULE_IDS) {
      const m = catalog.modules.find(m => m.id === id)!, r = results[id];
      lines.push("", `### ${m.title}`, m.question);
      if (r) for (const l of r.layers) lines.push(`- ${l.spec.title}: ${l.spec.categories ? "categorical output" : `${number(l.stats.mean)} ${l.spec.unit} (area-weighted mean)`}; valid area ${number(l.stats.validAreaKm2)} / ${number(l.stats.eligibleAreaKm2)} km²; ${l.spec.period}.`);
      else if (id === "lulc" && classicResult && landReady) {
        lines.push(`Dataset: ${String(classicResult.manifest.dataset)}`);
        for (const t of classicResult.transitions) lines.push(`- ${t.start}–${t.end}: ${number(t.changed * classicResult.grid.cell ** 2 / 1e6)} km² mapped class change within ${number(t.valid * classicResult.grid.cell ** 2 / 1e6)} km² common coverage.`);
      } else if (id === "fragmentation" && classicResult && forestReady) {
        lines.push(`Dataset: ${String(classicResult.manifest.dataset)}`);
        for (const p of classicResult.periods) for (const f of p.fragmentation?.metrics ?? []) lines.push(`- ${p.year} / ${f.stratum}: forest ${number(f.forest_ha)} ha; core ${number(f.core_ha)} ha; edge ${number(f.edge_ha)} ha; ${f.NP} connected patches; edge density ${number(f.ED)} m/ha.`);
      }
      else lines.push(`- ${m.status === "available" ? "Inputs available; not yet run in this session." : "Missing: " + m.missing?.join("; ")}`);
      lines.push("", "Method:", ...m.method.map(s => `- ${s}`), "", "Limitations:", ...m.limitations.map(s => `- ${s}`), "", "Step 3 field checks:", ...m.fieldChecks.map(s => `- ${s}`));
    }
    lines.push("", "## Sources", ...catalog.sources.map(s => `- ${s.name}; ${s.version}; ${s.licence}; ${s.url}`), "", "## Review gate", catalog.review.detail, "", "Deferred: additional-region ingestion, event forecasting, unified risk weighting, wildfire, irrigation, salinity / waterlogging, intervention selection and cost-benefit analysis.");
    download("ganjam-step2-review.md", lines.join("\n") + "\n", "text/markdown");
  };

  return <div className="app-shell step2-shell">
    <header className="topbar"><div className="brand"><span className="brand-mark" aria-hidden="true">N</span><div><p className="eyebrow">Nature-based Solutions · Geospatial Diagnostics</p><p className="brand-title">NbS Diagnostics Lab</p></div></div><div className="topbar-actions"><nav className="workspace-links" aria-label="Workspace navigation"><a href="#study-area">Overview</a><a href="#analysis-output">Analysis</a><a href="#step2-methods">Methods</a></nav><span className="version-label">v0.4 · Step 2</span></div></header>
    <main className="workspace">
      <section className="hero-panel"><div><p className="eyebrow accent">Ganjam · Odisha, India</p><h1>One landscape. Seven diagnostics.</h1><p className="hero-copy">Explore environmental change and climate pressures with public data. Follow each result from its source to a map, a statistic and a question for the field.</p></div><div className="step2-progress"><strong>{prepared}<span> / 7</span></strong><p>modules with prepared inputs</p><span className="status-tag neutral">Expert review pending</span></div></section>
      <details className="card execution-note"><summary>Where do the calculations happen?</summary><p>Earth Engine and Python prepare the public satellite and model inputs. This static website then calculates land-cover change, forest structure, map differences, land-degradation combinations and area statistics in your browser. Uploaded files stay on your device. The website does not run cloud jobs or contain Google credentials.</p><p>Each module lists its sources, preparation method, calculation rules and interpretation limits below the results.</p></details>
      <nav className="module-nav" aria-label="Diagnostic modules">{MODULE_IDS.map((id, i) => <button key={id} type="button" aria-pressed={selected === id} onClick={() => { setSelected(id); setError(null); }}><span className="module-symbol" aria-hidden="true">{symbols[i]}</span><span><small>0{i + 1}</small><strong>{titles[i]}</strong><em>{(results[id] || (id === "lulc" && landReady) || (id === "fragmentation" && forestReady)) ? "Results available" : catalog?.modules.find(m => m.id === id)?.status === "available" ? "Ready to run" : "Awaiting data"}</em></span></button>)}</nav>
      <section id="study-area" className="card map-panel" aria-labelledby="study-area-title"><div className="map-heading section-heading"><div><p className="step-number">STUDY AREA · SHARED OVERVIEW</p><h2 id="study-area-title">{study.label}</h2></div><div className="overview-actions"><span className="status-tag neutral">{isClassic && classic.extentOnly ? "Input raster extent" : "Selected boundary"}</span><label className="overlay-toggle"><input type="checkbox" disabled={!currentOverlay} checked={visible} onChange={e => setVisible(e.target.checked)} />Result layer</label></div></div>
        <MapPanel {...study} overlay={visible ? currentOverlay : null} opacity={opacity} />
        <div className="overlay-slider">{isClassic && classicResult && <select aria-label="Overview map year" value={classicResult.periods.some(p=>p.year===classicYear) ? classicYear : classicResult.periods.at(-1)!.year} onChange={e=>setClassicYear(Number(e.target.value))}>{classicResult.periods.map(p=><option key={p.year} value={p.year}>{p.year}</option>)}</select>}<label htmlFor="layer-opacity">Layer opacity</label><input id="layer-opacity" disabled={!currentOverlay} type="range" min={0} max={1} step={.05} value={opacity} onChange={e => setOpacity(Number(e.target.value))} /><span>{currentOverlay ? `${Math.round(opacity * 100)}%` : "Run a diagnostic to add a layer"}</span></div>
        <p className="overview-note">The overview stays in place when you run an analysis or switch diagnostics. Use “Locate study area” to return to the boundary.</p>
      </section>
      {loadError && <p className="error-box" role="alert">{loadError}</p>}
      <div id="analysis-output" className="step2-analysis">
        {!isClassic && active && <section className="card module-run-card"><div><p className="step-number">0{MODULE_IDS.indexOf(selected) + 1} · {active.title.toUpperCase()}</p><h2>{active.question}</h2><p className="section-copy">{uploaded ? "Local numeric package" : "Prepared public data"} · Ganjam · source resolution retained</p></div><div className="module-run-actions"><button className="run-button" disabled={!!running || active.status !== "available"} onClick={run}>{running === selected ? "Computing…" : result ? "Run again →" : "Run diagnostic →"}</button>{running && <button className="quiet-button" onClick={() => { token.current++; worker.current?.terminate(); worker.current = null; setRunning(null); setStatus("Analysis cancelled."); }}>Cancel {titles[MODULE_IDS.indexOf(running)]}</button>}</div><p className="run-status" role="status">{status}</p>{active.status === "needs-data" && <div className="data-needed"><strong>Data preparation required</strong><p>{active.missing?.join(" ")}</p><p>No result is inferred from missing inputs.</p></div>}{error && <p className="error-box" role="alert">{error}</p>}</section>}
        <div hidden={!isClassic}><LandCoverLab onStudyArea={setStudyArea} onResult={setLandResult} selectedView={selected === "fragmentation" ? "fragmentation" : "lulc"} /></div>
        {!isClassic && result && catalog && <NumericResults key={`${selected}-${String(result.manifest.computed_at)}`} result={result} catalog={catalog} aoi={aoi} onOverlay={setMapOverlay} />}
      </div>
      {active && catalog && <div id="step2-methods"><Methods module={active} catalog={catalog} /></div>}
      <section className="card result-section review-section"><div className="section-heading"><div><p className="step-number">EVIDENCE → FIELD CHECKS</p><h2>Step 2 review package</h2></div><button className="quiet-button" disabled={!catalog} onClick={report}>Download diagnostic brief ↓</button></div><p className="section-copy">Keep different periods, scales and uncertainties visible. Data availability and calculation success are separate from expert acceptance.</p><button className="text-button" onClick={() => setShowSummary(v => !v)} aria-expanded={showSummary}>{showSummary ? "Hide" : "View"} completion checklist</button>
        {showSummary && catalog && <div className="table-scroll"><table><thead><tr><th>Requirement</th><th>Current evidence</th></tr></thead><tbody>{MODULE_IDS.map(id => <tr key={id}><th>{titles[MODULE_IDS.indexOf(id)]}</th><td>{results[id] ? "Calculated in this session · review pending" : ((id === "lulc" && landReady) || (id === "fragmentation" && forestReady)) ? "Calculated in this session · review pending" : catalog.modules.find(m => m.id === id)?.status === "available" ? "Inputs available · run required" : "Numeric inputs required"}</td></tr>)}<tr><th>Protection / OECM applicability</th><td>{catalog.protection.detail}</td></tr><tr><th>Expert acceptance</th><td>{catalog.review.detail}</td></tr></tbody></table></div>}
        <details className="package-import"><summary>Use a prepared Ganjam data package</summary><p>Select a catalog JSON and its GeoTIFFs together. The catalog records bands, periods, units, sources, methods and hashes. Files stay on your device. The boundary must match Ganjam.</p><input type="file" accept=".json,.tif" multiple disabled={!!running} aria-label="Prepared Ganjam catalog and rasters" onChange={e => { void loadPackage(e.target.files); e.target.value = ""; }} />{uploaded && <button className="quiet-button" disabled={!!running} onClick={() => { setCatalog(original); setUploaded(null); setResults({}); setOverlay(null); setError(null); }}>Restore public package</button>}{error && isClassic && <p className="error-box" role="alert">{error}</p>}</details>
      </section>
    </main><footer><span>NbS Diagnostics Lab · public-data screening for technical review</span><a href="https://github.com/MickeyRay0624/nbs-gis-diagnostics-lab" target="_blank" rel="noreferrer">Code & methods ↗</a><span>geoBoundaries · OpenStreetMap · sources in each module</span></footer>
  </div>;
}
