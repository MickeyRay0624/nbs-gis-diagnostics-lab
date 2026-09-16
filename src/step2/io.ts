import { fromArrayBuffer, writeArrayBuffer } from "geotiff";
import type { Catalog, NumericRaster, RasterAsset, LayerResult } from "./model";
import { MODULE_IDS } from "./model";

export async function digest(buffer: ArrayBuffer): Promise<string> {
  return [...new Uint8Array(await crypto.subtle.digest("SHA-256", buffer))].map(v => v.toString(16).padStart(2, "0")).join("");
}

export function validateCatalog(value: unknown): Catalog {
  const c = value as Catalog;
  if (!c || c.schema !== "nbs-step2/v1" || !Array.isArray(c.modules) || !Array.isArray(c.rasters) || !Array.isArray(c.sources)) throw new Error("Expected an nbs-step2/v1 data catalog.");
  if (!c.studyArea || !(c.studyArea.areaKm2 > 0) || !c.protection || !c.review) throw new Error("Catalog needs study-area, protection and review metadata.");
  for (const key of [c.modules, c.rasters, c.sources]) if (new Set(key.map(v => v.id)).size !== key.length) throw new Error("Catalog IDs must be unique.");
  if (c.modules.length !== 7 || MODULE_IDS.some(id => !c.modules.some(m => m.id === id))) throw new Error("Catalog must describe all seven Step 2 modules.");
  const nonempty = (v: unknown): v is string => typeof v === "string" && v.trim().length > 0;
  const textList = (v: unknown) => Array.isArray(v) && v.every(nonempty);
  if (!nonempty(c.version) || !nonempty(c.preparedAt) || !nonempty(c.studyArea.name) || !/^[a-f0-9]{64}$/.test(c.studyArea.sha256) || !Number.isFinite(c.studyArea.areaKm2)) throw new Error("Catalog identity or boundary checksum is invalid.");
  if (!["pending", "reviewed"].includes(c.review.status) || !nonempty(c.review.detail) || !["not-assessed", "assessed"].includes(c.protection.status) || !nonempty(c.protection.detail)) throw new Error("Catalog review and protection evidence are required.");
  if (c.rasters.length > 32 || c.sources.length > 64) throw new Error("The catalog exceeds the browser package limit.");
  for (const source of c.sources) {
    if (![source.id, source.name, source.version, source.licence, source.description].every(nonempty) || !/^https:\/\//.test(source.url)) throw new Error("Each source needs a name, version, licence, description and HTTPS URL.");
  }
  for (const r of c.rasters) {
    if (!/^[a-zA-Z0-9_-]+\.tif$/.test(r.file) || !/^[a-f0-9]{64}$/.test(r.sha256)) throw new Error("Raster files need a local TIFF filename and SHA-256 checksum.");
    if (!c.sources.some(s => s.id === r.source)) throw new Error(`${r.id}: source provenance is missing.`);
    const g = r.grid;
    if (!g || ![4326, 6933, 3857].includes(g.crs) || ![g.left, g.top, g.dx, g.dy].every(Number.isFinite) || g.dx <= 0 || g.dy <= 0 || !Number.isInteger(g.width) || !Number.isInteger(g.height) || g.width < 1 || g.height < 1 || g.width * g.height > 8_000_000) throw new Error(`${r.id}: invalid or oversized numeric grid.`);
    if (!nonempty(r.nativeResolution) || !(nonempty(r.processing) || textList(r.processing))) throw new Error(`${r.id}: source scale and processing are required.`);
    if (!Array.isArray(r.bands) || !r.bands.length || r.bands.length > 256 || !r.bands.every(nonempty) || r.bands.length * g.width * g.height > 40_000_000 || !Number.isInteger(r.areaBand) || r.areaBand < 1 || r.areaBand > r.bands.length) throw new Error(`${r.id}: area-weight band is missing.`);
  }
  for (const m of c.modules) {
    if (!["available", "needs-data"].includes(m.status) || !Array.isArray(m.layers) || !Array.isArray(m.method) || !Array.isArray(m.limitations) || !Array.isArray(m.fieldChecks)) throw new Error(`${m.id}: incomplete methods or layer metadata.`);
    if (![m.title, m.question].every(nonempty) || !textList(m.sources) || !textList(m.method) || !m.method.length || !textList(m.limitations) || !m.limitations.length || !textList(m.fieldChecks) || !m.fieldChecks.length || m.layers.length > 128) throw new Error(`${m.id}: methods, limitations and field questions are required.`);
    if (m.sources.some(id => !c.sources.some(s => s.id === id))) throw new Error(`${m.id}: source metadata is missing.`);
    if (new Set(m.layers.map(l => l.id)).size !== m.layers.length) throw new Error(`${m.id}: duplicate layer ID.`);
    if (m.status === "available" && !["lulc", "fragmentation"].includes(m.id) && !m.layers.length) throw new Error(`${m.id}: an available module needs numeric layers.`);
    for (const series of m.series ?? []) {
      if (!nonempty(series.title) || !nonempty(series.unit) || !Array.isArray(series.points) || series.points.length > 10000 || new Set(series.points.map(p => p.date)).size !== series.points.length || series.points.some(p => !nonempty(p.date) || (p.value !== null && !Number.isFinite(p.value)) || (p.coveragePct !== undefined && (!Number.isFinite(p.coveragePct) || p.coveragePct < 0 || p.coveragePct > 100.00001)))) throw new Error(`${m.id}: invalid time-series observations.`);
    }
    let outputCells = 0;
    const requiredRasters = new Set<string>();
    for (const l of m.layers) {
      if (!["identity", "difference", "percent-change", "one-out-all-out"].includes(l.operation)) throw new Error(`${l.id}: unsupported operation.`);
      if (![l.id, l.title, l.unit, l.period, l.interpretation].every(nonempty) || !["sequential", "diverging", "water", "health"].includes(l.palette)) throw new Error(`${l.id}: layer units, period, interpretation and palette are required.`);
      const count = l.operation === "identity" ? 1 : l.operation === "one-out-all-out" ? 3 : 2;
      if (!Array.isArray(l.inputs) || l.inputs.length !== count) throw new Error(`${l.id}: wrong number of input bands.`);
      if (l.domain && (l.domain.length !== 2 || !l.domain.every(Number.isFinite) || l.domain[1] <= l.domain[0])) throw new Error(`${l.id}: invalid display range.`);
      if (l.categories && (!l.categories.length || l.categories.length > 64 || new Set(l.categories.map(v=>v.value)).size !== l.categories.length || l.categories.some(v=>!Number.isFinite(v.value) || !nonempty(v.label) || !/^#[0-9a-f]{6}$/i.test(v.color)))) throw new Error(`${l.id}: invalid class legend.`);
      if (l.categories && l.thresholds) throw new Error(`${l.id}: use categories or numeric thresholds, not both.`);
      if (l.thresholds) {
        for (let i=0;i<l.thresholds.length;i++) {
          const t=l.thresholds[i], low=t.min ?? -Infinity, high=t.max ?? Infinity;
          if (!nonempty(t.label) || (t.min !== undefined && !Number.isFinite(t.min)) || (t.max !== undefined && !Number.isFinite(t.max)) || low >= high || (i > 0 && low < (l.thresholds[i-1].max ?? Infinity))) throw new Error(`${l.id}: thresholds must be ordered and non-overlapping.`);
        }
      }
      for (const ref of l.inputs) {
        const r = c.rasters.find(r => r.id === ref.raster);
        requiredRasters.add(ref.raster);
        if (!r || !Number.isInteger(ref.band) || ref.band < 1 || ref.band > r.bands.length || ref.band === r.areaBand) throw new Error(`${l.id}: invalid numeric input band.`);
      }
      const first = c.rasters.find(r=>r.id===l.inputs[0].raster)!;
      outputCells += first.grid.width * first.grid.height;
    }
    const inputCells = c.rasters.filter(r=>requiredRasters.has(r.id)).reduce((sum,r)=>sum+r.grid.width*r.grid.height*r.bands.length,0);
    if (inputCells + outputCells > 40_000_000) throw new Error(`${m.id}: input and output arrays exceed the browser memory budget. Crop the package.`);
  }
  return c;
}

export async function readNumericRaster(buffer: ArrayBuffer, asset: RasterAsset): Promise<NumericRaster> {
  if (buffer.byteLength > 100_000_000) throw new Error("Crop numeric inputs to at most 100 MB each.");
  if (await digest(buffer) !== asset.sha256) throw new Error(`${asset.file}: checksum mismatch. Use the files belonging to this catalog.`);
  const tiff = await fromArrayBuffer(buffer), image = await tiff.getImage();
  const dir = image.getFileDirectory(), keys = image.getGeoKeys() ?? {}, g = asset.grid;
  const crs = Number(keys.ProjectedCSTypeGeoKey ?? keys.GeographicTypeGeoKey);
  if (image.getWidth() !== g.width || image.getHeight() !== g.height || image.getSamplesPerPixel() !== asset.bands.length || crs !== g.crs || keys.GTRasterTypeGeoKey === 2 || dir.getValue("ModelTransformation")) throw new Error(`${asset.file}: GeoTIFF grid does not match its catalog.`);
  const [x, y] = image.getOrigin(), [dx, dy] = image.getResolution();
  if (dx <= 0 || dy >= 0 || Math.abs(x - g.left) > g.dx * 1e-7 || Math.abs(y - g.top) > g.dy * 1e-7 || Math.abs(dx - g.dx) > g.dx * 1e-7 || Math.abs(dy + g.dy) > g.dy * 1e-7) throw new Error(`${asset.file}: north-up pixel-area georeferencing required.`);
  const nodata = image.getGDALNoData();
  const raw = await image.readRasters({ interleave: false });
  const bands = Array.from({ length: asset.bands.length }, (_, b) => Float32Array.from(raw[b] as ArrayLike<number>, value => !Number.isFinite(value) || (nodata !== null && value === nodata) ? NaN : value));
  return { grid: g, bands, asset };
}

export function numericGeoTiff(layer: LayerResult): ArrayBuffer {
  const g = layer.grid;
  return writeArrayBuffer(layer.values, { width: g.width, height: g.height, BitsPerSample: [32], SampleFormat: [3], SamplesPerPixel: 1,
    ModelPixelScale: [g.dx, g.dy, 0], ModelTiepoint: [0, 0, 0, g.left, g.top, 0],
    GTModelTypeGeoKey: g.crs === 4326 ? 2 : 1, GTRasterTypeGeoKey: 1,
    ...(g.crs === 4326 ? { GeographicTypeGeoKey: 4326, GeogAngularUnitsGeoKey: 9102 } : { ProjectedCSTypeGeoKey: g.crs, ProjLinearUnitsGeoKey: 9001 }),
    GDAL_NODATA: "nan\0", PhotometricInterpretation: 1,
  });
}
