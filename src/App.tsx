import { useEffect, useMemo, useRef, useState } from "react";
import {
  REQUIRED_DATASETS,
  runAoiPreflight,
} from "./diagnostics";
import type { AoiPreflightResult } from "./diagnostics";
import { geometryAreaSqKm, geometryVertexCount } from "./geo";
import { MapPanel } from "./MapPanel";
import type { AoiFeatureCollection } from "./types";

const YEARS = [2002, 2012, 2022];
const PIPELINE = [
  { label: "Load boundary", detail: "Read source GeoJSON" },
  { label: "Validate geometry", detail: "Type, domain and ring closure" },
  { label: "Derive metrics", detail: "Area, vertices and bounds" },
  { label: "Apply data gate", detail: "Check required raster inputs" },
  { label: "Package report", detail: "Manifest and QA output" },
];
const CHECKPOINTS = [
  { progress: 18, stage: 0, message: "Reading the Ganjam boundary…" },
  { progress: 41, stage: 1, message: "Validating polygon geometry…" },
  { progress: 64, stage: 2, message: "Calculating AOI metrics…" },
  { progress: 84, stage: 3, message: "Checking analysis input readiness…" },
  { progress: 100, stage: 4, message: "AOI pre-flight report ready" },
] as const;

type RunState = "idle" | "running" | "complete";

