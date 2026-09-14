import { fragment, reclassify, transition } from "./compute";
import { alignRaster, makeGrid, rasterizeVector, readRaster, sha256 } from "./io";
import type { LandClass, PeriodResult, Result, RunRequest } from "./model";

export async function runAnalysis(request: RunRequest, progress: (text: string) => void): Promise<Result> {
  const years = request.sources.map(s => s.year);
  if (new Set(years).size !== years.length || years.some(y => !Number.isInteger(y) || y < 1900 || y > 2100)) throw new Error("Choose distinct integer years between 1900 and 2100.");
  if (years.length < (request.module === "fragmentation" ? 1 : 2) || years.length > 3) throw new Error("LULC change needs 2–3 periods; fragmentation supports 1–3 periods.");
  const inputs = [];
  for (const s of [...request.sources].sort((a, b) => a.year - b.year)) {
    progress(`Reading ${s.year} land cover…`);
    let buffer = s.buffer;
    if (!buffer && s.url) { const response = await fetch(s.url); if (!response.ok) throw new Error(`Data download failed (${response.status}). Please retry.`); buffer = await response.arrayBuffer(); }
    if (!buffer) throw new Error(`Select a GeoTIFF for ${s.year}.`);
    const raster = await readRaster(buffer, s.year, s.name);
    if (s.expectedSha256 && raster.sha256 !== s.expectedSha256) throw new Error(`Integrity check failed for ${s.year}. Reload the page and try again.`);
    inputs.push(raster);
  }
  const grid = makeGrid(inputs[0], request.cell, request.aoi);
  if (request.module !== "lulc" && (!Number.isFinite(request.edge) || request.edge < grid.cell)) throw new Error("Edge width must be at least the analysis resolution.");
  progress("Aligning the equal-area grid and polygon masks…");
  const mask = request.aoi ? rasterizeVector(request.aoi, grid) : undefined;
  let strata: Uint8Array | undefined;
  if (request.protectedAreas || request.oecm) {
    strata = new Uint8Array(grid.width * grid.height).fill(3);
    if (request.oecm) rasterizeVector(request.oecm, grid, strata, 2);
    if (request.protectedAreas) rasterizeVector(request.protectedAreas, grid, strata, 1);
  }
  const classes = new Map<number, LandClass>();
  for (const r of request.crosswalk) classes.set(r.code, { code: r.code, name: r.name, color: r.color });
  if (request.module !== "lulc" && request.forestCodes.some(c => !classes.has(c))) throw new Error("Forest codes must be target classes in the crosswalk.");
  const periods: PeriodResult[] = [];
  for (const input of inputs) {
    progress(`Reclassifying ${input.year} on the common grid…`);
    const p = reclassify(alignRaster(input, grid, mask), request.crosswalk);
    if (request.module !== "lulc") {
      progress(`Calculating ${input.year} forest patches and distances…`);
      p.fragmentation = fragment(p.data, grid.width, grid.height, grid.cell, request.forestCodes, request.edge, strata, request.countBoundary);
    }
    periods.push(p);
  }
  const codes = [...classes.keys()].sort((a, b) => a - b);
  progress("Calculating transitions, gains, losses and quality checks…");
  const transitions = request.module === "fragmentation" ? [] : periods.slice(1).map((p, i) => transition(periods[i], p, codes));
  const hashVector = async (v: unknown) => v ? sha256(new TextEncoder().encode(JSON.stringify(v)).buffer) : null;
  return { grid, classes: codes.map(c => classes.get(c)!), periods, transitions, manifest: {
    schema: "nbs-browser-analysis/v1", computed_at: new Date().toISOString(), dataset: request.dataset,
    module: request.module, years: periods.map(p => p.year), grid, resampling: "nearest-neighbour; pixel-centre sampling",
    inputs: inputs.map(i => ({ name: i.name, year: i.year, sha256: i.sha256, grid: i.grid })),
    provenance: request.provenance, crosswalk: request.crosswalk, source_nodata: "GeoTIFF NoData and code 0",
    forest_codes: request.forestCodes, edge_width_m: request.edge, count_boundary_as_edge: request.countBoundary,
    protection: { available: !!strata, precedence: "Protected > OECM > remainder of supplied coverage",
      aoi_sha256: await hashVector(request.aoi), protected_sha256: await hashVector(request.protectedAreas), oecm_sha256: await hashVector(request.oecm) },
    qa: { class_conservation: periods.every(p => Object.values(p.counts).reduce((s, n) => s + n, 0) === p.valid),
      transition_conservation: transitions.every(t => t.matrix.flat().reduce((s, n) => s + n, 0) === t.valid),
      valid_pixels: periods.map(p => ({ year: p.year, count: p.valid, coverage_pct: p.valid / (mask ? mask.reduce((s, n) => s + n, 0) : grid.width * grid.height) * 100 })),
      fragmentation: periods.map(p => ({ year: p.year, ...p.fragmentation?.qa })) },
    methodology: { forest_connectivity: 8, clearing_connectivity: 4, clearings: "Enclosed non-forest components with no contact with NoData or the grid boundary; excluded from forest area.",
      patch_assignment: "Whole patch to majority stratum; ties Protected, OECM, Unprotected.",
      area_and_edge: "Pixel allocation. Administrative protection boundaries never add edges.",
      MPS: "Mean area of assigned whole patches.", LPI: "Largest patch intersection / stratum landscape area × 100.",
      clearings_intersecting: "Count of clearings intersecting each stratum; these counts need not sum to All." },
    limitations: ["Technical analysis, subject to data quality and GIS review.",
      "Forest is inferred from selected land-cover classes, not field validation.",
      "Results depend on analysis resolution and edge width; source detail lost by resampling is not recovered.",
      "Outside-AOI forest continuity is unknown; the optional boundary setting controls this assumption.",
      ...(request.dataset.includes("WorldCover") ? ["WorldCover 2020 v100 and 2021 v200 use different algorithms; their differences are not verified land-cover change."] : []),
      ...(!strata ? ["No protection dataset supplied; only All statistics are computed."] : ["Unprotected means outside the supplied polygons; completeness and historical validity must be checked."])],
  } };
}
