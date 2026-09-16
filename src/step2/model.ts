export const MODULE_IDS = ["lulc", "fragmentation", "groundwater", "drought", "climate", "flood", "degradation"] as const;
export type ModuleId = typeof MODULE_IDS[number];
export type NumericGrid = { width: number; height: number; crs: number; left: number; top: number; dx: number; dy: number };
export type BandRef = { raster: string; band: number };
export type Source = { id: string; name: string; url: string; version: string; licence: string; description: string };
export type RasterAsset = {
  id: string; file: string; sha256: string; source: string; grid: NumericGrid;
  bands: string[]; areaBand: number; nativeResolution: string; processing: string | string[];
};
export type Category = { value: number; label: string; color: string };
export type LayerSpec = {
  id: string; title: string; unit: string; period: string;
  operation: "identity" | "difference" | "percent-change" | "one-out-all-out";
  inputs: BandRef[];
  palette: "sequential" | "diverging" | "water" | "health";
  domain?: [number, number]; categories?: Category[];
  thresholds?: { label: string; min?: number; max?: number }[];
  interpretation: string;
};
export type SeriesPoint = { date: string; value: number | null; coveragePct?: number };
export type ModuleSpec = {
  id: ModuleId; title: string; question: string; status: "available" | "needs-data";
  method: string[]; limitations: string[]; fieldChecks: string[];
  sources: string[]; layers: LayerSpec[]; series?: { title: string; unit: string; points: SeriesPoint[] }[];
  missing?: string[];
};
export type Catalog = {
  schema: "nbs-step2/v1"; version: string; preparedAt: string;
  studyArea: { name: string; areaKm2: number; boundary: string; sha256: string };
  sources: Source[]; rasters: RasterAsset[]; modules: ModuleSpec[];
  protection: { status: "not-assessed" | "assessed"; detail: string; source?: string };
  review: { status: "pending" | "reviewed"; detail: string };
};
export type NumericRaster = { grid: NumericGrid; bands: Float32Array[]; asset: RasterAsset };
export type LayerResult = {
  spec: LayerSpec; grid: NumericGrid; values: Float32Array; areas: Float32Array;
  stats: { validAreaKm2: number; eligibleAreaKm2: number; missingAreaKm2: number; coveragePct: number;
    mean: number | null; min: number | null; max: number | null; cells: number;
    classes: { label: string; areaKm2: number; percent: number | null }[] };
};
export type ModuleResult = { module: ModuleSpec; layers: LayerResult[]; manifest: Record<string, unknown> };
export type MapOverlay = { url: string; coordinates: [number, number][]; label: string };
