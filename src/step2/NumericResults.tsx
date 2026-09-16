import { useEffect, useMemo, useState } from "react";
import { csv, download } from "../analysis/presets";
import type { VectorCollection } from "../analysis/model";
import type { Catalog, MapOverlay, ModuleResult, SeriesPoint } from "./model";
import { numericGeoTiff } from "./io";
import { domain, mapPng, palettes, rasterImage } from "./render";

export const number = (n: number | null, digits = 2) => n === null ? "No data" : n.toLocaleString("en", { maximumFractionDigits: digits });

function TimeSeries({ title, unit, points }: { title: string; unit: string; points: SeriesPoint[] }) {
  const finite = points.flatMap(p => p.value === null ? [] : [p.value]);
  if (!finite.length) return <p>{title}: no valid observations.</p>;
  const low = Math.min(...finite), high = Math.max(...finite), range = high - low || 1;
  const dates = points.map(p => Date.parse(p.date.length === 4 ? `${p.date}-01-01` : p.date.length === 7 ? `${p.date}-01` : p.date));
  const timed = dates.every(Number.isFinite) && dates.at(-1)! > dates[0];
  let path = "", previous = false;
  points.forEach((p, i) => { if (p.value === null) { previous = false; return; } path += `${previous ? "L" : "M"}${65 + (timed ? (dates[i]-dates[0]) / (dates.at(-1)!-dates[0]) : i / Math.max(points.length - 1, 1)) * 685},${175 - (p.value - low) / range * 135} `; previous = true; });
  return <article className="series-card"><h3>{title}</h3><svg viewBox="0 0 780 210" role="img" aria-label={`${title}, ${points[0].date} to ${points.at(-1)!.date}. Values in ${unit}; gaps are missing observations.`}>
    {[0, .5, 1].map(t => <g key={t}><line x1="65" x2="750" y1={175 - 135 * t} y2={175 - 135 * t} stroke="#d8e0da" /><text x="5" y={180 - 135 * t}>{number(low + range * t, 1)}</text></g>)}
    <path d={path} fill="none" stroke="#216756" strokeWidth="2.2" /><text x="65" y="202">{points[0].date}</text><text x="750" y="202" textAnchor="end">{points.at(-1)!.date}</text><text x="65" y="20">{unit}</text>
  </svg><details><summary>View observations</summary><div className="table-scroll"><table><thead><tr><th>Period</th><th>{unit}</th><th>Coverage (%)</th></tr></thead><tbody>{points.map(p => <tr key={p.date}><th>{p.date}</th><td>{number(p.value)}</td><td>{p.coveragePct === undefined ? "Not reported" : number(p.coveragePct)}</td></tr>)}</tbody></table></div></details>
    <button className="quiet-button" onClick={() => download(`${title.replace(/[^a-z0-9]+/gi, "-")}.csv`, csv([["period", unit, "coverage_percent"], ...points.map(p => [p.date, p.value ?? "", p.coveragePct ?? ""])]), "text/csv")}>Time series CSV ↓</button>
  </article>;
}

