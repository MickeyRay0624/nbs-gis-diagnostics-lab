import proj4 from "proj4";
import "../analysis/io";
import type { VectorCollection } from "../analysis/model";
import type { LayerResult, MapOverlay } from "./model";

export const palettes = {
  sequential: ["#f2ecd6", "#d9ae53", "#934b39"],
  diverging: ["#24678d", "#f2f0e6", "#b64a36"],
  water: ["#e1f2f2", "#429bb7", "#183a77"],
  health: ["#b94e39", "#efcf70", "#2c7951"],
};
const rgb = (hex: string) => [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16));
type DisplayLayer = Pick<LayerResult, "spec" | "grid" | "stats"> & { values: ArrayLike<number>; areas?: ArrayLike<number> };
export function domain(layer: Pick<LayerResult, "spec" | "stats">): [number, number] {
  if (layer.spec.domain) return layer.spec.domain;
  if (layer.spec.palette === "diverging") { const v = Math.max(Math.abs(layer.stats.min ?? 0), Math.abs(layer.stats.max ?? 0), 1e-6); return [-v, v]; }
  const lo = layer.stats.min ?? 0, hi = layer.stats.max ?? 1;
  return [lo, hi === lo ? lo + 1 : hi];
}
export function color(value: number, layer: Pick<LayerResult, "spec" | "stats">): number[] {
  if (!Number.isFinite(value)) return [0, 0, 0, 0];
  if (layer.spec.categories) { const c = layer.spec.categories.find(c => c.value === value); return c ? [...rgb(c.color), 255] : [0, 0, 0, 0]; }
  const [min, max] = domain(layer), fraction = Math.max(0, Math.min(1, (value - min) / (max - min))) * 2;
  const colors = palettes[layer.spec.palette].map(rgb), n = Math.min(1, Math.floor(fraction)), t = fraction - n;
  return [...colors[n].map((v, i) => Math.round(v + (colors[n + 1][i] - v) * t)), 255];
}

// Render into Web Mercator before placing the image on MapLibre. Merely using
// geographic corner coordinates would stretch geographic rows non-linearly.
export function rasterImage(layer: DisplayLayer, aoi?: VectorCollection | null): { canvas: HTMLCanvasElement; overlay: MapOverlay } {
  const g = layer.grid, source = `EPSG:${g.crs}`;
  const project = proj4(source, "EPSG:3857"), unproject = proj4("EPSG:3857", source);
  const [left, top] = project.forward([g.left, g.top]), [right, bottom] = project.forward([g.left + g.width * g.dx, g.top - g.height * g.dy]);
  const canvas = document.createElement("canvas");
  const ratio = (right - left) / (top - bottom);
  canvas.width = Math.max(1, Math.min(720, Math.round(540 * ratio))); canvas.height = Math.max(1, Math.min(900, Math.round(canvas.width / ratio)));
  const context = canvas.getContext("2d")!, pixels = context.createImageData(canvas.width, canvas.height);
  for (let y = 0; y < canvas.height; y++) for (let x = 0; x < canvas.width; x++) {
    const [sx, sy] = unproject.forward([left + (x + .5) / canvas.width * (right - left), top - (y + .5) / canvas.height * (top - bottom)]);
    const col = Math.floor((sx - g.left) / g.dx), row = Math.floor((g.top - sy) / g.dy), i = row * g.width + col;
    if (col >= 0 && col < g.width && row >= 0 && row < g.height && (!layer.areas || layer.areas[i] > 0)) pixels.data.set(color(layer.values[i], layer), (y * canvas.width + x) * 4);
  }
  context.putImageData(pixels, 0, 0);
  if (aoi) {
    context.globalCompositeOperation = "destination-in"; context.beginPath();
    for (const f of aoi.features) {
      const polygons = f.geometry.type === "Polygon" ? [f.geometry.coordinates as number[][][]] : f.geometry.coordinates as number[][][][];
      for (const p of polygons) for (const ring of p) ring.forEach((point, i) => {
        const [mx, my] = proj4("EPSG:4326", "EPSG:3857", point), x = (mx - left) / (right - left) * canvas.width, y = (top - my) / (top - bottom) * canvas.height;
        if (i === 0) context.moveTo(x, y); else context.lineTo(x, y);
      });
    }
    context.fill("evenodd"); context.globalCompositeOperation = "source-over";
  }
  const ll = (x: number, y: number) => proj4("EPSG:3857", "EPSG:4326", [x, y]) as [number, number];
  return { canvas, overlay: { url: canvas.toDataURL("image/png"), coordinates: [ll(left, top), ll(right, top), ll(right, bottom), ll(left, bottom)], label: layer.spec.title } };
}

export function mapPng(layer: LayerResult, map: HTMLCanvasElement, attribution: string, studyArea: string): Promise<Blob> {
  const out = document.createElement("canvas"); out.width = 1000;
  const rows = layer.spec.categories ? Math.ceil(layer.spec.categories.length / 2) : 2;
  out.height = map.height + 320 + rows * 25;
  const ctx = out.getContext("2d")!; ctx.fillStyle = "#fffefa"; ctx.fillRect(0, 0, out.width, out.height);
  const wrap = (text: string, y: number, size = 14, bold = false) => {
    ctx.font = `${bold ? "bold " : ""}${size}px sans-serif`;
    let line = "";
    for (const word of text.split(" ")) {
      if (line && ctx.measureText(`${line} ${word}`).width > 940) { ctx.fillText(line, 30, y); y += size + 7; line = word; }
      else line += `${line ? " " : ""}${word}`;
    }
    ctx.fillText(line, 30, y); return y + size + 7;
  };
  ctx.fillStyle = "#102d2c";
  let y = wrap(layer.spec.title, 35, 21, true);
  y = wrap(`${layer.spec.period} · ${layer.spec.unit} · EPSG:${layer.grid.crs} source grid`, y, 13);
  ctx.drawImage(map, (out.width - map.width) / 2, y + 10); y += map.height + 35;
  ctx.font = "14px sans-serif";
  if (layer.spec.categories) {
    layer.spec.categories.forEach((c, i) => {
      const x = 30 + i % 2 * 475, rowY = y + Math.floor(i / 2) * 25;
      ctx.fillStyle = c.color; ctx.fillRect(x, rowY, 16, 16); ctx.fillStyle = "#102d2c"; ctx.fillText(c.label, x + 23, rowY + 13, 440);
    });
    y += rows * 25;
  } else {
    const gradient = ctx.createLinearGradient(30, 0, 500, 0); palettes[layer.spec.palette].forEach((c, i) => gradient.addColorStop(i / 2, c)); ctx.fillStyle = gradient; ctx.fillRect(30, y, 470, 18);
    ctx.fillStyle = "#102d2c"; const d = domain(layer); ctx.fillText(d[0].toFixed(2), 30, y + 39); ctx.fillText(`${d[1].toFixed(2)} ${layer.spec.unit}`, 430, y + 39); y += 55;
  }
  ctx.fillStyle = "#647572";
  y = wrap(`${studyArea} · transparent = missing / excluded · coverage ${layer.stats.coveragePct.toFixed(1)}% of eligible area`, y + 20, 13);
  y = wrap(attribution, y, 12);
  wrap("Technical screening · expert review pending. See the run manifest for methods and limitations.", y, 13);
  return new Promise((resolve, reject) => out.toBlob(blob => blob ? resolve(blob) : reject(new Error("PNG export failed.")), "image/png"));
}
