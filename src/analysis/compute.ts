import type { CrosswalkRow, FragmentResult, Metrics, PeriodResult, Raster, Transition } from "./model";

export function reclassify(raster: Raster, rows: CrosswalkRow[]): PeriodResult {
  const map = new Map(rows.map(r => [r.source, r.code]));
  if (map.size !== rows.length) throw new Error("Each source class must appear once in the crosswalk.");
  const definitions = new Map<number, string>();
  for (const r of rows) {
    if (!Number.isInteger(r.source) || r.source < 1 || r.source > 65534 || !Number.isInteger(r.code) || r.code < 1 || r.code > 999 || !r.name.trim() || !/^#[0-9a-f]{6}$/i.test(r.color))
      throw new Error("Crosswalk requires source codes 1–65534, target codes 1–999, names and #RRGGBB colours. Code 0 is NoData.");
    const definition = `${r.name}|${r.color.toLowerCase()}`;
    if (definitions.has(r.code) && definitions.get(r.code) !== definition) throw new Error(`Target ${r.code} has conflicting names or colours.`);
    definitions.set(r.code, definition);
  }
  const data = new Uint16Array(raster.data.length), counts: Record<number, number> = {};
  let valid = 0;
  for (let i = 0; i < data.length; i++) {
    const source = raster.data[i];
    if (!source) continue;
    const code = map.get(source);
    if (code === undefined) throw new Error(`Unmapped source class ${source} in ${raster.year}. Add it to the crosswalk.`);
    data[i] = code; counts[code] = (counts[code] || 0) + 1; valid++;
  }
  if (!valid) throw new Error(`No valid mapped pixels in ${raster.year}. Check AOI overlap and NoData.`);
  return { year: raster.year, data, counts, valid };
}

export function transition(a: PeriodResult, b: PeriodResult, codes: number[]): Transition {
  const index = new Map(codes.map((v, i) => [v, i]));
  const matrix = codes.map(() => codes.map(() => 0));
  const data = new Uint8Array(a.data.length).fill(255);
  let valid = 0, changed = 0;
  for (let i = 0; i < data.length; i++) {
    const from = a.data[i], to = b.data[i];
    if (!from || !to) continue;
    matrix[index.get(from)!][index.get(to)!]++; valid++;
    data[i] = from === to ? 0 : 1; changed += data[i];
  }
  if (!valid) throw new Error(`No common valid pixels for ${a.year}–${b.year}.`);
  return { start: a.year, end: b.year, valid, changed, matrix, codes, data,
    gains: codes.map((code, i) => {
      const loss = matrix[i].reduce((s, n) => s + n, 0) - matrix[i][i];
      const gain = matrix.reduce((s, row) => s + row[i], 0) - matrix[i][i];
      return { code, gain, loss, net: gain - loss };
    }),
  };
}

// Exact squared Euclidean distance, separable lower envelopes of parabolas.
export function squaredDistance(seeds: Uint8Array, width: number, height: number) {
  const n = Math.max(width, height), f = new Float64Array(n), d = new Float64Array(n);
  const v = new Int32Array(n), z = new Float64Array(n + 1), out = new Float64Array(seeds.length);
  const edt = (length: number) => {
    let k = 0; v[0] = 0; z[0] = -Infinity; z[1] = Infinity;
    for (let q = 1; q < length; q++) {
      let s = ((f[q] + q * q) - (f[v[k]] + v[k] * v[k])) / (2 * (q - v[k]));
      while (s <= z[k]) { k--; s = ((f[q] + q * q) - (f[v[k]] + v[k] * v[k])) / (2 * (q - v[k])); }
      k++; v[k] = q; z[k] = s; z[k + 1] = Infinity;
    }
    k = 0;
    for (let q = 0; q < length; q++) { while (z[k + 1] < q) k++; d[q] = (q - v[k]) ** 2 + f[v[k]]; }
  };
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) f[x] = seeds[y * width + x] ? 0 : 1e12;
    edt(width); out.set(d.subarray(0, width), y * width);
  }
  for (let x = 0; x < width; x++) {
    for (let y = 0; y < height; y++) f[y] = out[y * width + x];
    edt(height);
    for (let y = 0; y < height; y++) out[y * width + x] = d[y];
  }
  return out;
}

function components(mask: Uint8Array, width: number, height: number, eight: boolean) {
  const labels = new Int32Array(mask.length), queue = new Int32Array(mask.length);
  let count = 0;
  for (let i = 0; i < mask.length; i++) {
    if (!mask[i] || labels[i]) continue;
    count++; let head = 0, tail = 1; queue[0] = i; labels[i] = count;
    while (head < tail) {
      const p = queue[head++], x = p % width, y = Math.floor(p / width);
      for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
        if ((!dx && !dy) || (!eight && dx && dy)) continue;
        const nx = x + dx, ny = y + dy;
        if (nx < 0 || nx >= width || ny < 0 || ny >= height) continue;
        const j = ny * width + nx;
        if (mask[j] && !labels[j]) { labels[j] = count; queue[tail++] = j; }
      }
    }
  }
  return { labels, count };
}

