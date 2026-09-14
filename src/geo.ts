import type { AoiGeometry, Position } from "./types";
import type { VectorCollection } from "./analysis/model";

const EARTH_RADIUS_M = 6_378_137;

function degreesToRadians(value: number) {
  return (value * Math.PI) / 180;
}

function ringAreaSqM(ring: Position[]) {
  if (ring.length < 3) return 0;
  let total = 0;
  for (let index = 0; index < ring.length; index += 1) {
    const current = ring[index];
    const next = ring[(index + 1) % ring.length];
    total +=
      degreesToRadians(next[0] - current[0]) *
      (2 + Math.sin(degreesToRadians(current[1])) + Math.sin(degreesToRadians(next[1])));
  }
  return Math.abs((total * EARTH_RADIUS_M * EARTH_RADIUS_M) / 2);
}

function polygonAreaSqM(rings: Position[][]) {
  if (!rings.length) return 0;
  const holes = rings.slice(1).reduce((sum, ring) => sum + ringAreaSqM(ring), 0);
  return Math.max(0, ringAreaSqM(rings[0]) - holes);
}

export function geometryAreaSqKm(geometry: AoiGeometry) {
  const squareMetres =
    geometry.type === "Polygon"
      ? polygonAreaSqM(geometry.coordinates)
      : geometry.coordinates.reduce((sum, polygon) => sum + polygonAreaSqM(polygon), 0);
  return squareMetres / 1_000_000;
}

export function geometryVertexCount(geometry: AoiGeometry) {
  if (geometry.type === "Polygon") {
    return geometry.coordinates.reduce((sum, ring) => sum + ring.length, 0);
  }
  return geometry.coordinates.reduce(
    (total, polygon) => total + polygon.reduce((sum, ring) => sum + ring.length, 0),
    0,
  );
}

export function collectionBounds(collection: { features: { geometry: VectorCollection["features"][number]["geometry"] }[] }) {
  let west = Number.POSITIVE_INFINITY;
  let south = Number.POSITIVE_INFINITY;
  let east = Number.NEGATIVE_INFINITY;
  let north = Number.NEGATIVE_INFINITY;

  const visit = (position: number[]) => {
    west = Math.min(west, position[0]);
    south = Math.min(south, position[1]);
    east = Math.max(east, position[0]);
    north = Math.max(north, position[1]);
  };

  collection.features.forEach((feature) => {
    if (feature.geometry.type === "Polygon") {
      (feature.geometry.coordinates as number[][][]).forEach((ring) => ring.forEach(visit));
    } else {
      (feature.geometry.coordinates as number[][][][]).forEach((polygon) =>
        polygon.forEach((ring) => ring.forEach(visit)),
      );
    }
  });

  return { west, south, east, north };
}

export function geometryRingsAreClosed(geometry: AoiGeometry) {
  const rings =
    geometry.type === "Polygon" ? geometry.coordinates : geometry.coordinates.flat();
  return rings.every((ring) => {
    if (ring.length < 4) return false;
    const first = ring[0];
    const last = ring[ring.length - 1];
    return first[0] === last[0] && first[1] === last[1];
  });
}
