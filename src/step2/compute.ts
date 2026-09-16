import type { LayerResult, LayerSpec, NumericGrid, NumericRaster } from "./model";

export function sameGrid(a: NumericGrid, b: NumericGrid): boolean {
  return a.crs === b.crs && a.width === b.width && a.height === b.height &&
    ["left", "top", "dx", "dy"].every(k => Math.abs(a[k as keyof NumericGrid] - b[k as keyof NumericGrid]) <= Math.max(a.dx, a.dy) * 1e-7);
}

// Codes are -1 degraded, 0 stable, +1 improving. A known degraded component
// establishes degradation even if another component is missing; otherwise all
// three components are needed. Unknown land is never silently stable.
export function oneOutAllOut(values: number[]): number {
  if (values.length !== 3) throw new Error("Land degradation needs productivity, land cover and soil carbon.");
  if (values.some(v => Number.isFinite(v) && ![-1, 0, 1].includes(v))) throw new Error("Invalid subindicator class: expected -1, 0 or 1.");
  if (values.includes(-1)) return -1;
  if (values.some(v => !Number.isFinite(v))) return NaN;
  return values.includes(1) ? 1 : 0;
}

export function calculateLayer(spec: LayerSpec, rasters: Map<string, NumericRaster>): LayerResult {
  const expected = spec.operation === "identity" ? 1 : spec.operation === "one-out-all-out" ? 3 : 2;
  if (spec.inputs.length !== expected) throw new Error(`${spec.title}: expected ${expected} input bands.`);
  const inputs = spec.inputs.map(ref => {
    const raster = rasters.get(ref.raster);
    if (!raster || !Number.isInteger(ref.band) || !raster.bands[ref.band - 1]) throw new Error(`${spec.title}: input band is missing.`);
    return { raster, data: raster.bands[ref.band - 1] };
  });
  const reference = inputs[0].raster;
  if (inputs.some(x => !sameGrid(reference.grid, x.raster.grid))) throw new Error(`${spec.title}: inputs must share a grid; prepare them before comparison.`);
  const areas = reference.bands[reference.asset.areaBand - 1];
  if (!areas) throw new Error("An AOI intersection area band is required for area-weighted statistics.");
  for (const input of inputs) {
    const other = input.raster.bands[input.raster.asset.areaBand - 1];
    if (!other || other.some((value, i) => !Number.isFinite(value) || Math.abs(value - areas[i]) > 1e-5)) throw new Error("Compared rasters must use identical AOI area weights.");
  }
  const length = reference.grid.width * reference.grid.height;
  if (areas.length !== length || inputs.some(i=>i.data.length !== length || i.raster.bands[i.raster.asset.areaBand-1].length !== length)) throw new Error("Raster band lengths must match the declared grid.");
  const values = new Float32Array(length).fill(NaN);
  const classes = spec.categories?.map(c => ({ label: c.label, areaKm2: 0, percent: null as number | null })) ??
    spec.thresholds?.map(c => ({ label: c.label, areaKm2: 0, percent: null as number | null })) ?? [];
  let eligible = 0, valid = 0, total = 0, min = Infinity, max = -Infinity, cells = 0;
  for (let i = 0; i < length; i++) {
    const area = areas[i];
    if (!Number.isFinite(area) || area < 0) throw new Error("Area weights must be finite, non-negative square kilometres.");
    if (area === 0) continue;
    eligible += area;
    const v = inputs.map(input => input.data[i]);
    let value = NaN;
    if (spec.operation === "one-out-all-out") value = oneOutAllOut(v);
    else if (v.every(Number.isFinite)) {
      value = spec.operation === "identity" ? v[0] : spec.operation === "difference" ? v[1] - v[0] : v[0] === 0 ? NaN : (v[1] - v[0]) / Math.abs(v[0]) * 100;
    }
    values[i] = value;
    value = values[i]; // Statistics describe the exported Float32 values exactly.
    if (!Number.isFinite(value)) continue;
    if (spec.categories && !spec.categories.some(c => c.value === value)) throw new Error(`${spec.title}: undeclared category ${value}.`);
    valid += area; total += area * value; min = Math.min(min, value); max = Math.max(max, value); cells++;
    if (spec.categories) spec.categories.forEach((c, j) => { if (value === c.value) classes[j].areaKm2 += area; });
    else spec.thresholds?.forEach((c, j) => { if ((c.min === undefined || value >= c.min) && (c.max === undefined || value < c.max)) classes[j].areaKm2 += area; });
  }
  classes.forEach(c => { c.percent = valid ? c.areaKm2 / valid * 100 : null; });
  return { spec, grid: reference.grid, values, areas, stats: { validAreaKm2: valid, eligibleAreaKm2: eligible,
    missingAreaKm2: Math.max(0, eligible - valid), coveragePct: eligible ? valid / eligible * 100 : 0,
    mean: valid ? total / valid : null, min: valid ? min : null, max: valid ? max : null, cells, classes } };
}
