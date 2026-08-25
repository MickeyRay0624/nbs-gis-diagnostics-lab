import {
  collectionBounds,
  geometryAreaSqKm,
  geometryRingsAreClosed,
  geometryVertexCount,
} from "./geo";
import type { AoiFeatureCollection } from "./types";

export const REQUIRED_DATASETS = [
  { id: "lulc-2002", name: "LULC raster — 2002", format: "GeoTIFF / COG", purpose: "Baseline land-cover surface" },
  { id: "lulc-2012", name: "LULC raster — 2012", format: "GeoTIFF / COG", purpose: "Intermediate change period" },
  { id: "lulc-2022", name: "LULC raster — 2022", format: "GeoTIFF / COG", purpose: "Latest comparison surface" },
  { id: "crosswalk", name: "Class crosswalk", format: "CSV / XLSX", purpose: "Map source classes to the project taxonomy" },
  { id: "method", name: "Method specification", format: "Python / R / GEE / written rules", purpose: "Fix reproducible processing decisions" },
  { id: "reference", name: "Reference outputs", format: "Maps / tables / QA thresholds", purpose: "Support numerical regression and expert acceptance" },
] as const;

export interface QaCheck {
  id: string;
  label: string;
  detail: string;
  status: "pass" | "warning";
}

export interface AoiPreflightResult {
  runId: string;
  createdAt: string;
  status: "aoi-preflight-complete";
  areaSqKm: number;
  vertexCount: number;
  bounds: { west: number; south: number; east: number; north: number };
  qa: QaCheck[];
  manifest: Record<string, unknown>;
}

function round(value: number, places: number) {
  const factor = 10 ** places;
  return Math.round(value * factor) / factor;
}

export function runAoiPreflight(
  collection: AoiFeatureCollection,
  runAt = new Date(),
): AoiPreflightResult {
  const feature = collection.features[0];
  if (!feature) throw new Error("The AOI collection does not contain a feature");

  const bounds = collectionBounds(collection);
  const areaSqKm = geometryAreaSqKm(feature.geometry);
  const vertexCount = geometryVertexCount(feature.geometry);
  const ringsClosed = geometryRingsAreClosed(feature.geometry);
  const coordinatesPlausible =
    bounds.west >= -180 &&
    bounds.east <= 180 &&
    bounds.south >= -90 &&
    bounds.north <= 90 &&
    bounds.west < bounds.east &&
    bounds.south < bounds.north;
  const createdAt = runAt.toISOString();
  const runId = `NBS-AOI-${createdAt.slice(0, 10).replaceAll("-", "")}-${createdAt
    .slice(11, 19)
    .replaceAll(":", "")}`;

  const qa: QaCheck[] = [
    {
      id: "feature-count",
      label: "Feature count",
      detail: `${collection.features.length} AOI feature found`,
      status: collection.features.length === 1 ? "pass" : "warning",
    },
    {
      id: "geometry-type",
      label: "Geometry type",
      detail: `${feature.geometry.type} is supported`,
      status: "pass",
    },
    {
      id: "ring-closure",
      label: "Ring closure",
      detail: ringsClosed ? "All polygon rings are closed" : "One or more polygon rings are open",
      status: ringsClosed ? "pass" : "warning",
    },
    {
      id: "coordinate-domain",
      label: "Coordinate domain",
      detail: coordinatesPlausible ? "Longitude and latitude ranges are valid" : "Coordinates fall outside CRS84 bounds",
      status: coordinatesPlausible ? "pass" : "warning",
    },
    {
      id: "provenance",
      label: "Provenance",
      detail: `${feature.properties.boundarySource} · ${feature.properties.boundaryYear}`,
      status: feature.properties.sourceURL ? "pass" : "warning",
    },
  ];

  const roundedBounds = {
    west: round(bounds.west, 5),
    south: round(bounds.south, 5),
    east: round(bounds.east, 5),
    north: round(bounds.north, 5),
  };

  const manifest = {
    schema: "nbs-diagnostics-run-manifest/v0.2",
    run_id: runId,
    created_at: createdAt,
    status: "aoi-preflight-complete",
    study_area: {
      name: "Ganjam District",
      country: "India",
      administrative_level: "ADM2",
      boundary_year: feature.properties.boundaryYear,
      source: feature.properties.boundarySource,
      license: feature.properties.boundaryLicense,
      geometry_type: feature.geometry.type,
      vertex_count: vertexCount,
      area_sq_km_approx: round(areaSqKm, 2),
      bounds: roundedBounds,
    },
    analysis: {
      module: "lulc-change",
      requested_periods: [2002, 2012, 2022],
      execution_state: "blocked-pending-raster-inputs",
    },
    qa,
    missing_inputs: REQUIRED_DATASETS.map((item) => item.id),
    limitations: [
      "AOI validation only",
      "No land-cover raster is connected",
      "No land-cover change result has been calculated",
    ],
  };

  return {
    runId,
    createdAt,
    status: "aoi-preflight-complete",
    areaSqKm: round(areaSqKm, 2),
    vertexCount,
    bounds: roundedBounds,
    qa,
    manifest,
  };
}