function downloadJson(filename: string, value: unknown) {
  const blob = new Blob([JSON.stringify(value, null, 2)], {
    type: "application/geo+json;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export default function App() {
  const [aoi, setAoi] = useState<AoiFeatureCollection | null>(null);
  const [aoiError, setAoiError] = useState<string | null>(null);
  const [runState, setRunState] = useState<RunState>("idle");
  const [progress, setProgress] = useState(0);
  const [activeStage, setActiveStage] = useState(-1);
  const [runMessage, setRunMessage] = useState("Waiting to start AOI pre-flight");
  const [result, setResult] = useState<AoiPreflightResult | null>(null);
  const timers = useRef<number[]>([]);

  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}data/ganjam-aoi.geojson`)
      .then((response) => {
        if (!response.ok) throw new Error("AOI request failed");
        return response.json() as Promise<AoiFeatureCollection>;
      })
      .then(setAoi)
      .catch(() => setAoiError("The AOI boundary could not be loaded"));
  }, []);

  useEffect(() => {
    const pending = timers.current;
    return () => pending.forEach((timer) => window.clearTimeout(timer));
  }, []);

  const aoiMetrics = useMemo(() => {
    const feature = aoi?.features[0];
    if (!feature) return null;
    return {
      area: geometryAreaSqKm(feature.geometry),
      vertices: geometryVertexCount(feature.geometry),
    };
  }, [aoi]);

  const startPreflight = () => {
    if (!aoi) return;
    timers.current.forEach((timer) => window.clearTimeout(timer));
    timers.current = [];
    setRunState("running");
    setProgress(5);
    setActiveStage(0);
    setRunMessage("Initialising AOI validation…");
    setResult(null);

    CHECKPOINTS.forEach((checkpoint, index) => {
      const timer = window.setTimeout(
        () => {
          setProgress(checkpoint.progress);
          setActiveStage(checkpoint.stage);
          setRunMessage(checkpoint.message);
          if (index === CHECKPOINTS.length - 1) {
            setResult(runAoiPreflight(aoi));
            setRunState("complete");
          }
        },
        420 + index * 520,
      );
      timers.current.push(timer);
    });
  };

  const qaPassed = result?.qa.filter((check) => check.status === "pass").length ?? 0;

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">N</span>
          <div>
            <p className="eyebrow">Nature-based Solutions · Geospatial Diagnostics</p>
            <p className="brand-title">NbS Diagnostics Lab</p>
          </div>
        </div>
        <div className="topbar-actions">
          <span className="live-pill"><span /> Live AOI</span>
          <span className="version-label">Prototype 0.2</span>
        </div>
      </header>

      <main className="workspace">
        <section className="hero-panel">
          <div>
            <p className="eyebrow accent">India pilot · AOI pre-flight</p>
            <h1>A real study-area boundary, ready for reproducible diagnostics.</h1>
            <p className="hero-copy">
              This prototype uses the verified Ganjam District boundary on an interactive OpenStreetMap basemap. It validates the study area before any raster analysis is allowed to run.
            </p>
          </div>
          <div className="architecture-chip" aria-label="Platform architecture">
            <span><small>Compute</small>GIS engine</span>
            <b aria-hidden="true">→</b>
            <span><small>Review</small>Web workspace</span>
          </div>
        </section>

        <section className="primary-grid">
          <aside className="control-panel card">
            <div className="section-heading">
              <div><p className="step-number">01 · RUN SETUP</p><h2>Configure diagnostic</h2></div>
              <span className="status-tag neutral">AOI mode</span>
            </div>

            <label className="field-label" htmlFor="study-area">Study area</label>
            <select id="study-area" value="ganjam" disabled>
              <option value="ganjam">Ganjam District, Odisha, India</option>
            </select>
            <p className="field-help">ADM2 boundary · represented year 2021</p>

            <label className="field-label" htmlFor="module">Diagnostic module</label>
            <select id="module" value="lulc" disabled>
              <option value="lulc">Land-use / land-cover change</option>
            </select>

            <fieldset className="period-fieldset">
              <legend className="field-label">Analysis periods</legend>
              <div className="year-checks">
                {YEARS.map((year) => <span key={year}>{year}</span>)}
              </div>
            </fieldset>

            <div className="source-contract">
              <span className="source-icon" aria-hidden="true">AOI</span>
              <div><strong>Verified boundary connected</strong><small>CRS84 GeoJSON · ODbL 1.0</small></div>
              <span className="status-tag ready">Ready</span>
            </div>

            <button
              className="run-button"
              type="button"
              onClick={startPreflight}
              disabled={!aoi || runState === "running"}
            >
              <span>{runState === "running" ? "Running AOI pre-flight" : runState === "complete" ? "Run AOI pre-flight again" : "Run AOI pre-flight"}</span>
              <span aria-hidden="true">{runState === "running" ? "···" : "→"}</span>
            </button>
            <p className="safety-note"><span aria-hidden="true">!</span>No LULC raster is connected yet. The map is real; change results remain locked.</p>
          </aside>

          <section className="map-panel card" aria-labelledby="map-heading">
            <div className="section-heading map-heading">
              <div><p className="step-number">02 · STUDY AREA</p><h2 id="map-heading">Ganjam District AOI</h2></div>
              <div className="map-meta"><span>Boundary 2021</span><span>CRS84</span></div>
            </div>
            <MapPanel aoi={aoi} loading={!aoi && !aoiError} error={aoiError} />
          </section>

          <aside className="readiness-panel card">
            <div className="section-heading">
              <div><p className="step-number">03 · DATA GATE</p><h2>Readiness</h2></div>
              <span className="readiness-score">1 / 7</span>
            </div>

            <div className="aoi-stat">
              <small>Boundary-derived area</small>
              <strong>{aoiMetrics ? aoiMetrics.area.toLocaleString(undefined, { maximumFractionDigits: 0 }) : "—"}</strong>
              <span>km² · approximate</span>
            </div>
            <div className="aoi-stat secondary">
              <small>Boundary vertices</small>
              <strong>{aoiMetrics ? aoiMetrics.vertices.toLocaleString() : "—"}</strong>
              <span>simplified geometry</span>
            </div>

            <ul className="readiness-list">
              <li className="complete"><span>✓</span><div><strong>AOI boundary</strong><small>Connected and visible</small></div></li>
              <li><span>!</span><div><strong>LULC rasters</strong><small>0 of 3 connected</small></div></li>
              <li><span>!</span><div><strong>Class crosswalk</strong><small>Not provided</small></div></li>
              <li><span>!</span><div><strong>Reference outputs</strong><small>Not provided</small></div></li>
            </ul>

            <div className="source-note">
              <span>Boundary provenance</span>
              <strong>geoBoundaries gbOpen</strong>
              <small>India ADM2 · ODbL 1.0</small>
            </div>
          </aside>
        </section>

        <section className="lower-grid">
          <section className="workflow-panel card" aria-live="polite">
            <div className="section-heading">
              <div><p className="step-number">04 · AUTOMATION</p><h2>AOI pre-flight report</h2></div>
              <span className={`status-tag ${runState}`}>{runState}</span>
            </div>

            <div className="progress-wrap">
              <div className="progress-copy"><span>{runMessage}</span><strong>{progress}%</strong></div>
              <div className="progress-track" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress}><span style={{ width: `${progress}%` }} /></div>
            </div>

            <ol className="pipeline-list">
              {PIPELINE.map((stage, index) => {
                const isDone = runState === "complete" || activeStage > index;
                const isActive = runState === "running" && activeStage === index;
                return (
                  <li className={isDone ? "done" : isActive ? "active" : ""} key={stage.label}>
                    <span className="pipeline-marker">{isDone ? "✓" : index + 1}</span>
                    <div><strong>{stage.label}</strong><small>{stage.detail}</small></div>
                  </li>
                );
              })}
            </ol>

            {!result ? (
              <div className="empty-report">
                <span aria-hidden="true">↗</span>
                <div><strong>No report generated yet</strong><p>Run the pre-flight to validate the real AOI geometry and package a machine-readable manifest.</p></div>
              </div>
            ) : (
              <div className="report-content">
                <div className="metric-row">
                  <article><small>AOI area</small><strong>{result.areaSqKm.toLocaleString(undefined, { maximumFractionDigits: 0 })}</strong><span>km² · boundary-derived</span></article>
                  <article><small>Geometry</small><strong>{result.vertexCount.toLocaleString()}</strong><span>vertices validated</span></article>
                  <article><small>Automated QA</small><strong>{qaPassed}<i> / {result.qa.length}</i></strong><span>checks passed</span></article>
                </div>

                <div className="qa-table">
                  <div className="qa-table-head"><span>Check</span><span>Result</span><span>Status</span></div>
                  {result.qa.map((check) => (
                    <div className="qa-table-row" key={check.id}>
                      <strong>{check.label}</strong><span>{check.detail}</span><em className={check.status}>{check.status}</em>
                    </div>
                  ))}
                </div>

                <div className="output-actions">
                  <button type="button" onClick={() => downloadJson("ganjam-district-aoi-2021.geojson", aoi)}>Download AOI <span>GeoJSON</span></button>
                  <button type="button" onClick={() => downloadJson(`${result.runId}-manifest.json`, result.manifest)}>Download report <span>JSON</span></button>
                  <a href="https://www.geoboundaries.org/api/current/gbOpen/IND/ADM2/" target="_blank" rel="noreferrer">Open boundary source <span>External</span></a>
                </div>
              </div>
            )}
          </section>

          <aside className="requirements-panel card">
            <div className="section-heading">
              <div><p className="step-number">REAL ANALYSIS GATE</p><h2>Inputs still required</h2></div>
              <span className="missing-count">{REQUIRED_DATASETS.length}</span>
            </div>
            <p className="requirements-intro">The AOI is real and ready. Land-cover change remains blocked until these inputs are connected.</p>
            <ul className="requirements-list">
              {REQUIRED_DATASETS.map((item) => (
                <li key={item.id}><span aria-hidden="true">!</span><div><strong>{item.name}</strong><small>{item.format}</small><p>{item.purpose}</p></div></li>
              ))}
            </ul>
          </aside>
        </section>

        <section className="gate-strip card">
          <div><p className="eyebrow accent">Evidence gate</p><h2>Real AOI validated. Raster analysis remains intentionally locked.</h2></div>
          <div className="gate-flow"><span className="passed">AOI pre-flight</span><b>→</b><span>Raster ingestion</span><b>→</b><span className="locked">Scientific review</span></div>
        </section>
      </main>

      <footer>
        <span>NbS GIS Diagnostics Lab · Ganjam AOI prototype</span>
        <span>Boundary: geoBoundaries gbOpen · Basemap: OpenStreetMap</span>
      </footer>
    </div>
  );
}
