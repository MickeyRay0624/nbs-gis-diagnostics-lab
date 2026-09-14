import { fromArrayBuffer, writeArrayBuffer } from "geotiff";
import proj4 from "proj4";
import shp from "shpjs";
import type { Grid, Raster, VectorCollection } from "./model";

proj4.defs("EPSG:6933", "+proj=cea +lat_ts=30 +lon_0=0 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs");
for (let zone = 1; zone <= 60; zone++) {
  proj4.defs(`EPSG:${32600 + zone}`, `+proj=utm +zone=${zone} +datum=WGS84 +units=m +no_defs`);
  proj4.defs(`EPSG:${32700 + zone}`, `+proj=utm +zone=${zone} +south +datum=WGS84 +units=m +no_defs`);
}
export const MAX_PIXELS = 8_000_000;

export async function sha256(buffer: ArrayBuffer) {
  const hash = await crypto.subtle.digest("SHA-256", buffer);
  return Array.from(new Uint8Array(hash), v => v.toString(16).padStart(2, "0")).join("");
}

export async function readRaster(buffer: ArrayBuffer, year: number, name: string): Promise<Raster> {
  const tiff = await fromArrayBuffer(buffer), image = await tiff.getImage();
  const width = image.getWidth(), height = image.getHeight();
  if (width * height > 25_000_000) throw new Error(`${name}: crop the input to your study area first (maximum 25 million input pixels).`);
  if (image.getSamplesPerPixel() !== 1) throw new Error(`${name}: use a single-band categorical GeoTIFF, not an RGB image.`);
  if (image.fileDirectory.hasTag("ModelTransformation")) throw new Error(`${name}: rotated grids are not supported; export a north-up GeoTIFF.`);
  const keys = image.getGeoKeys();
  const epsg = keys?.ProjectedCSTypeGeoKey || keys?.GeographicTypeGeoKey;
  const crs = `EPSG:${epsg}`;
  if (!proj4.defs(crs)) throw new Error(`${name}: CRS not supported. Use EPSG:6933, WGS84, Web Mercator or WGS84 UTM.`);
  if (keys?.GTRasterTypeGeoKey === 2) throw new Error(`${name}: export a PixelIsArea raster before analysis.`);
  const [left, top] = image.getOrigin(), [rx, ry] = image.getResolution();
  if (![left, top, rx, ry].every(Number.isFinite) || rx <= 0 || ry >= 0) throw new Error(`${name}: invalid north-up georeferencing.`);
  const input = await image.readRasters({ samples: [0], interleave: true });
  const nodata = image.getGDALNoData();
  const data = new Uint16Array(input.length);
  for (let i = 0; i < input.length; i++) {
    const value = Number(input[i]);
    if (!Number.isFinite(value) || value === nodata || value === 0) continue;
    if (!Number.isInteger(value) || value < 1 || value > 65534) throw new Error(`${name}: expected integer land-cover codes 1–65534; 0 is NoData.`);
    data[i] = value;
  }
  // Preserve both source resolutions until sampling into the square analysis grid.
  const raster: Raster & { yCell: number } = { year, name, data, grid: { width, height, cell: rx, left, top, crs }, yCell: -ry, sha256: await sha256(buffer) };
  return raster;
}

export function validateVector(value: unknown): VectorCollection {
  const doc = value as VectorCollection;
  if (doc?.type !== "FeatureCollection" || !Array.isArray(doc.features) || !doc.features.length)
    throw new Error("Provide a non-empty polygon GeoJSON FeatureCollection or zipped Shapefile.");
  for (const f of doc.features) {
    if (!f.geometry || !["Polygon", "MultiPolygon"].includes(f.geometry.type)) throw new Error("Only Polygon and MultiPolygon features are supported.");
    const polygons = f.geometry.type === "Polygon" ? [f.geometry.coordinates as number[][][]] : f.geometry.coordinates as number[][][][];
    for (const polygon of polygons) {
      if (!polygon.length) throw new Error("Empty polygon.");
      for (const ring of polygon) {
        if (ring.length < 4 || ring[0][0] !== ring.at(-1)![0] || ring[0][1] !== ring.at(-1)![1]) throw new Error("Polygon rings must be closed with at least four coordinates.");
        for (const p of ring) if (!p || !Number.isFinite(p[0]) || !Number.isFinite(p[1]) || Math.abs(p[0]) > 180 || Math.abs(p[1]) > 85) throw new Error("Use WGS84 coordinates between 85°S and 85°N.");
      }
    }
  }
  return doc;
}

export async function readVector(file: File): Promise<VectorCollection> {
  if (file.size > 25_000_000) throw new Error("Vector upload limit is 25 MB. Simplify or crop first.");
  let doc: unknown;
  if (file.name.toLowerCase().endsWith(".zip")) {
    doc = await shp(await file.arrayBuffer());
    if (Array.isArray(doc)) {
      if (doc.length !== 1) throw new Error("Upload a ZIP containing exactly one Shapefile layer with .shp, .dbf and .prj.");
      doc = doc[0];
    }
  } else doc = JSON.parse(await file.text());
  return validateVector(doc);
}

