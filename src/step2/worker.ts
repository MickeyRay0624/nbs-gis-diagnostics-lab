import { calculateLayer } from "./compute";
import { readNumericRaster, validateCatalog } from "./io";
import type { Catalog, ModuleId, NumericRaster } from "./model";

self.onmessage = async (event: MessageEvent<{ catalog: Catalog; moduleId: ModuleId; base: string; files?: Record<string, ArrayBuffer> }>) => {
  try {
    const { moduleId, base, files } = event.data, catalog = validateCatalog(event.data.catalog);
    const module = catalog.modules.find(m => m.id === moduleId);
    if (!module || module.status !== "available" || !module.layers.length) throw new Error("This module still needs a validated data package.");
    const ids = new Set(module.layers.flatMap(l => l.inputs.map(i => i.raster))), rasters = new Map<string, NumericRaster>();
    for (const id of ids) {
      const asset = catalog.rasters.find(r => r.id === id)!;
      self.postMessage({ type: "progress", message: `Checking and reading ${asset.file}…` });
      let buffer = files?.[asset.file];
      if (!buffer) { if (files) throw new Error(`Upload ${asset.file} alongside the catalog.`); const response = await fetch(new URL(asset.file, base)); if (!response.ok) throw new Error(`Could not load ${asset.file} (${response.status}).`); buffer = await response.arrayBuffer(); }
      rasters.set(id, await readNumericRaster(buffer, asset));
    }
    const layers = module.layers.map(l => calculateLayer(l, rasters));
    const manifest = { schema: "nbs-step2-run/v1", catalog_version: catalog.version, prepared_at: catalog.preparedAt, computed_at: new Date().toISOString(),
      module: moduleId, study_area: catalog.studyArea, inputs: [...ids].map(id => catalog.rasters.find(r => r.id === id)),
      sources: catalog.sources.filter(s => module.sources.includes(s.id)), methods: module.method, limitations: module.limitations,
      execution: "Public source preparation is offline / Earth Engine. Hash verification, map arithmetic and AOI-weighted statistics run in a browser Web Worker.",
      outputs: layers.map(l => ({ ...l.spec, grid: l.grid, statistics: l.stats })), protection: catalog.protection, expert_review: catalog.review };
    self.postMessage({ type: "result", result: { module, layers, manifest } });
  } catch (error) { self.postMessage({ type: "error", message: error instanceof Error ? error.message : String(error) }); }
};
