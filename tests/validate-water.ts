import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { readWaterLayer, type WaterResult } from "../src/water/client";

const root = process.argv[2];
if (!root) throw new Error("Pass a directory containing checked online results.");
const result: WaterResult = JSON.parse(await readFile(path.join(root, "result.json"), "utf8"));
let checked = 0;
for (const spec of result.layers) {
  const bytes = await readFile(path.join(root, spec.file));
  const layer = await readWaterLayer(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer, result, spec);
  let total = 0, validArea = 0, eligibleArea = 0, cells = 0;
  for (let i = 0; i < layer.values.length; i++) {
    eligibleArea += layer.areas[i];
    if (Number.isFinite(layer.values[i]) && layer.areas[i] > 0) { total += layer.values[i] * layer.areas[i]; validArea += layer.areas[i]; cells++; }
  }
  assert.equal(cells, spec.stats.cells);
  if (validArea) assert.ok(Math.abs(total / validArea - spec.stats.mean!) < 1e-4, `${spec.id} mean disagrees`);
  else assert.equal(spec.stats.mean, null);
  assert.ok(Math.abs(100 * validArea / eligibleArea - spec.stats.coveragePct) < 1e-4);
  checked++;
}
console.log(JSON.stringify({ status:"passed", maps_checked:checked, checks:"GeoTIFF grid/NoData and independently recomputed browser area-weighted means, coverage and pixel counts" },null,2));
