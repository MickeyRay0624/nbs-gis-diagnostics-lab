import { useEffect, useMemo, useRef, useState } from "react";
import type { CrosswalkRow, Result, RunRequest, VectorCollection } from "./analysis/model";
import { readRaster, readRasterFootprint, readVector, validateVector } from "./analysis/io";
import { csv, download, ESRI, GLCFCS, PALETTE, parseCrosswalk, WORLDCOVER } from "./analysis/presets";
import type { StudyAreaState } from "./step2/Workspace";
import { Results } from "./Results";
import { HelpGuide } from "./HelpGuide";
import { FileUpload } from "./FileUpload";

type DemoMetadata = { name: string; inputs: { year: number; file: string; sha256: string }[]; [key: string]: unknown };
type Upload = { year: number; file?: File };
const BASE = import.meta.env.BASE_URL;
const message = (e: unknown) => e instanceof Error ? e.message : String(e);

export default function LandCoverLab({ onStudyArea, onResult, selectedView, studyAreaOverride }: { studyAreaOverride?: { aoi: VectorCollection; label: string }; selectedView: "lulc" | "fragmentation"; onStudyArea: (value: StudyAreaState) => void; onResult: (value: Result | null) => void }) {
  const [aoi, setAoi] = useState<VectorCollection | null>(null);
  const [footprint, setFootprint] = useState<VectorCollection | null>(null);
  const [footprintLoading, setFootprintLoading] = useState(false);
  const [footprintError, setFootprintError] = useState<string | null>(null);
  const [metadata, setMetadata] = useState<DemoMetadata | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [dataset, setDataset] = useState(studyAreaOverride ? "upload" : "demo");
  const [preset, setPreset] = useState("glc");
  const [module, setModule] = useState<RunRequest["module"]>("both");
  const [years, setYears] = useState([2002, 2012, 2022]);
  const [uploads, setUploads] = useState<Upload[]>([{ year: 2020 }, { year: 2021 }]);
  const [rows, setRows] = useState<CrosswalkRow[]>(GLCFCS);
  const [forest, setForest] = useState([2]);
  const [cell, setCell] = useState(50), [edge, setEdge] = useState(50);
  const [boundaryEdge, setBoundaryEdge] = useState(false);
  const [vectors, setVectors] = useState<{ aoi?: VectorCollection; protectedAreas?: VectorCollection; oecm?: VectorCollection }>(studyAreaOverride ? { aoi: studyAreaOverride.aoi } : {});
  const [vectorNames, setVectorNames] = useState<Record<string, string>>(studyAreaOverride ? { aoi: studyAreaOverride.label } : {});
  const [result, setResult] = useState<Result | null>(null);
  const [running, setRunning] = useState(false), [inspecting, setInspecting] = useState(false);
  const [status, setStatus] = useState("Ready to analyse public data"), [error, setError] = useState<string | null>(null);
  const worker = useRef<Worker | null>(null);
  const runToken = useRef(0);
  const uniqueClasses = useMemo(() => [...new Map(rows.map(r => [r.code, r])).values()].sort((a, b) => a.code - b.code), [rows]);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([fetch(`${BASE}data/ganjam-aoi.geojson`, { signal: controller.signal }), fetch(`${BASE}data/glcfcs/metadata.json`, { signal: controller.signal })])
      .then(async responses => { if (responses.some(r => !r.ok)) throw new Error("Public example could not be loaded. Reload to retry, or upload your own rasters."); return Promise.all(responses.map(r => r.json())); })
      .then(([boundary, meta]) => { setAoi(validateVector(boundary)); setMetadata(meta); })
      .catch(e => { if (e.name !== "AbortError") setLoadError(message(e)); });
    return () => { controller.abort(); runToken.current++; worker.current?.terminate(); };
  }, []);

  useEffect(() => { setResult(null); setError(null); setStatus("Ready to run with the current settings"); }, [dataset, preset, module, years, uploads, rows, forest, cell, edge, boundaryEdge, vectors]);

  // The runner sorts years before selecting its reference grid; preview the same input.
  const firstFile = [...uploads].sort((a, b) => a.year - b.year)[0]?.file;
  useEffect(() => {
    let active = true;
    setFootprint(null); setFootprintError(null); setFootprintLoading(false);
    if (dataset === "upload" && firstFile && !vectors.aoi) {
      setFootprintLoading(true);
      readRasterFootprint(firstFile).then(value => { if (active) setFootprint(value); })
        .catch(e => { if (active) setFootprintError(message(e)); })
        .finally(() => { if (active) setFootprintLoading(false); });
    }
    return () => { active = false; };
  }, [dataset, firstFile, vectors.aoi]);

  const mapAoi = dataset === "demo" ? aoi : vectors.aoi ?? footprint;
  const areaLabel = dataset === "demo" ? "Ganjam District, Odisha" : vectors.aoi ? vectorNames.aoi : firstFile?.name ?? "Your study area";

  useEffect(() => { onStudyArea({ aoi: mapAoi, label: areaLabel, extentOnly: dataset === "upload" && !vectors.aoi, loading: dataset === "demo" ? !aoi && !loadError : footprintLoading, error: dataset === "demo" ? loadError : footprintError }); }, [mapAoi, areaLabel, dataset, vectors.aoi, aoi, loadError, footprintLoading, footprintError, onStudyArea]);
  useEffect(() => { onResult(result); }, [result, onResult]);

  const choosePreset = (name: string) => {
    setPreset(name); setRows(name === "worldcover" ? WORLDCOVER : name === "esri" ? ESRI : name === "glc" ? GLCFCS : []);
    setForest(name === "worldcover" ? [10, 95] : ["esri", "glc"].includes(name) ? [2] : []);
  };
  const inspect = async () => {
    setInspecting(true); setError(null);
    try {
      const selected = uploads.filter(u => u.file);
      if (!selected.length) throw new Error("Select at least one GeoTIFF first.");
      const codes = new Set<number>();
      for (const u of selected) { const raster = await readRaster(await u.file!.arrayBuffer(), u.year, u.file!.name); for (const code of raster.data) if (code) codes.add(code); }
      if (codes.size > 100) throw new Error("More than 100 classes found. Confirm this is a categorical land-cover raster.");
      const definitions = preset === "worldcover" ? WORLDCOVER : preset === "esri" ? ESRI : preset === "glc" ? GLCFCS : [];
      const newRows = [...codes].sort((a, b) => a - b).map((code, i) => definitions.find(r => r.source === code) ?? { source: code, code: code < 1000 ? code : i + 1, name: `Class ${code}`, color: PALETTE[i % PALETTE.length] });
      setRows(newRows); setForest(newRows.filter(r => preset === "worldcover" ? [10, 95].includes(r.source) : preset === "esri" ? r.source === 2 : preset === "glc" ? (r.source >= 51 && r.source <= 92) || r.source === 185 : false).map(r => r.code));
      setStatus(`Loaded ${codes.size} source classes. Review the legend and forest definition.`);
    } catch (e) { setError(message(e)); } finally { setInspecting(false); }
  };
  const loadVector = async (key: "aoi" | "protectedAreas" | "oecm", file?: File) => {
    if (!file) return; setInspecting(true); setError(null);
    try { const vector = await readVector(file); setVectors(v => ({ ...v, [key]: vector })); setVectorNames(v => ({ ...v, [key]: file.name })); }
    catch (e) { setError(message(e)); } finally { setInspecting(false); }
  };
  const run = async () => {
    const token = ++runToken.current;
    setError(null); setResult(null); setRunning(true); setStatus("Preparing input data…");
    try {
      if (!rows.length) throw new Error("Load raster class codes or import a crosswalk CSV first.");
      const sources: RunRequest["sources"] = dataset === "demo" ? metadata!.inputs.filter(s => years.includes(s.year)).map(s => ({ year: s.year, name: s.file, url: new URL(`${BASE}data/glcfcs/${s.file}`, location.href).href, expectedSha256: s.sha256 })) : await Promise.all(uploads.map(async u => {
        if (!u.file) throw new Error(`Select a GeoTIFF for ${u.year}, or remove that period.`);
        if (u.file.size > 100_000_000) throw new Error("GeoTIFF upload limit is 100 MB per file. Crop the input first.");
        return { year: u.year, name: u.file.name, buffer: await u.file.arrayBuffer() };
      }));
      if (token !== runToken.current) return;
      const request: RunRequest = { sources, crosswalk: rows, forestCodes: forest, edge, cell, countBoundary: boundaryEdge, module,
        dataset: dataset === "demo" ? "GLC-FCS30D · Ganjam public-data diagnostic" : `${{ worldcover: "WorldCover", esri: "ESRI land cover", glc: "GLC-FCS30D", custom: "Custom land cover" }[preset]} · uploaded rasters`,
        aoi: dataset === "demo" ? aoi! : vectors.aoi,
        protectedAreas: vectors.protectedAreas, oecm: vectors.oecm,
        provenance: dataset === "demo" ? metadata! : { source: "User uploads", preset, vector_files: vectorNames } };
      worker.current?.terminate();
      const w = new Worker(new URL("./analysis/worker.ts", import.meta.url), { type: "module" }); worker.current = w;
      w.onmessage = event => {
        if (token !== runToken.current) return;
        if (event.data.type === "progress") setStatus(event.data.message);
        if (event.data.type === "result") { setResult(event.data.result); setRunning(false); setStatus("Analysis complete · results reflect the selected settings"); w.terminate(); worker.current = null; }
        if (event.data.type === "error") { setError(event.data.message); setRunning(false); setStatus("Check the inputs and run again"); w.terminate(); worker.current = null; }
      };
      w.onerror = () => { if (token !== runToken.current) return; setError("The analysis worker stopped. Try a smaller study area or a coarser resolution."); setRunning(false); w.terminate(); worker.current = null; };
      w.postMessage(request, sources.flatMap(s => s.buffer ? [s.buffer] : []));
    } catch (e) { if (token === runToken.current) { setError(message(e)); setRunning(false); } }
  };

  return <div className="land-cover-workspace">
      {dataset === "demo" && <div className="demo-notice"><strong>Consistent land-cover series</strong><span>GLC-FCS30D 2002, 2012 and 2022 use one product and an editable ten-class legend. Mapped change still needs local verification. <a href="https://essd.copernicus.org/articles/16/1353/2024/" target="_blank" rel="noreferrer">Source & licence ↗</a></span></div>}
      <HelpGuide />
      <div className="lab-grid">
        <aside className="control-panel card">
          <div className="section-heading"><div><p className="step-number">01 · RUN SETUP</p><h2>Configure your analysis</h2></div></div>
          <fieldset disabled={running || inspecting} className="controls-fieldset">
            <label className="field-label" htmlFor="dataset">Data source</label><select id="dataset" value={dataset} onChange={e => { setDataset(e.target.value); if (e.target.value === "demo") { choosePreset("glc"); setCell(50); setEdge(50); } }}>{!studyAreaOverride && <option value="demo">Public data · Ganjam GLC-FCS30D</option>}<option value="upload">Upload your own GeoTIFFs</option></select>
            {dataset === "demo" ? <><p className="field-help">Full Ganjam district · 30 m source → 50 m equal-area grid · no account needed.</p><fieldset className="period-fieldset"><legend className="field-label">Analysis years</legend><div className="checkbox-list inline">{[2002, 2012, 2022].map(y => <label key={y}><input type="checkbox" checked={years.includes(y)} onChange={e => setYears(e.target.checked ? [...years, y].sort() : years.filter(v => v !== y))} />{y}</label>)}</div></fieldset></> : <>
              <label className="field-label" htmlFor="preset">Source classification</label><select id="preset" value={preset} onChange={e => choosePreset(e.target.value)}><option value="worldcover">ESA WorldCover</option><option value="esri">ESRI / Impact Observatory</option><option value="glc">GLC-FCS30D · project ten-class legend</option><option value="custom">Other categorical land cover</option></select>
              <p className="field-help">Single-band GeoTIFFs. WGS84, UTM, Web Mercator or EPSG:6933. Code 0 and declared NoData are excluded. Crop large tiles first.</p>
              {uploads.map((u, i) => <div className="upload-period" key={i}><input aria-label={`Year ${i + 1}`} type="number" min={1900} max={2100} value={u.year} onChange={e => setUploads(v => v.map((x, n) => n === i ? { ...x, year: Number(e.target.value) } : x))} /><FileUpload label={`GeoTIFF ${i + 1}`} accept=".tif,.tiff" fileName={u.file?.name ?? ""} onChange={file => setUploads(v => v.map((x, n) => n === i ? { ...x, file } : x))} /><button className="remove-button" aria-label={`Remove period ${i + 1}`} onClick={() => setUploads(v => v.filter((_, n) => n !== i))}>×</button></div>)}
              <div className="output-actions">{uploads.length < 3 && <button onClick={() => setUploads(v => [...v, { year: (v.at(-1)?.year ?? 2019) + 1 }])}>+ Add period</button>}<button onClick={inspect}>Load raster class codes</button></div>
              {studyAreaOverride ? <p className="field-help">Using the imported boundary: {studyAreaOverride.label}. Restore the Ganjam example or import a different result package to change the shared study area.</p> : <><label className="field-label" htmlFor="aoi-upload">AOI boundary (optional)</label><FileUpload id="aoi-upload" label="AOI boundary (optional)" accept=".geojson,.json,.zip" fileName={vectorNames.aoi ?? ""} onChange={file => loadVector("aoi", file)} /><p className="field-help">WGS84 GeoJSON or one zipped Shapefile with .shp, .dbf and .prj. Defaults to the earliest-year raster’s extent.</p>
              {vectors.aoi && <button className="text-button" onClick={() => { setVectors(v => ({ ...v, aoi: undefined })); setVectorNames(v => ({ ...v, aoi: "" })); }}>Clear {vectorNames.aoi}</button>}</>}
            </>}
            <label className="field-label" htmlFor="module">Diagnostic module</label><select id="module" value={module} onChange={e => setModule(e.target.value as RunRequest["module"])}><option value="both">LULC change + forest fragmentation</option><option value="lulc">LULC change only</option><option value="fragmentation">Forest fragmentation only</option></select>
            <div className="parameter-grid"><div><label className="field-label" htmlFor="resolution">Grid resolution (m)</label><input id="resolution" type="number" min={10} max={1000} step={10} value={cell} onChange={e => setCell(Number(e.target.value))} /></div>{module !== "lulc" && <div><label className="field-label" htmlFor="edge">Forest edge width (m)</label><input id="edge" type="number" min={cell} max={5000} value={edge} onChange={e => setEdge(Number(e.target.value))} /></div>}</div>
            <p className="field-help">Smaller cells retain more detail. Full Ganjam fits the browser at 50 m or coarser; the limit is 8 million analysis cells.</p>
            {module !== "lulc" && <><fieldset className="period-fieldset"><legend className="field-label">Classes counted as forest</legend><div className="checkbox-list">{uniqueClasses.map(c => <label key={c.code}><input type="checkbox" checked={forest.includes(c.code)} onChange={e => setForest(e.target.checked ? [...forest, c.code] : forest.filter(v => v !== c.code))} /><i style={{ background: c.color }} />{c.name}</label>)}</div></fieldset><label className="check-setting"><input type="checkbox" checked={boundaryEdge} onChange={e => setBoundaryEdge(e.target.checked)} />Count AOI / NoData boundaries as edges</label><p className="field-help">Off by default, following the reference method. Protection boundaries never create forest edges.</p></>}
            <details className="setup-details"><summary>Reclassify land cover</summary><p className="field-help">GLC-FCS30D source classes use the project ten-class crosswalk. To merge classes, use the same target code, name and colour for each source.</p>
              <label className="field-label" htmlFor="crosswalk">Import crosswalk CSV</label><FileUpload id="crosswalk" label="Import crosswalk CSV" accept=".csv" onChange={async f => { if (f) try { setRows(parseCrosswalk(await f.text())); } catch (err) { setError(message(err)); } }} />
              <div className="table-scroll crosswalk-table"><table><thead><tr><th>Source</th><th>Target</th><th>Name</th><th>Colour</th></tr></thead><tbody>{rows.map((r, i) => <tr key={i}><td>{r.source}</td><td><input aria-label={`Target code for source ${r.source}`} type="number" min={1} max={999} value={r.code} onChange={e => setRows(v => v.map((x, n) => n === i ? { ...x, code: Number(e.target.value) } : x))} /></td><td><input aria-label={`Target name for source ${r.source}`} value={r.name} onChange={e => setRows(v => v.map((x, n) => n === i ? { ...x, name: e.target.value } : x))} /></td><td><input aria-label={`Colour for source ${r.source}`} type="color" value={r.color} onChange={e => setRows(v => v.map((x, n) => n === i ? { ...x, color: e.target.value } : x))} /></td></tr>)}</tbody></table></div>
              <button className="quiet-button" onClick={() => download("crosswalk.csv", csv([["source_code", "target_code", "target_name", "color"], ...rows.map(r => [r.source, r.code, r.name, r.color])]), "text/csv")}>Export crosswalk CSV ↓</button>
            </details>
            {module !== "lulc" && <details className="setup-details"><summary>Protection & OECM layers</summary><p className="field-help">Optional WGS84 polygon GeoJSON or zipped Shapefiles. Use a complete dataset for the study area. Protected polygons take precedence where layers overlap.</p>{(["protectedAreas", "oecm"] as const).map(key => <div key={key}><label className="field-label" htmlFor={key}>{key === "oecm" ? "OECM polygons" : "Protected-area polygons"}</label><FileUpload id={key} label={key === "oecm" ? "OECM polygons" : "Protected-area polygons"} accept=".geojson,.json,.zip" fileName={vectorNames[key] ?? ""} onChange={file => loadVector(key, file)} />{vectors[key] && <button className="text-button" onClick={() => { setVectors(v => ({ ...v, [key]: undefined })); setVectorNames(v => ({ ...v, [key]: "" })); }}>Clear {vectorNames[key]}</button>}</div>)}</details>}
          </fieldset>
          <button className="run-button" disabled={running || inspecting || (dataset === "demo" && (!aoi || !metadata))} onClick={run}><span>{running ? "Computing analysis…" : result ? "Run analysis again" : "Run analysis"}</span><span aria-hidden="true">→</span></button>
          {running && <button className="quiet-button cancel-button" onClick={() => { runToken.current++; worker.current?.terminate(); worker.current = null; setRunning(false); setStatus("Analysis cancelled. Change settings or run again."); }}>Cancel analysis</button>}
          <p className="run-status" role="status" aria-live="polite">{inspecting ? "Reading uploaded data…" : status}</p>
          {(error || (dataset === "demo" && loadError)) && <p className="error-box" role="alert">{error || loadError}</p>}
          <p className="privacy-note">Files are processed in your browser. Uploaded data stays on your device.</p>
        </aside>
        <div className="results-column">
          <div className="results-slot">
            {result ? <Results key={String(result.manifest.computed_at)} result={result} selectedView={selectedView} /> :
              <section className="card welcome-card"><p className="step-number">YOUR ANALYSIS WORKSPACE</p><h2>{running ? "Calculating from the selected rasters…" : "A complete workflow, ready to run."}</h2><p>One run produces comparable land-cover maps, transition tables and forest structure metrics. Change the forest definition or edge width to explore how the results respond.</p><div className="feature-strip"><span>01<br /><strong>Land-cover comparison</strong><small>Maps, matrix, gains & losses</small></span><span>02<br /><strong>Forest fragmentation</strong><small>Core, edge, patch & clearings</small></span><span>03<br /><strong>Reproducible outputs</strong><small>GeoTIFF, PNG, CSV & JSON</small></span></div>{running && <div className="computing-indicator"><i />{status}</div>}</section>}
          </div>
          {dataset === "demo" && metadata && <section className="card result-section"><h2>Inspect the example inputs</h2><p className="section-copy">Download the same cropped rasters used by this page to test the upload workflow or compare results in another GIS tool.</p><div className="output-actions">{metadata.inputs.map(s => <a key={s.year} href={`${BASE}data/glcfcs/${s.file}`} download>{s.year} GeoTIFF ↓</a>)}<a href={`${BASE}data/glcfcs/python-reference.json`} download>Python reference results ↓</a><a href={`${BASE}data/ganjam-aoi.geojson`} download>AOI GeoJSON ↓</a></div></section>}

        </div>
      </div>
  </div>;
}