export function fragment(data: Uint16Array, width: number, height: number, cell: number,
  forestCodes: number[], edge: number, strata?: Uint8Array, countBoundary = false): FragmentResult {
  if (data.length !== width * height || width < 1 || height < 1) throw new Error("Invalid raster dimensions.");
  if (!Number.isFinite(cell) || cell <= 0 || !Number.isFinite(edge) || edge < cell) throw new Error("Forest edge width must be at least one analysis cell.");
  if (!forestCodes.length || forestCodes.includes(0)) throw new Error("Choose at least one forest class; NoData cannot be forest.");
  if (strata && (strata.length !== data.length || strata.some((v, i) => data[i] > 0 && ![1, 2, 3].includes(v)))) throw new Error("Protection strata must match the grid.");
  const codes = new Set(forestCodes), forest = new Uint8Array(data.length), seeds = new Uint8Array(data.length);
  let forestPixels = 0, validPixels = 0;
  for (let i = 0; i < data.length; i++) {
    if (data[i]) validPixels++;
    forest[i] = +(data[i] > 0 && codes.has(data[i])); forestPixels += forest[i];
    seeds[i] = +(!forest[i] && (data[i] > 0 || countBoundary));
  }
  const distance = squaredDistance(seeds, width, height);
  const { labels, count } = components(forest, width, height, true);
  const hasCore = new Uint8Array(count + 1), areas = new Float64Array(count + 1), perims = new Float64Array(count + 1);
  const sides = new Uint8Array(data.length), out = new Uint8Array(data.length);
  const portions = strata ? [1, 2, 3].map(() => new Uint32Array(count + 1)) : undefined;
  for (let i = 0; i < data.length; i++) {
    if (!data[i]) { out[i] = 255; continue; }
    if (!forest[i]) continue;
    const x = i % width, y = Math.floor(i / width), label = labels[i];
    let d = distance[i];
    if (countBoundary) d = Math.min(d, (x + 1) ** 2, (width - x) ** 2, (y + 1) ** 2, (height - y) ** 2);
    out[i] = d * cell * cell > edge * edge ? 4 : 2;
    if (out[i] === 4) hasCore[label] = 1;
    areas[label]++;
    if (strata) portions![strata[i] - 1][label]++;
    for (const [dx, dy] of [[-1, 0], [1, 0], [0, -1], [0, 1]]) {
      const nx = x + dx, ny = y + dy;
      if (nx < 0 || nx >= width || ny < 0 || ny >= height) { if (countBoundary) sides[i]++; }
      else { const j = ny * width + nx; if (!forest[j] && (data[j] || countBoundary)) sides[i]++; }
    }
    perims[label] += sides[i] * cell;
  }
  const background = Uint8Array.from(forest, v => +!v);
  const bg = components(background, width, height, false), exterior = new Uint8Array(bg.count + 1);
  exterior[0] = 1;
  for (let i = 0; i < data.length; i++) if (!data[i] || i < width || i >= data.length - width || i % width === 0 || i % width === width - 1) exterior[bg.labels[i]] = 1;
  for (let i = 0; i < data.length; i++) {
    if (forest[i] && !hasCore[labels[i]]) out[i] = 1;
    if (data[i] && !forest[i] && !exterior[bg.labels[i]]) out[i] = 3;
  }
  const assignment = new Uint8Array(count + 1);
  let straddling = 0;
  for (let label = 1; label <= count; label++) if (portions) {
    let best = 0, present = 0;
    for (let s = 0; s < 3; s++) { if (portions[s][label]) present++; if (portions[s][label] > portions[best][label]) best = s; }
    assignment[label] = best + 1; if (present > 1) straddling++;
  }
  const cellHa = cell * cell / 10000;
  const metrics: Metrics[] = (strata ? [0, 1, 2, 3] : [0]).map(s => {
    const cls = [0, 0, 0, 0, 0], holes = new Set<number>(); let landscape = 0, sideSum = 0;
    for (let i = 0; i < data.length; i++) if (data[i] && (!s || strata![i] === s)) {
      landscape++; cls[out[i]]++; sideSum += sides[i]; if (out[i] === 3) holes.add(bg.labels[i]);
    }
    let np = 0, areaSum = 0, perimSum = 0, shapeSum = 0, weightedShape = 0, largest = 0;
    for (let label = 1; label <= count; label++) {
      largest = Math.max(largest, s ? portions![s - 1][label] : areas[label]);
      if (s && assignment[label] !== s) continue;
      const a = areas[label] * cell * cell, p = perims[label], shape = .25 * p / Math.sqrt(a);
      np++; areaSum += a; perimSum += p; shapeSum += shape; weightedShape += shape * a;
    }
    const fn = cls[1] + cls[2] + cls[4], te = sideSum * cell;
    return { stratum: ["All", "Protected", "OECM", "Unprotected"][s], landscape_ha: landscape * cellHa,
      forest_ha: fn * cellHa, PLAND: landscape ? fn / landscape * 100 : 0,
      patch_ha: cls[1] * cellHa, edge_ha: cls[2] * cellHa, core_ha: cls[4] * cellHa, clearing_ha: cls[3] * cellHa,
      core_pct: fn ? cls[4] / fn * 100 : 0, NP: np, TE_m: te, ED: landscape ? te / (landscape * cellHa) : 0,
      MPS_ha: np ? areaSum / np / 10000 : 0, MPE: np ? perimSum / np : 0, MSI: np ? shapeSum / np : 0,
      AWMSI: areaSum ? weightedShape / areaSum : 0, LPI: landscape ? largest / landscape * 100 : 0,
      largest_patch_ha: largest * cellHa, clearings_intersecting: holes.size };
  });
  return { data: out, metrics, qa: { forest_pixels: forestPixels, valid_pixels: validPixels,
    class_conservation: Math.abs(metrics[0].patch_ha + metrics[0].edge_ha + metrics[0].core_ha - forestPixels * cellHa) < 1e-6,
    straddling_patches: straddling, connectivity: 8, clearing_connectivity: 4,
    edge_width_m: edge, count_boundary_as_edge: countBoundary, protection_available: !!strata } };
}
