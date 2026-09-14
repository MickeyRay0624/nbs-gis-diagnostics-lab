export interface LandClass { code: number; name: string; color: string }
export interface CrosswalkRow extends LandClass { source: number }
export interface Grid { width: number; height: number; cell: number; left: number; top: number; crs: string }
export interface Raster { year: number; name: string; data: Uint16Array; grid: Grid; sha256?: string }
export interface Metrics {
  stratum: string; landscape_ha: number; forest_ha: number; PLAND: number;
  patch_ha: number; edge_ha: number; core_ha: number; clearing_ha: number;
  core_pct: number; NP: number; TE_m: number; ED: number; MPS_ha: number;
  MPE: number; MSI: number; AWMSI: number; LPI: number;
  largest_patch_ha: number; clearings_intersecting: number;
}
export interface FragmentResult { data: Uint8Array; metrics: Metrics[]; qa: Record<string, number | boolean> }
export interface PeriodResult {
  year: number; data: Uint16Array; counts: Record<number, number>; valid: number;
  fragmentation?: FragmentResult;
}
export interface Transition {
  start: number; end: number; valid: number; changed: number;
  matrix: number[][]; codes: number[]; data: Uint8Array;
  gains: { code: number; gain: number; loss: number; net: number }[];
}
export interface Result {
  grid: Grid; classes: LandClass[]; periods: PeriodResult[]; transitions: Transition[];
  manifest: Record<string, unknown>;
}
export interface VectorCollection {
  type: "FeatureCollection";
  features: { type: "Feature"; geometry: { type: "Polygon" | "MultiPolygon"; coordinates: number[][][] | number[][][][] }; properties: Record<string, unknown> | null }[];
}
export interface RunRequest {
  sources: { year: number; name: string; url?: string; buffer?: ArrayBuffer; expectedSha256?: string }[];
  crosswalk: CrosswalkRow[]; forestCodes: number[]; edge: number; countBoundary: boolean;
  module: "both" | "lulc" | "fragmentation"; cell: number; dataset: string;
  aoi?: VectorCollection; protectedAreas?: VectorCollection; oecm?: VectorCollection;
  provenance: Record<string, unknown>;
}
export const FRAGMENT_CLASSES: LandClass[] = [
  { code: 0, name: "Non-forest", color: "#efede2" },
  { code: 4, name: "Core", color: "#286845" },
  { code: 2, name: "Edge", color: "#e6ab36" },
  { code: 1, name: "Patch", color: "#d64233" },
  { code: 3, name: "Internal clearing", color: "#b752a3" },
];