export function NumericResults({ result, catalog, aoi, onOverlay }: { result: ModuleResult; catalog: Catalog; aoi: VectorCollection | null; onOverlay: (value: MapOverlay | null) => void }) {
  const [index, setIndex] = useState(0), [seriesIndex, setSeriesIndex] = useState(0), [exportError, setExportError] = useState<string | null>(null);
  const layer = result.layers[Math.min(index, result.layers.length - 1)];
  const rendered = useMemo(() => rasterImage(layer, aoi), [layer, aoi]);
  useEffect(() => { onOverlay(rendered.overlay); return () => onOverlay(null); }, [rendered, onOverlay]);
  const sources = catalog.sources.filter(s => result.module.sources.includes(s.id));
  const asset = catalog.rasters.find(r => r.id === layer.spec.inputs[0].raster)!;
  const stats = layer.stats, limits = domain(layer);
  const exportTable = () => download(`${result.module.id}-statistics.csv`, csv([
    ["layer", "period", "unit", "mean", "min", "max", "valid_area_km2", "eligible_area_km2", "missing_area_km2", "coverage_percent", "native_resolution"],
    ...result.layers.map(l => [l.spec.title, l.spec.period, l.spec.unit, l.stats.mean ?? "", l.stats.min ?? "", l.stats.max ?? "", l.stats.validAreaKm2, l.stats.eligibleAreaKm2, l.stats.missingAreaKm2, l.stats.coveragePct, catalog.rasters.find(r => r.id === l.spec.inputs[0].raster)!.nativeResolution])]), "text/csv");
  return <div className="numeric-results">
    <div className="metric-row">
      <article><small>{layer.spec.categories ? "Classified area" : "Area-weighted mean"}</small><strong>{layer.spec.categories ? number(stats.validAreaKm2) : number(stats.mean)} <i>{layer.spec.categories ? "km²" : layer.spec.unit}</i></strong><span>{layer.spec.categories ? "Review the class distribution below" : "On valid, eligible cells"}</span></article>
      <article><small>Valid coverage</small><strong>{number(stats.coveragePct, 1)}<i> %</i></strong><span>{number(stats.validAreaKm2)} of {number(stats.eligibleAreaKm2)} km² eligible area</span></article>
      <article><small>Source resolution</small><strong className="resolution-value">{asset.nativeResolution}</strong><span>{number(stats.missingAreaKm2)} km² missing / excluded</span></article>
    </div>
    <section className="card result-section">
      <div className="section-heading"><div><p className="step-number">MAP & EVIDENCE</p><h2>{result.module.title}</h2></div><span className="status-tag ready">Calculated · review pending</span></div>
      <label className="field-label" htmlFor="numeric-layer">Map layer</label><select id="numeric-layer" value={index} onChange={e => setIndex(Number(e.target.value))}>{result.layers.map((l, i) => <option key={l.spec.id} value={i}>{l.spec.title}</option>)}</select>
      <p className="section-copy">{layer.spec.period} · {layer.spec.unit}</p>
      <div className="numeric-map"><img src={rendered.overlay.url} alt={`${layer.spec.title} across Ganjam. The same layer is shown on the overview map.`} />
        <div className="numeric-legend">{layer.spec.categories ? layer.spec.categories.map(c => <span key={c.value}><i style={{ background: c.color }} />{c.label}</span>) : <><div className="gradient-legend" style={{ background: `linear-gradient(90deg, ${palettes[layer.spec.palette].join(",")})` }} /><div className="legend-endpoints"><span>{number(limits[0])}</span><span>{number(limits[1])} {layer.spec.unit}</span></div></>}<small>Transparent = missing / excluded. Map colours do not add spatial precision.</small></div>
      </div>
      <p className="interpretation">{layer.spec.interpretation}</p>
      {!!stats.classes.length && <div className="table-scroll"><table><caption>Distribution on the valid footprint</caption><thead><tr><th>Class / threshold</th><th>Area (km²)</th><th>Valid area (%)</th></tr></thead><tbody>{stats.classes.map(c => <tr key={c.label}><th>{c.label}</th><td>{number(c.areaKm2)}</td><td>{number(c.percent)}</td></tr>)}</tbody></table></div>}
      <div className="output-actions"><button onClick={() => download(`${layer.spec.id}.tif`, numericGeoTiff(layer), "image/tiff")}>Layer GeoTIFF ↓</button><button onClick={async () => { try { download(`${layer.spec.id}.png`, await mapPng(layer, rendered.canvas, sources.map(s => `${s.name} ${s.version}`).join(" · ")), "image/png"); } catch (e) { setExportError(String(e)); } }}>Map PNG ↓</button><button onClick={exportTable}>Statistics CSV ↓</button><button onClick={() => download(`${result.module.id}-manifest.json`, JSON.stringify(result.manifest, null, 2))}>Run manifest ↓</button>
        {!!stats.classes.length && <button onClick={() => download(`${layer.spec.id}-classes.csv`, csv([["class", "area_km2", "valid_area_percent"], ...stats.classes.map(c => [c.label, c.areaKm2, c.percent ?? ""])]), "text/csv")}>Class areas CSV ↓</button>}</div>
      {exportError && <p className="error-box" role="alert">{exportError}</p>}
    </section>
    {!!result.module.series?.length && <section className="card result-section"><h2>Time series</h2><p className="section-copy">Prepared from the source observations. Missing observations remain gaps.</p><label className="field-label" htmlFor="series-choice">Time series</label><select id="series-choice" value={seriesIndex} onChange={e=>setSeriesIndex(Number(e.target.value))}>{result.module.series.map((s,i)=><option key={s.title} value={i}>{s.title}</option>)}</select><TimeSeries {...result.module.series[seriesIndex]} /></section>}
    <section className="card result-section"><h2>Compare all outputs</h2><div className="table-scroll"><table><thead><tr><th>Layer</th><th>Unit</th><th>Mean</th><th>Valid area (km²)</th><th>Coverage (%)</th></tr></thead><tbody>{result.layers.map(l => <tr key={l.spec.id}><th>{l.spec.title}</th><td>{l.spec.unit}</td><td>{l.spec.categories ? "—" : number(l.stats.mean)}</td><td>{number(l.stats.validAreaKm2)}</td><td>{number(l.stats.coveragePct, 1)}</td></tr>)}</tbody></table></div></section>
  </div>;
}