export function vectorPolygons(doc: VectorCollection, toCrs: string): number[][][][] {
  return doc.features.flatMap(f => {
    const polygons = f.geometry.type === "Polygon" ? [f.geometry.coordinates as number[][][]] : f.geometry.coordinates as number[][][][];
    return polygons.map(p => p.map(r => r.map(c => proj4("EPSG:4326", toCrs, c))));
  });
}

export function makeGrid(first: Raster, cell: number, aoi?: VectorCollection): Grid {
  if (!Number.isFinite(cell) || cell < 10 || cell > 1000) throw new Error("Analysis resolution must be between 10 and 1000 metres.");
  let coordinates: number[][];
  if (aoi) coordinates = vectorPolygons(aoi, "EPSG:6933").flat(2);
  else {
    const g = first.grid, yCell = (first as Raster & { yCell?: number }).yCell ?? g.cell;
    // Densify the source perimeter to include the bounds of projected edges.
    coordinates = [];
    for (let t = 0; t <= 20; t++) for (const p of [[g.left + g.width * g.cell * t / 20, g.top], [g.left + g.width * g.cell * t / 20, g.top - g.height * yCell], [g.left, g.top - g.height * yCell * t / 20], [g.left + g.width * g.cell, g.top - g.height * yCell * t / 20]])
      coordinates.push(proj4(g.crs, "EPSG:6933", p));
  }
  let left = Infinity, right = -Infinity, top = -Infinity, bottom = Infinity;
  for (const [x, y] of coordinates) { left = Math.min(left, x); right = Math.max(right, x); top = Math.max(top, y); bottom = Math.min(bottom, y); }
  left = Math.floor(left / cell) * cell; right = Math.ceil(right / cell) * cell;
  top = Math.ceil(top / cell) * cell; bottom = Math.floor(bottom / cell) * cell;
  const width = Math.round((right - left) / cell), height = Math.round((top - bottom) / cell);
  if (!Number.isFinite(width * height) || width < 1 || height < 1 || width * height > MAX_PIXELS)
    throw new Error(`The analysis grid exceeds ${MAX_PIXELS.toLocaleString()} pixels. Increase the resolution in metres or use a smaller AOI.`);
  return { width, height, left, top, cell, crs: "EPSG:6933" };
}

export function rasterizeVector(doc: VectorCollection, grid: Grid, target?: Uint8Array, value = 1): Uint8Array {
  const mask = target ?? new Uint8Array(grid.width * grid.height);
  for (const polygon of vectorPolygons(doc, grid.crs)) {
    let minY = Infinity, maxY = -Infinity;
    for (const ring of polygon) for (const p of ring) { minY = Math.min(minY, p[1]); maxY = Math.max(maxY, p[1]); }
    const start = Math.max(0, Math.floor((grid.top - maxY) / grid.cell));
    const end = Math.min(grid.height - 1, Math.ceil((grid.top - minY) / grid.cell));
    for (let row = start; row <= end; row++) {
      const y = grid.top - (row + .5) * grid.cell, xs: number[] = [];
      for (const ring of polygon) for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
        const a = ring[i], b = ring[j];
        if ((a[1] > y) !== (b[1] > y)) xs.push(a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1]));
      }
      xs.sort((a, b) => a - b);
      for (let i = 0; i + 1 < xs.length; i += 2) {
        const lo = Math.max(0, Math.ceil((xs[i] - grid.left) / grid.cell - .5));
        const hi = Math.min(grid.width, Math.ceil((xs[i + 1] - grid.left) / grid.cell - .5));
        if (hi > lo) mask.fill(value, row * grid.width + lo, row * grid.width + hi);
      }
    }
  }
  return mask;
}

export function alignRaster(source: Raster, grid: Grid, mask?: Uint8Array): Raster {
  const g = source.grid, sy = (source as Raster & { yCell?: number }).yCell ?? g.cell;
  const convert = proj4(grid.crs, g.crs), data = new Uint16Array(grid.width * grid.height);
  const sameCrs = grid.crs === g.crs;
  for (let row = 0; row < grid.height; row++) for (let col = 0; col < grid.width; col++) {
    const i = row * grid.width + col;
    if (mask && !mask[i]) continue;
    const point = [grid.left + (col + .5) * grid.cell, grid.top - (row + .5) * grid.cell];
    const [x, y] = sameCrs ? point : convert.forward(point);
    const sx = Math.floor((x - g.left) / g.cell), ry = Math.floor((g.top - y) / sy);
    if (sx >= 0 && sx < g.width && ry >= 0 && ry < g.height) data[i] = source.data[ry * g.width + sx];
  }
  return { ...source, data, grid };
}

export function geoTiff(data: Uint16Array | Uint8Array, grid: Grid, nodata: number) {
  return writeArrayBuffer(data, { width: grid.width, height: grid.height,
    ModelPixelScale: [grid.cell, grid.cell, 0], ModelTiepoint: [0, 0, 0, grid.left, grid.top, 0],
    GTModelTypeGeoKey: 1, GTRasterTypeGeoKey: 1, ProjectedCSTypeGeoKey: 6933,
    GDAL_NODATA: String(nodata),
    BitsPerSample: [data instanceof Uint16Array ? 16 : 8], SampleFormat: [1], SamplesPerPixel: 1,
    PhotometricInterpretation: 1 });
}
