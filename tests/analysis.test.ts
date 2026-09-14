import assert from "node:assert/strict";
import { test } from "node:test";
import { fragment, reclassify, squaredDistance, transition } from "../src/analysis/compute";
import { alignRaster, geoTiff, makeGrid, rasterizeVector, readRaster, validateVector } from "../src/analysis/io";
import { parseCrosswalk, csv, WORLDCOVER } from "../src/analysis/presets";
import type { Raster, VectorCollection } from "../src/analysis/model";

const grid = { width: 9, height: 9, cell: 10, left: 0, top: 90, crs: "EPSG:6933" };
function ring() {
  const a = new Uint16Array(81).fill(20);
  for (let y = 1; y < 8; y++) for (let x = 1; x < 8; x++) a[y * 9 + x] = 10;
  a[40] = 20; return a;
}
test("known forest ring: area, clearings, exact edges", () => {
  const r = fragment(ring(), 9, 9, 10, [10], 10), m = r.metrics[0];
  assert.equal(m.forest_ha, .48); assert.equal(m.core_ha, .20);
  assert.equal(m.edge_ha, .28); assert.equal(m.clearing_ha, .01);
  assert.equal(m.TE_m, 320); assert.equal(m.NP, 1); assert.equal(m.MPS_ha, .48);
  assert.equal(r.data[40], 3);
});
test("unknown holes do not create clearings or edges", () => {
  const a = ring(); a[40] = 0;
  const r = fragment(a, 9, 9, 10, [10], 10);
  assert.equal(r.data[40], 255); assert.equal(r.metrics[0].clearing_ha, 0);
  assert.equal(r.metrics[0].TE_m, 280); assert.equal(r.metrics[0].core_ha, .24);
});
test("all-forest administrative boundary behaviour", () => {
  const a = new Uint16Array(49).fill(10);
  assert.equal(fragment(a, 7, 7, 10, [10], 10).metrics[0].core_ha, .49);
  const m = fragment(a, 7, 7, 10, [10], 10, undefined, true).metrics[0];
  assert.equal(m.core_ha, .25); assert.equal(m.TE_m, 280);
});
test("protection stratification conserves area and does not cut forest", () => {
  const a = ring(), strata = new Uint8Array(81).fill(3);
  for (let i = 0; i < 81; i++) if (i % 9 < 4) strata[i] = 1; else if (i < 18) strata[i] = 2;
  const r = fragment(a, 9, 9, 10, [10], 10, strata);
  assert.deepEqual(r.data, fragment(a, 9, 9, 10, [10], 10).data);
  assert.equal(r.qa.straddling_patches, 1);
  for (const key of ["forest_ha", "TE_m", "NP"] as const) assert.ok(Math.abs(r.metrics.slice(1).reduce((s, m) => s + m[key], 0) - r.metrics[0][key]) < 1e-8);
  assert.ok(r.metrics.every(m => m.LPI <= 100));
  assert.equal(r.metrics.slice(1).find(m => m.NP)!.MPS_ha, .48);
});
test("Euclidean distance equals brute-force distances, including diagonals", () => {
  const seeds = new Uint8Array(42); seeds[2] = seeds[16] = seeds[37] = 1;
  const d = squaredDistance(seeds, 6, 7);
  for (let i = 0; i < 42; i++) assert.equal(d[i], Math.min(...[2, 16, 37].map(j => (i % 6 - j % 6) ** 2 + (Math.floor(i / 6) - Math.floor(j / 6)) ** 2)));
});
test("changes and gains/losses only use common valid footprint", () => {
  const a = reclassify({ year: 2020, name: "a", grid, data: Uint16Array.from([10, 10, 20, 0]) }, WORLDCOVER);
  const b = reclassify({ year: 2021, name: "b", grid, data: Uint16Array.from([10, 20, 0, 20]) }, WORLDCOVER);
  const t = transition(a, b, [10, 20]);
  assert.equal(t.valid, 2); assert.equal(t.changed, 1); assert.deepEqual(t.matrix, [[1, 1], [0, 0]]);
  assert.deepEqual(t.gains, [{ code: 10, gain: 0, loss: 1, net: -1 }, { code: 20, gain: 1, loss: 0, net: 1 }]);
});
test("crosswalk merges classes and rejects inconsistent definitions", () => {
  const rows = WORLDCOVER.map(r => r.source === 20 ? { ...r, code: 10, name: "Tree cover", color: "#006400" } : r);
  const source: Raster = { year: 2020, name: "x", grid, data: Uint16Array.from([10, 20, 0]) };
  assert.deepEqual([...reclassify(source, rows).data], [10, 10, 0]);
  assert.throws(() => reclassify(source, rows.map(r => r.source === 20 ? { ...r, name: "Different" } : r)), /conflicting/);
  assert.throws(() => reclassify(source, rows.filter(r => r.source !== 20)), /Unmapped/);
  assert.throws(() => fragment(ring(), 9, 9, 50, [10], 30), /at least/);
  assert.throws(() => fragment(ring(), 9, 9, 10, [], 50), /Choose/);
});
test("GeoTIFF roundtrip preserves integer values, CRS, NoData and cell geometry", async () => {
  const source = ring(); source[0] = 0;
  const buffer = geoTiff(source, grid, 0), raster = await readRaster(buffer, 2020, "roundtrip.tif");
  assert.deepEqual(raster.grid, grid); assert.deepEqual(raster.data, source);
  assert.deepEqual(alignRaster(raster, grid).data, source);
  const f = fragment(source, 9, 9, 10, [10], 10);
  const reread = await readRaster(geoTiff(f.data, grid, 255), 2020, "fragmentation.tif");
  assert.equal(reread.data[0], 0); assert.equal(reread.data[40], 3);
});
test("polygon masks preserve holes and protection precedence", () => {
  const v: VectorCollection = { type: "FeatureCollection", features: [{ type: "Feature", properties: {}, geometry: { type: "Polygon", coordinates: [[[0, 0], [.01, 0], [.01, .01], [0, .01], [0, 0]], [[.004, .004], [.006, .004], [.006, .006], [.004, .006], [.004, .004]]] } }] };
  validateVector(v);
  const g = makeGrid({ year: 1, name: "x", grid, data: ring() }, 100, v);
  const mask = rasterizeVector(v, g);
  assert.ok(mask.includes(0) && mask.includes(1));
  const s = new Uint8Array(mask.length).fill(3);
  rasterizeVector(v, g, s, 2); rasterizeVector(v, g, s, 1);
  assert.ok(s.includes(1) && !s.includes(2));
  assert.throws(() => makeGrid({ year: 1, name: "x", grid, data: ring() }, NaN), /resolution/);
});
test("CSV preserves quoted class names and escapes spreadsheet formulas", () => {
  const text = 'source_code,target_code,target_name,color\n10,10,"Trees, mixed",#006400\n';
  assert.equal(parseCrosswalk(text)[0].name, "Trees, mixed");
  assert.match(csv([["=CMD()", 1]]), /'=CMD/);
  assert.throws(() => parseCrosswalk('no,columns\n1,2'), /needs/);
});
