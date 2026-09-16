import test from "node:test";
import assert from "node:assert/strict";
import { fromArrayBuffer } from "geotiff";
import { calculateLayer, oneOutAllOut } from "../src/step2/compute";
import { numericGeoTiff } from "../src/step2/io";
import type { NumericRaster, LayerSpec } from "../src/step2/model";

const raster = (bands: number[][]): NumericRaster => ({
  grid: { width: bands[0].length, height: 1, crs: 4326, left: 84, top: 20, dx: .25, dy: .25 },
  bands: bands.map(b => Float32Array.from(b)),
  asset: { id: "r", file: "r.tif", sha256: "", source: "test", bands: bands.map((_, i) => String(i)), areaBand: bands.length, grid: { width: bands[0].length, height: 1, crs: 4326, left: 84, top: 20, dx: .25, dy: .25 }, nativeResolution: "0.25 degrees", processing: "Test fixture" },
});
const layer = (operation: LayerSpec["operation"], count = operation === "identity" ? 1 : 2): LayerSpec => ({ id: "test", title: "Test", unit: "mm", period: "test", operation, inputs: Array.from({ length: count }, (_, i) => ({ raster: "r", band: i + 1 })), palette: "diverging", interpretation: "Test only" });

test("continuous change uses common support and fractional area; zero and negative values are valid", () => {
  const r = raster([[0, -5, 10, NaN], [2, -8, NaN, 7], [1, 3, 2, 4]]);
  const result = calculateLayer(layer("difference"), new Map([["r", r]]));
  assert.deepEqual([...result.values], [2, -3, NaN, NaN]);
  assert.equal(result.stats.mean, -1.75);
  assert.equal(result.stats.validAreaKm2, 4);
  assert.equal(result.stats.missingAreaKm2, 6);
  assert.equal(result.stats.coveragePct, 40);
});

test("relative changes have no invented zero-baseline percentages", () => {
  const result = calculateLayer(layer("percent-change"), new Map([["r", raster([[0, 10], [1, 8], [1, 1]])]]));
  assert.deepEqual([...result.values], [NaN, -20]);
});

test("one-out-all-out requires three components and preserves unresolved missing data", () => {
  assert.equal(oneOutAllOut([-1, NaN, 0]), -1);
  assert.ok(Number.isNaN(oneOutAllOut([0, NaN, 1])));
  assert.equal(oneOutAllOut([0, 1, 0]), 1);
  assert.equal(oneOutAllOut([0, 0, 0]), 0);
  assert.throws(() => oneOutAllOut([0, 0]), /needs productivity/);
  assert.throws(() => oneOutAllOut([0, 2, 1]), /Invalid/);
});

test("empty evidence remains missing; impossible weights and mismatched grids fail", () => {
  const result = calculateLayer(layer("identity"), new Map([["r", raster([[NaN, NaN], [1, 2]])]]));
  assert.equal(result.stats.mean, null); assert.equal(result.stats.min, null); assert.equal(result.stats.coveragePct, 0);
  assert.throws(() => calculateLayer(layer("identity"), new Map([["r", raster([[1, 2], [1, -1]])]])), /weights/);
  const a = raster([[1], [1]]), b = raster([[2], [1]]); b.grid.left += .25;
  const spec = layer("difference"); spec.inputs[1] = { raster: "b", band: 1 };
  assert.throws(() => calculateLayer(spec, new Map([["r", a], ["b", b]])), /share a grid/);
});

test("Float32 GeoTIFF exports preserve negative values, true zero, NoData and geographic resolution", async () => {
  const result = calculateLayer(layer("identity"), new Map([["r", raster([[-2.5, 0, NaN], [1, 1, 1]])]]));
  const tif = await fromArrayBuffer(numericGeoTiff(result)), image = await tif.getImage();
  assert.deepEqual([...await image.readRasters({ interleave: true })], [-2.5, 0, NaN]);
  assert.equal(image.getGeoKeys()?.GeographicTypeGeoKey, 4326);
  assert.deepEqual(image.getResolution().slice(0, 2), [.25, -.25]);
  assert.ok(Number.isNaN(image.getGDALNoData()));
});

test("catalog rejects malformed legends, dangerous paths, oversized decoded arrays and unsupported input counts", async () => {
  const { readFile } = await import("node:fs/promises");
  const { validateCatalog } = await import("../src/step2/io");
  const original = JSON.parse(await readFile(new URL("../public/data/step2/catalog.json", import.meta.url), "utf8"));
  const change = (mutate: (c: any) => void, pattern: RegExp) => {const c=structuredClone(original);mutate(c);assert.throws(()=>validateCatalog(c),pattern);};
  assert.equal(validateCatalog(original).modules.length,7);
  change(c=>c.rasters[0].file="../other.tif", /local TIFF/);
  change(c=>c.rasters[0].bands=Array(257).fill("x"), /area-weight/);
  change(c=>c.modules.find((m:any)=>m.id==="climate").layers[0].inputs=[], /input bands/);
  change(c=>c.modules.find((m:any)=>m.id==="degradation").layers[0].categories[0].color="red", /class legend/);
  change(c=>c.modules.find((m:any)=>m.id==="drought").layers[0].thresholds[1].min=-10, /non-overlapping/);
  change(c=>c.modules.find((m:any)=>m.id==="groundwater").series[0].points[0].value=Infinity, /observations/);
});

test("numeric input integrity rejects changed bytes and mismatched georeferencing", async () => {
  const { readFile } = await import("node:fs/promises");
  const { readNumericRaster } = await import("../src/step2/io");
  const c=JSON.parse(await readFile(new URL("../public/data/step2/catalog.json",import.meta.url),"utf8"));
  const asset=c.rasters.find((r:any)=>r.id==="gldas-groundwater");
  const bytes=await readFile(new URL(`../public/data/step2/${asset.file}`,import.meta.url));
  const input=Uint8Array.from(bytes).buffer;
  await readNumericRaster(input,asset);
  const changed=input.slice(0);new Uint8Array(changed)[10]^=1;
  await assert.rejects(()=>readNumericRaster(changed,asset),/checksum mismatch/);
  await assert.rejects(()=>readNumericRaster(input,{...asset,grid:{...asset.grid,top:asset.grid.top+1}}),/georeferencing/);
});
