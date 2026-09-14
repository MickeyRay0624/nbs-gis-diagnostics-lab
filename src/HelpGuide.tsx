import { guideContent as copy, metricDefinitions } from "./guideContent";

export function HelpGuide() {
  return <section id="user-guide" className="card help-guide">
    <details>
      <summary>Feature guide & calculation methods</summary>
      <h2>{copy.title}</h2><p className="guide-quickstart">{copy.lead}</p>
      <article className="guide-architecture"><h3>{copy.architectureTitle}</h3>
        <ol className="browser-flow">{copy.steps.map(step => <li key={step}>{step}</li>)}</ol>
        <p>{copy.architecture}</p><p>{copy.limits}</p>
      </article>
      <div className="guide-features">{copy.entries.map((entry, index) => <details key={index}>
        <summary>{String(index + 1).padStart(2, "0")} · {entry.title}</summary>
        <p><strong>{copy.how}: </strong>{entry.how}</p><p><strong>{copy.method}: </strong>{entry.method}</p>
      </details>)}</div>
      <details className="guide-metrics"><summary>{copy.metrics}</summary><div className="table-scroll"><table>
        <thead><tr><th>Field</th><th>Meaning</th><th>Formula / convention</th></tr></thead>
        <tbody>{metricDefinitions.map(row => <tr key={row[0]}><th>{row[0]}</th><td>{row[1]}</td><td>{row[2]}</td></tr>)}</tbody>
      </table></div></details>
      <div className="output-actions"><a href={`${import.meta.env.BASE_URL}guide.en.md`} download>Download full guide ↓</a><a href="https://github.com/MickeyRay0624/nbs-gis-diagnostics-lab/tree/main/src/analysis" target="_blank" rel="noreferrer">Calculation source code ↗</a></div>
    </details>
  </section>;
}
