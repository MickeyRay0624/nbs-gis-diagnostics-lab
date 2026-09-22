import { fromArrayBuffer } from "geotiff";
import { digest } from "../step2/io";
import type { VectorCollection } from "../analysis/model";
import type { LayerResult, NumericGrid, SeriesPoint } from "../step2/model";

export type WaterRequest = { mode: "sample" | "custom"; name: string; start: string; end: string; bbox: number[]; boundary?: VectorCollection | null };
export type WaterJob = { id: string; request: WaterRequest; status: "queued" | "running" | "succeeded" | "failed" | "cancelled" | "expired"; stage: string; created: number; updated: number; error: string | null; cancel_requested: boolean };
export type Capabilities = { analyst: string; worker_online: boolean; sample_ready: boolean; custom_enabled: boolean; max_area_km2: number; max_days: number; retention_days: number; sample: Omit<WaterRequest, "mode"> };
export type WaterAsset = { file: string; bytes: number; sha256: string; media_type: string };
export type WaterLayer = { id: string; variable: string; period: string; file: string; band: number; title: string; unit: string; palette: "water" | "health"; stats: LayerResult["stats"] };
export type WaterResult = { schema: "nbs-water/v1"; name: string; model: string; prepared_at: string; scope: string; notes: string[]; grid: NumericGrid; boundary: VectorCollection; periods: { id: string; label: string; start: string; end: string; days: number }[]; layers: WaterLayer[]; series: { id: string; title: string; unit: string; points: SeriesPoint[] }[]; assets: WaterAsset[]; validation: { status: "passed"; checks: number }; source_url: string | null };

export function serviceUrl(value: string) {
  const url = new URL(value, typeof location === "undefined" ? "http://localhost" : location.href);
  if (url.username || url.password || url.search || url.hash || (url.protocol !== "https:" && !(url.protocol === "http:" && ["localhost", "127.0.0.1"].includes(url.hostname)))) throw new Error("The compute service must use HTTPS (HTTP is allowed only for localhost).");
  return url.href.replace(/\/$/, "");
}

const openingSessions = new Map<string, Promise<void>>();
export function prepareComputeSession(base: string, legacyCode = "") {
  const endpoint = serviceUrl(base);
  const current = openingSessions.get(endpoint);
  if (current) return current;
  const pending = new WaterClient(endpoint, legacyCode).request<{ready:boolean}>("/session", {
    method:"POST", headers:{"Content-Type":"application/json"}, body:"{}",
  }).then(result => { if (!result.ready) throw new Error("Could not prepare your workspace. Please retry."); })
    .finally(() => openingSessions.delete(endpoint));
  openingSessions.set(endpoint, pending);
  return pending;
}

export class WaterClient {
  readonly base: string;
  constructor(base: string, private code = "") { this.base = serviceUrl(base); }
  async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const response = await fetch(this.base + path, { ...options, credentials:"include", headers: { ...options.headers, ...(this.code ? {Authorization: `Bearer ${this.code}`} : {}) } });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(typeof body.detail === "string" ? body.detail : Array.isArray(body.detail) ? body.detail.map((e: { msg: string }) => e.msg).join("; ") : `The compute service returned ${response.status}. Please retry.`);
    }
    return response.json() as Promise<T>;
  }
  capabilities(signal?: AbortSignal) { return this.request<Capabilities>("/capabilities", { signal }); }
  jobs(signal?: AbortSignal) { return this.request<WaterJob[]>("/jobs", { signal }); }
  submit(payload: WaterRequest, key: string) { return this.request<WaterJob>("/jobs", { method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": key }, body: JSON.stringify(payload) }); }
  cancel(id: string) { return this.request<WaterJob>(`/jobs/${id}/cancel`, { method: "POST" }); }
  result(id: string, signal?: AbortSignal) { return this.request<WaterResult>(`/jobs/${id}/result`, { signal }); }
  async asset(id: string, asset: WaterAsset, signal?: AbortSignal) {
    if (!/^[a-zA-Z0-9_.-]+$/.test(asset.file) || asset.file.includes("..") || asset.bytes > 300_000_000) throw new Error("Invalid or oversized result file.");
    const response = await fetch(`${this.base}/jobs/${id}/assets/${encodeURIComponent(asset.file)}`, { credentials:"include", headers: this.code ? {Authorization: `Bearer ${this.code}`} : {}, signal });
    if (!response.ok) throw new Error("The result file is unavailable. Reconnect to the service and retry.");
    const bytes = await response.arrayBuffer();
    if (bytes.byteLength !== asset.bytes || await digest(bytes) !== asset.sha256) throw new Error("The result checksum did not match. Download the file again.");
    return bytes;
  }
}

export async function readWaterLayer(bytes: ArrayBuffer, result: WaterResult, layer: WaterLayer): Promise<LayerResult> {
  const tiff = await fromArrayBuffer(bytes), image = await tiff.getImage(), g = result.grid;
  const origin = image.getOrigin(), resolution = image.getResolution();
  if (image.getGeoKeys()?.GeographicTypeGeoKey !== 4326 || g.crs !== 4326 || image.getWidth() !== g.width || image.getHeight() !== g.height || g.width * g.height > 400_000 || image.getSamplesPerPixel() !== 9 || layer.band < 1 || layer.band > 8 ||
      Math.abs(origin[0] - g.left) > 1e-8 || Math.abs(origin[1] - g.top) > 1e-8 || Math.abs(resolution[0] - g.dx) > 1e-8 || Math.abs(resolution[1] + g.dy) > 1e-8) throw new Error("The result raster and map grid do not match.");
  const raw = await image.readRasters({ samples: [layer.band - 1, 8] }), nodata = image.getGDALNoData();
  const values = Float32Array.from(raw[0] as ArrayLike<number>, n => Number.isFinite(n) && n !== nodata ? n : NaN);
  const areas = Float32Array.from(raw[1] as ArrayLike<number>);
  const period = result.periods.find(p => p.id === layer.period)!;
  return { grid: g, values, areas, stats: layer.stats, spec: { id: layer.id, title: layer.title, unit: layer.unit, period: `${period.start}–${period.end} (${period.days} days)`, palette: layer.palette, operation: "identity", inputs: [], interpretation: result.notes.join(" "), ...(layer.variable === "se_root" ? { domain: [0, 1] as [number, number] } : {}) } };
}
