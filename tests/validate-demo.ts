import assert from "node:assert/strict";
import { readFile, writeFile } from "node:fs/promises";
import { runAnalysis } from "../src/analysis/runner";
import { WORLDCOVER, GLCFCS } from "../src/analysis/presets";
import { sha256 } from "../src/analysis/io";

const root = new URL("../public/data/", import.meta.url);
const read = async (path: string) => JSON.parse(await readFile(new URL(path, root), "utf8"));
const dataset = process.argv.includes("--glcfcs") ? "glcfcs" : "worldcover";
const metadata = await read(`${dataset}/metadata.json`), reference = await read(`${dataset}/python-reference.json`);
const sources = await Promise.all(metadata.inputs.map(async (s: {year: number; file: string; sha256: string}) => {
  const buffer = await readFile(new URL(`${dataset}/${s.file}`, root));
  return { year: s.year, name: s.file, expectedSha256: s.sha256, buffer: buffer.buffer.slice(buffer.byteOffset, buffer.byteOffset + buffer.byteLength) as ArrayBuffer };
}));
const started = performance.now();
const result = await runAnalysis({ sources, crosswalk: dataset === "glcfcs" ? GLCFCS : WORLDCOVER, forestCodes: dataset === "glcfcs" ? [2] : [10, 95], edge: 50, cell: 50, countBoundary: false,
  module: "both", dataset: metadata.name, aoi: await read("ganjam-aoi.geojson"), provenance: metadata }, console.log);
assert.deepEqual(result.grid, reference.grid);
assert.equal(result.transitions.length,reference.transitions.length,"All configured comparison periods must be validated");
let checked = 0;
for (const row of reference.class_area_by_year) {
  const period = result.periods.find(p => p.year === row.year)!;
  assert.equal(period.counts[row.class_code] ?? 0, row.pixel_count, `class ${row.class_code} in ${row.year}`); checked++;
}
for (const [i, t] of result.transitions.entries()) {
  assert.equal(t.valid, reference.transitions[i].valid_pixel_count);
  assert.equal(t.changed, reference.transitions[i].changed_pixel_count);
  for (const gain of t.gains) {
    const ref = reference.transitions[i].gain_loss.find((r: { class_code: number }) => r.class_code === gain.code);
    for (const key of ["gain", "loss", "net"] as const) assert.ok(Math.abs(gain[key] * .25 - ref[`${key}_ha`]) < 1e-6);
    checked += 3;
  }
}
for (const period of result.periods) {
  for (const m of period.fragmentation!.metrics) {
    const ref = reference.fragmentation.find((r: { year: number; stratum: string }) => r.year === period.year && r.stratum === m.stratum);
    for (const [key, value] of Object.entries(m)) {
      if (typeof value === "number") { assert.ok(Math.abs(value - ref[key]) < 1e-6, `${period.year} ${key}: JS ${value} vs Python ${ref[key]}`); checked++; }
    }
  }
  assert.equal(await sha256(period.fragmentation!.data.buffer as ArrayBuffer), reference.fragmentation_pixel_sha256[String(period.year)], `every fragmentation pixel for ${period.year}`);
}
const report = { status: "pass", checked_numeric_values: checked, fragmentation_pixels_compared: result.grid.width * result.grid.height * result.periods.length,
  elapsed_seconds: (performance.now() - started) / 1000, inputs: metadata.inputs, grid: result.grid,
  checks: ["Class counts match Python", "Common-footprint transitions match Python", "Gross gains, losses and net changes match Python", "All forest metrics match Python within 1e-6", "Every fragmentation classification pixel matches Python by SHA-256"],
  limitation: "Software validation against independent Python/SciPy implementation. Not field validation or verified land-cover change." };
await writeFile(new URL(`${dataset}/validation.json`, root), JSON.stringify(report, null, 2) + "\n");
console.log(JSON.stringify(report, null, 2));
