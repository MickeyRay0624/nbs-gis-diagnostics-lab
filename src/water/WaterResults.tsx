import { useEffect, useMemo, useState } from "react";
import { MapPanel } from "../MapPanel";
import { TimeSeries, number } from "../step2/NumericResults";
import { rasterImage, palettes, domain } from "../step2/render";
import { download } from "../analysis/presets";
import type { LayerResult } from "../step2/model";
import { readWaterLayer, type WaterResult, type WaterClient } from "./client";

export function WaterResults({ result, jobId, client, embedded=false }: { result: WaterResult; jobId: string; client: WaterClient; embedded?:boolean }) {
  const [period, setPeriod] = useState("whole"), [variable, setVariable] = useState("et_24_mm");
  const [layer, setLayer] = useState<LayerResult | null>(null), [error, setError] = useState<string | null>(null), [busy, setBusy] = useState(false);
  const [raster, setRaster] = useState<{ file: string; bytes: ArrayBuffer } | null>(null);
  const spec = result.layers.find(l => l.period === period && l.variable === variable);
  const asset = result.assets.find(a => a.file === spec?.file);
  const [opacity, setOpacity] = useState(.8);
  useEffect(() => {
    const controller = new AbortController();
    setRaster(null); setError(null);
    // Variables share a multiband period file. Changing a variable should not
    // abort and download that same file again.
    if (asset) client.asset(jobId, asset, controller.signal).then(bytes => {
      if (!controller.signal.aborted) setRaster({ file: asset.file, bytes });
    }).catch(e => { if (!controller.signal.aborted) setError(e.message); });
    return () => controller.abort();
  }, [client, jobId, asset]);
  useEffect(() => {
    let active = true;
    setLayer(null);
    if (spec && raster?.file === spec.file) {
      setError(null);
      readWaterLayer(raster.bytes, result, spec).then(l => { if (active) setLayer(l); }).catch(e => { if (active) setError(e.message); });
    }
    return () => { active = false; };
  }, [raster, result, spec]);
  const rendered = useMemo(() => layer ? rasterImage(layer, result.boundary) : null, [layer, result.boundary]);
  const series = result.series.find(s => s.id === variable);
  const limits = layer ? domain(layer) : null;
  const save = async (file: string) => {
    const asset = result.assets.find(a => a.file === file);
    if (!asset) return;
    setBusy(true); setError(null);
    try { download(file, await client.asset(jobId, asset), asset.media_type); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  };
  return <section className="water-results" aria-label="Online water results">
    {!embedded&&<div className="section-heading"><div><p className="step-number">RESULTS READY · {result.model}</p><h2>{result.name}</h2><p className="section-copy">{result.validation.checks} data checks passed · {result.grid.width} × {result.grid.height} pixels · original model grid</p></div><span className="status-tag neutral">Technical screening</span></div>}
    <div className="water-fields"><label className="prep-field">Map variable<select value={variable} onChange={e => setVariable(e.target.value)}>{result.series.map(s => <option key={s.id} value={s.id}>{s.title}</option>)}</select></label>
      <label className="prep-field">Map period<select value={period} onChange={e => setPeriod(e.target.value)}>{result.periods.map(p => <option key={p.id} value={p.id}>{p.label} · {p.days} days</option>)}</select></label></div>
    {spec && <div className="water-metrics"><div><small>Area-weighted mean</small><strong>{number(spec.stats.mean)} <em>{spec.unit === "1" ? "(0–1)" : spec.unit}</em></strong></div><div><small>Valid area coverage</small><strong>{number(spec.stats.coveragePct, 1)}<em>%</em></strong></div><div><small>Period</small><strong className="water-period">{result.periods.find(p => p.id === period)?.start}<br />{result.periods.find(p => p.id === period)?.end}</strong></div></div>}
    {error && <p className="error-box" role="alert">{error}</p>}
    {!layer && !error && <p role="status">Loading the selected result map…</p>}
    <MapPanel aoi={result.boundary} label={result.name} loading={false} error={null} overlay={rendered?.overlay} opacity={opacity} showMarker={false} />
    <div className="overlay-slider"><label htmlFor="water-opacity">Map opacity</label><input id="water-opacity" type="range" min={0} max={1} step={.05} value={opacity} onChange={e => setOpacity(Number(e.target.value))} /></div>
    {layer && limits && <div className="water-legend"><span>{number(limits[0])}</span><i style={{ background: `linear-gradient(to right, ${palettes[layer.spec.palette].join(",")})` }} /><span>{number(limits[1])} {layer.spec.unit === "1" ? "" : layer.spec.unit}</span><small>Transparent = missing or outside the selected area</small></div>}
    {series && <TimeSeries {...series} unit={series.unit === "1" ? "Fraction (0–1)" : series.unit} />}
    <div className="output-actions">{asset && <button disabled={busy} onClick={() => void save(asset.file)}>Period GeoTIFF ↓</button>}<button disabled={busy} onClick={() => void save("daily-summary.csv")}>Daily CSV ↓</button><button disabled={busy} onClick={() => void save("period-summary.csv")}>Period CSV ↓</button><button disabled={busy} onClick={() => void save("results.zip")}>All results ↓</button><button disabled={busy} onClick={() => void save("run-manifest.json")}>Run details ↓</button></div>
    {busy && <p role="status">Downloading and checking the result file…</p>}
    <details className="water-methods"><summary>Methods, sources & interpretation</summary><p>{result.scope}</p><ul>{result.notes.map(n => <li key={n}>{n}</li>)}</ul>{result.source_url && <a href={result.source_url} target="_blank" rel="noreferrer">FAO public sample source ↗</a>}<p>Period totals show only pixels with a complete series of daily model values. Cloud-filtered and interpolated model inputs are documented in the run configuration.</p></details>
  </section>;
}
