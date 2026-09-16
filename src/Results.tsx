import { useEffect, useState } from "react";
import { FRAGMENT_CLASSES } from "./analysis/model";
import type { Result } from "./analysis/model";
import { csv, download } from "./analysis/presets";
import { RasterView } from "./RasterView";

const number = (n: number, digits = 1) => n.toLocaleString("en", { maximumFractionDigits: digits });
export function Results({ result, selectedView }: { result: Result; selectedView?: "lulc" | "fragmentation" }) {
  const hasForest = !!result.periods[0].fragmentation;
  const [tab, setTab] = useState<"lulc" | "forest" | "change">(result.transitions.length ? "lulc" : "forest");
  const [pair, setPair] = useState(0);
  useEffect(() => { if (selectedView) setTab(selectedView === "fragmentation" && hasForest ? "forest" : "lulc"); }, [selectedView, hasForest]);
  const ha = result.grid.cell ** 2 / 10000, t = result.transitions[pair];
  const latest = result.periods.at(-1)!, fm = latest.fragmentation?.metrics[0];
  const className = (code: number) => result.classes.find(c => c.code === code)?.name ?? String(code);
  const maxGain = t ? Math.max(1, ...t.gains.flatMap(g => [g.loss, g.gain])) : 1;
  const attribution = String(result.manifest.dataset).includes("WorldCover") ? "© ESA WorldCover 2020/2021 · modified Copernicus Sentinel data · Technical demonstration" : String(result.manifest.dataset).includes("GLC-FCS30D") ? "Zhang et al. (2024) · GLC-FCS30D · CC BY 4.0 · Technical screening" : "User-supplied categorical land cover · Technical analysis";
  const areaRows = [["year", "class_code", "class_name", "pixels", "area_ha"], ...result.periods.flatMap(p => result.classes.map(c => [p.year, c.code, c.name, p.counts[c.code] ?? 0, (p.counts[c.code] ?? 0) * ha]))];
  const fragRows = result.periods.flatMap(p => (p.fragmentation?.metrics ?? []).map(m => ({ year: p.year, ...m })));
  const exportMetrics = () => { if (fragRows.length) download("forest_fragmentation.csv", csv([Object.keys(fragRows[0]), ...fragRows.map(r => Object.values(r))]), "text/csv"); };
  return <div className="analysis-results">
    <div className="metric-row">
      <article><small>Mapped area · {latest.year}</small><strong>{number(latest.valid * ha / 100)} <i>km²</i></strong><span>{number(latest.valid, 0)} valid pixels</span></article>
      <article><small>{fm ? `Forest cover · ${latest.year}` : "Comparable area"}</small><strong>{fm ? `${number(fm.PLAND)}%` : `${number(t.valid * ha / 100)} km²`}</strong><span>{fm ? `${number(fm.forest_ha)} ha of selected forest classes` : "Common valid footprint for both periods"}</span></article>
      <article><small>{fm ? "Core share of forest" : "Class difference"}</small><strong>{number(fm ? fm.core_pct : t.changed / t.valid * 100)}<i> %</i></strong><span>{fm ? `${number(fm.NP, 0)} connected forest patches` : `${t.start}–${t.end} · mapped class change`}</span></article>
    </div>

    <section className="card result-section">
      <div className="section-heading"><div><p className="step-number">02 · MAP COMPARISON</p><h2>Read the landscape</h2></div><span className="status-tag ready">Calculated from rasters</span></div>
      <div className="tab-bar" role="tablist" aria-label="Map layers">
        <button role="tab" aria-selected={tab === "lulc"} onClick={() => setTab("lulc")}>Land cover</button>
        {hasForest && <button role="tab" aria-selected={tab === "forest"} onClick={() => setTab("forest")}>Forest fragmentation</button>}
        {!!result.transitions.length && <button role="tab" aria-selected={tab === "change"} onClick={() => setTab("change")}>Class difference</button>}
      </div>
      <div className="raster-grid">
        {tab === "change" ? result.transitions.map(p => <RasterView key={`${p.start}-${p.end}`} title={`Class difference ${p.start}–${p.end}`} data={p.data} grid={result.grid} nodata={255} attribution={attribution} classes={[{ code: 0, name: "Unchanged", color: "#e6e7db" }, { code: 1, name: "Different class", color: "#b65835" }]} />) : result.periods.map(p => <RasterView key={`${tab}-${p.year}`} title={`${tab === "forest" ? "Forest fragmentation" : "Land cover"} ${p.year}`} data={tab === "forest" ? p.fragmentation!.data : p.data} grid={result.grid} classes={tab === "forest" ? FRAGMENT_CLASSES : result.classes} nodata={tab === "forest" ? 255 : 0} attribution={attribution} />)}
      </div>
      <div className="legend">{(tab === "forest" ? FRAGMENT_CLASSES : tab === "change" ? [{ code: 0, name: "Unchanged", color: "#e6e7db" }, { code: 1, name: "Different class", color: "#b65835" }] : result.classes).map(c => <span key={c.code}><i style={{ background: c.color }} />{c.name}</span>)}</div>
      {tab === "forest" && <p className="field-help">Internal clearings are enclosed non-forest areas and are excluded from forest area. NoData is transparent.</p>}
    </section>

    {!!result.transitions.length && <section className="card result-section">
      <div className="section-heading"><div><p className="step-number">03 · LAND-COVER CHANGE</p><h2>Transitions, gains & losses</h2></div>
        <select aria-label="Comparison period" value={pair} onChange={e => setPair(Number(e.target.value))}>{result.transitions.map((p, i) => <option key={i} value={i}>{p.start} → {p.end}</option>)}</select></div>
      <p className="section-copy">{number(t.changed * ha)} ha ({number(t.changed / t.valid * 100)}%) have a different class within {number(t.valid * ha)} ha of common valid coverage. Rows are {t.start}; columns are {t.end}. Values are hectares.</p>
      <div className="table-scroll"><table className="matrix"><caption>Land-cover transition matrix · hectares</caption><thead><tr><th>From ↓ / To →</th>{t.codes.map(c => <th key={c} title={className(c)}>{className(c)}</th>)}</tr></thead><tbody>{t.matrix.map((row, i) => <tr key={i}><th>{className(t.codes[i])}</th>{row.map((v, j) => <td key={j} title={`${className(t.codes[i])} → ${className(t.codes[j])}: ${v} pixels`} style={{ background: `rgba(77, 133, 81, ${v ? .1 + .55 * Math.sqrt(v / t.valid) : 0})` }}>{number(v * ha)}</td>)}</tr>)}</tbody></table></div>
      <div className="gains-chart" role="img" aria-label={`Gross losses and gains in hectares, ${t.start} to ${t.end}`}>
        <div className="gain-row gain-heading"><span>Land-cover class</span><span>← Gross loss (ha)</span><span>Gross gain (ha) →</span><span>Net (ha)</span></div>
        {t.gains.map(g => <div className="gain-row" key={g.code}><strong>{className(g.code)}</strong><div className="loss-cell"><i style={{ width: `${g.loss / maxGain * 100}%` }} /><span>−{number(g.loss * ha)}</span></div><div className="gain-cell"><i style={{ width: `${g.gain / maxGain * 100}%` }} /><span>+{number(g.gain * ha)}</span></div><b>{g.net > 0 ? "+" : ""}{number(g.net * ha)}</b></div>)}
      </div>
      <div className="output-actions">
        <button onClick={() => download(`transition_${t.start}_${t.end}.csv`, csv([["from / to (ha)", ...t.codes.map(className)], ...t.matrix.map((row, i) => [className(t.codes[i]), ...row.map(v => v * ha)])]), "text/csv")}>Transition matrix CSV ↓</button>
        <button onClick={() => download(`gain_loss_${t.start}_${t.end}.csv`, csv([["class_code", "class_name", "gain_ha", "loss_ha", "net_ha"], ...t.gains.map(g => [g.code, className(g.code), g.gain * ha, g.loss * ha, g.net * ha])]), "text/csv")}>Gain / loss CSV ↓</button>
      </div>
    </section>}

    {hasForest && <section className="card result-section"><div className="section-heading"><div><p className="step-number">04 · FOREST STRUCTURE</p><h2>Fragmentation by year & protection</h2></div><button className="quiet-button" onClick={exportMetrics}>Metrics CSV ↓</button></div>
      <p className="section-copy">{result.periods[0].fragmentation!.qa.protection_available ? "Protected, OECM and the remainder of supplied coverage are calculated after whole-landscape classification. Protected areas take precedence over OECM." : "No protection layer supplied. Showing whole-landscape results; upload protection polygons to enable strata."}</p>
      <div className="forest-bars">{fragRows.filter(r => r.stratum === "All").map(r => <div key={r.year}><strong>{r.year}</strong><div className="stacked-bar" aria-label={`Forest composition ${r.year}`}>
        {[{ v: r.core_ha, label: "Core", color: "#286845" }, { v: r.edge_ha, label: "Edge", color: "#e6ab36" }, { v: r.patch_ha, label: "Patch", color: "#d64233" }].map(x => <span key={x.label} style={{ width: `${r.forest_ha ? x.v / r.forest_ha * 100 : 0}%`, background: x.color }} title={`${x.label}: ${number(x.v)} ha`} />)}
      </div><small>{number(r.forest_ha)} ha forest</small></div>)}</div>
      <div className="table-scroll"><table><caption>Forest metrics · whole patches assigned by majority area</caption><thead><tr>{["Year", "Stratum", "Forest (ha)", "Core (ha)", "Edge (ha)", "Patch (ha)", "Clearings (ha)", "Patches (NP)", "Edge density (m/ha)", "Mean patch (ha)", "Shape (MSI)", "AWMSI", "LPI (%)"].map(s => <th key={s}>{s}</th>)}</tr></thead><tbody>{fragRows.map(r => <tr key={`${r.year}-${r.stratum}`}>{[r.year, r.stratum, number(r.forest_ha), number(r.core_ha), number(r.edge_ha), number(r.patch_ha), number(r.clearing_ha), number(r.NP, 0), number(r.ED, 2), number(r.MPS_ha, 2), number(r.MSI, 3), number(r.AWMSI, 3), number(r.LPI, 2)].map((v, i) => <td key={i}>{v}</td>)}</tr>)}</tbody></table></div>
      <p className="field-help">NP and mean patch size use whole patches assigned by majority area. Area and edge length use pixel allocation. LPI uses each patch’s actual area within the stratum. Full definitions are in the run manifest.</p>
    </section>}

    <section className="card result-section"><div className="section-heading"><div><p className="step-number">05 · REPRODUCIBILITY</p><h2>Take the evidence with you</h2></div><span className="status-tag ready">Area conservation passed</span></div>
      <p className="section-copy">The manifest records input hashes, class rules, grid, forest parameters, coverage checks and limitations for this exact run.</p>
      <div className="output-actions"><button onClick={() => download("nbs_run_manifest.json", JSON.stringify(result.manifest, null, 2))}>Run manifest JSON ↓</button><button onClick={() => download("class_area_by_year.csv", csv(areaRows), "text/csv")}>Class areas CSV ↓</button></div>
      <details><summary>Method, coverage & limitations</summary><ul>{(result.manifest.limitations as string[]).map(s => <li key={s}>{s}</li>)}</ul><pre>{JSON.stringify(result.manifest.qa, null, 2)}</pre></details>
    </section>
  </div>;
}
