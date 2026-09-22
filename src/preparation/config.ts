import proj4 from "proj4";
import { validateVector } from "../analysis/io";
import type { VectorCollection } from "../analysis/model";

export const PREP_MODULES = [
  { id: "flood", title: "River flood hazard", source: "JRC / CEMS-GloFAS", note: "Open data · no registration required" },
  { id: "degradation", title: "Land degradation", source: "Trends.Earth", note: "Open data · no registration required" },
  { id: "climate", title: "Climate extremes", source: "NASA NEX-GDDP-CMIP6 v2.0", note: "Daily data subsets · many requests for long periods" },
  { id: "groundwater", title: "Groundwater storage", source: "NASA GLDAS 2.2", note: "NASA Earthdata account · regional daily subsets" },
  { id: "drought", title: "Drought & vegetation stress", source: "NASA MODIS 6.1", note: "NASA Earthdata account · large satellite-tile downloads" },
] as const;
export type PrepModule = typeof PREP_MODULES[number]["id"];
export const MODELS = ["ACCESS-CM2", "MIROC6", "MPI-ESM1-2-HR"] as const;
export const METRICS = { hot: "Hot days", warm: "Warm nights", frost: "Frost days", temperature: "Mean temperature", rain: "Heavy-rain days", dry: "Longest dry spell" } as const;
export type Job = {
  schema: "nbs-local-job/v1"; name: string; modules: PrepModule[]; boundarySha256: string;
  groundwater: { baseline: [number, number]; monitoring: [number, number] };
  drought: { reference: [number, number]; minimumYears: number; compare: [number, number]; seasons: { name: string; start: number; end: number }[] };
  climate: { baseline: [number, number]; future: [number, number]; models: string[]; scenarios: string[]; metrics: (keyof typeof METRICS)[]; thresholds: { hot: number; warm: number; rain: number; dry: number } };
  flood: { returnPeriods: number[] }; landMask: "worldcover2021" | "all-land"; maxDownloadGB: number;
};
export function defaultJob(): Job {
  return { schema: "nbs-local-job/v1", name: "Ganjam District, Odisha", modules: ["flood", "degradation"], boundarySha256: "",
    groundwater: { baseline: [2003, 2013], monitoring: [2014, 2023] },
    drought: { reference: [2001, 2023], minimumYears: 15, compare: [2013, 2023], seasons: [{ name: "Season 1", start: 6, end: 10 }, { name: "Season 2", start: 11, end: 3 }] },
    climate: { baseline: [1991, 2020], future: [2041, 2070], models: [...MODELS], scenarios: ["ssp245", "ssp585"], metrics: Object.keys(METRICS) as (keyof typeof METRICS)[], thresholds: { hot: 35, warm: 25, rain: 20, dry: 1 } },
    flood: { returnPeriods: [10, 100, 500] }, landMask: "worldcover2021", maxDownloadGB: 20 };
}
export function validateJob(j: Job, requireHash = true): Job {
  const range = (v: number[], name: string, low: number, high: number) => { if (v.length !== 2 || !v.every(Number.isInteger) || v[0] < low || v[1] > high || v[0] > v[1]) throw new Error(`${name}: choose ordered years between ${low} and ${high}.`); };
  if (!j.name.trim() || j.name.length > 120) throw new Error("Enter a study-area name of 1–120 characters.");
  if (j.schema !== "nbs-local-job/v1" || (requireHash && !/^[a-f0-9]{64}$/.test(j.boundarySha256))) throw new Error("The configuration and boundary must belong to the same package.");
  if (!j.modules.length || new Set(j.modules).size !== j.modules.length || j.modules.some(m => !PREP_MODULES.some(p => p.id === m))) throw new Error("Choose at least one module.");
  range(j.groundwater.baseline, "Groundwater baseline", 2003, 2025); range(j.groundwater.monitoring, "Groundwater monitoring", 2003, 2025);
  if (j.groundwater.baseline[1] >= j.groundwater.monitoring[0]) throw new Error("Groundwater monitoring must follow the baseline.");
  range(j.drought.reference, "VHI reference", 2001, 2024);
  const years = j.drought.reference[1] - j.drought.reference[0] + 1;
  if (!Number.isInteger(j.drought.minimumYears) || j.drought.minimumYears < 15 || j.drought.minimumYears > years) throw new Error("VHI requires at least 15 reference years.");
  range(j.drought.compare, "VHI comparison", ...j.drought.reference);
  if (j.drought.compare[0] === j.drought.compare[1]) throw new Error("Select two different VHI comparison years.");
  if (j.drought.seasons.length < 1 || j.drought.seasons.length > 2) throw new Error("Choose one or two growing seasons.");
  const months = new Set<number>();
  for (const s of j.drought.seasons) {
    if (!s.name.trim() || s.name.length > 50 || ![s.start,s.end].every(v=>Number.isInteger(v) && v >= 1 && v <= 12)) throw new Error("Each season needs a name and valid months.");
    for (let i=0;i<((s.end-s.start+12)%12)+1;i++) { const m=(s.start-1+i)%12+1; if(months.has(m)) throw new Error("Growing seasons must not overlap."); months.add(m); }
  }
  range(j.climate.baseline, "Climate baseline", 1950, 2020); range(j.climate.future, "Climate future", 2021, 2100);
  for (const [key, allowed] of [["models", MODELS], ["scenarios", ["ssp245", "ssp585"]], ["metrics", Object.keys(METRICS)]] as const) {
    const values: string[] = j.climate[key];
    if (!values.length || new Set(values).size !== values.length || values.some(v=>!(allowed as readonly string[]).includes(v))) throw new Error(`Choose supported climate ${key}.`);
  }
  const limits = { hot: [-20,60], warm: [-20,45], rain: [1,500], dry: [.1,20] };
  for (const k of Object.keys(limits) as (keyof typeof limits)[]) { const n=j.climate.thresholds[k]; if(!Number.isFinite(n) || n<limits[k][0] || n>limits[k][1]) throw new Error(`Check the ${k} threshold.`); }
  if (!j.flood.returnPeriods.length || new Set(j.flood.returnPeriods).size !== j.flood.returnPeriods.length || j.flood.returnPeriods.some(v=>![10,100,500].includes(v))) throw new Error("Choose a flood return period.");
  if (!["worldcover2021","all-land"].includes(j.landMask) || !Number.isFinite(j.maxDownloadGB) || j.maxDownloadGB < .1 || j.maxDownloadGB > 100) throw new Error("Check the land mask and managed-download limit (0.1–100 GB).");
  return j;
}
export function bboxBoundary(w: number, s: number, e: number, n: number): VectorCollection {
  if (![w,s,e,n].every(Number.isFinite) || w>=e || s>=n) throw new Error("West must be less than east, and south less than north.");
  return validateBoundary({ type: "FeatureCollection", features: [{ type: "Feature", properties: {}, geometry: { type: "Polygon", coordinates: [[[w,s],[e,s],[e,n],[w,n],[w,s]]] } }] }).boundary;
}
export function validateBoundary(value: unknown): { boundary: VectorCollection; areaKm2: number } {
  const v = value as {type?: string};
  const boundary = validateVector(v?.type === "Feature" ? {type:"FeatureCollection",features:[v]} : v?.type === "Polygon" || v?.type === "MultiPolygon" ? {type:"FeatureCollection",features:[{type:"Feature",properties:{},geometry:v}]} : v);
  let area=0, coordinates=0, west=180, east=-180;
  const projection="EPSG:6933";
  for (const f of boundary.features) for (const polygon of f.geometry.type === "Polygon" ? [f.geometry.coordinates as number[][][]] : f.geometry.coordinates as number[][][][]) {
    for (let r=0;r<polygon.length;r++) {
      const ring=polygon[r]; coordinates+=ring.length;
      const p=ring.map(([x,y])=>{west=Math.min(west,x);east=Math.max(east,x);return proj4("EPSG:4326",projection,[x,y]);});
      let sum=0; for(let i=0;i<p.length-1;i++) sum+=p[i][0]*p[i+1][1]-p[i+1][0]*p[i][1];
      area+=(r===0?1:-1)*Math.abs(sum)/2;
    }
  }
  if (coordinates>100_000) throw new Error("Simplify the boundary to at most 100,000 coordinates.");
  if (east-west>180) throw new Error("This version does not support boundaries crossing the date line.");
  if (!(area>0 && area<=50_000*1e6)) throw new Error("Choose a study area of up to 50,000 km². Split larger regions into separate packages.");
  return {boundary,areaKm2:area/1e6};
}
export function climateRequests(j: Job): number {
  const variables = {hot:"tasmax",warm:"tasmin",frost:"tasmin",temperature:"tas",rain:"pr",dry:"pr"};
  return j.climate.models.length * new Set(j.climate.metrics.map(m=>variables[m])).size * (j.climate.baseline[1]-j.climate.baseline[0]+1 + j.climate.scenarios.length*(j.climate.future[1]-j.climate.future[0]+1));
}
