import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";
import { readVector } from "../src/analysis/io";
import { runAnalysis } from "../src/analysis/runner";
import { WORLDCOVER, parseCrosswalk } from "../src/analysis/presets";

const fixture = (name: string) => new URL(`fixtures/${name}`, import.meta.url);
async function input(year: number) {
  const buf = await readFile(fixture(`test_only_lulc_${year}.tif`));
  return { year, name: `test_only_${year}.tif`, buffer: Uint8Array.from(buf).buffer };
}
async function vector(name: string) {
  const buf = await readFile(fixture(name));
  return readVector(new File([Uint8Array.from(buf).buffer], name));
}
test("three uploaded periods, polygon AOI, zipped protection and OECM overlap", async () => {
  const result = await runAnalysis({ sources: await Promise.all([2017, 2021, 2025].map(input)),
    crosswalk: WORLDCOVER, forestCodes: [10], edge: 50, cell: 50, countBoundary: false, module: "both", dataset: "SYNTHETIC TEST ONLY", provenance: {},
    aoi: await vector("test_only_aoi.geojson"), protectedAreas: await vector("test_only_protected.zip"), oecm: await vector("test_only_oecm.geojson") }, () => {});
  assert.equal(result.periods.length, 3); assert.equal(result.transitions.length, 3);
  assert.deepEqual(result.periods.map(p => p.valid), [143, 143, 143]);
  assert.deepEqual(result.transitions.slice(0,2).map(t => t.changed), [5, 5]);
  assert.deepEqual(result.transitions.map(t=>[t.start,t.end]),[[2017,2021],[2021,2025],[2017,2025]]);
  let fullChange = 0;
  result.periods[0].data.forEach((value,i)=>{const target=result.periods[2].data[i];if(value && target && value!==target)fullChange++;});
  assert.equal(result.transitions[2].changed,fullChange);
  assert.deepEqual(result.periods[0].fragmentation!.metrics.map(m => m.stratum), ["All", "Protected", "OECM", "Unprotected"]);
  const first = result.periods[0].fragmentation!.metrics;
  assert.equal(first[1].landscape_ha, 71 * .25);
  assert.equal(first[2].landscape_ha, 36 * .25);
  assert.equal(first[3].landscape_ha, 36 * .25);
  const total = first.slice(1).reduce((s, r) => s + r.forest_ha, 0);
  assert.equal(total, first[0].forest_ha);
});
test("custom CSV merges, single-year forest module and configurable edge depth", async () => {
  const common = { crosswalk: parseCrosswalk(await readFile(fixture("merge_crosswalk.csv"), "utf8")), forestCodes: [10], cell: 50, countBoundary: true, module: "fragmentation" as const, dataset: "SYNTHETIC TEST ONLY", provenance: {} };
  const narrow = await runAnalysis({ ...common, sources: [await input(2017)], edge: 50 }, () => {});
  const wide = await runAnalysis({ ...common, sources: [await input(2017)], edge: 150 }, () => {});
  assert.equal(narrow.transitions.length, 0);
  assert.equal(narrow.classes.length, 1);
  assert.equal(narrow.periods[0].fragmentation!.metrics[0].forest_ha, 143 * .25);
  assert.ok(narrow.periods[0].fragmentation!.metrics[0].core_ha > wide.periods[0].fragmentation!.metrics[0].core_ha);
});
test("invalid years, absent periods, unknown forest classes, oversized grid", async () => {
  const base = { crosswalk: WORLDCOVER, forestCodes: [10], edge: 50, cell: 50, countBoundary: false, module: "both" as const, dataset: "SYNTHETIC TEST ONLY", provenance: {} };
  await assert.rejects(() => runAnalysis({ ...base, sources: [] }, () => {}), /2–3/);
  await assert.rejects(async () => runAnalysis({ ...base, sources: [await input(2017), await input(2017)] }, () => {}), /distinct/);
  await assert.rejects(async () => runAnalysis({ ...base, forestCodes: [500], sources: [await input(2017), await input(2021)] }, () => {}), /target classes/);
  await assert.rejects(async () => runAnalysis({ ...base, cell: Infinity, sources: [await input(2017), await input(2021)] }, () => {}), /resolution/);
});
