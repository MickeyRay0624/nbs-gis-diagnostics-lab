import { WaterClient, type WaterAsset } from "../water/client";
import type { VectorCollection } from "../analysis/model";
import type { LayerResult, ModuleId, NumericGrid, Source, SeriesPoint } from "../step2/model";
import { readNumericRaster } from "../step2/io";
import type { Job } from "../preparation/config";

export type Crosswalk = {source:number;code:number;name:string;color:string};
export type SourceUpload = {id:string;kind:'raster'|'vector';name:string;bytes:number;sha256:string;expires:number;info:{codes?:number[];width?:number;height?:number;crs:string;bounds?:number[];features?:number}};
export type LandOptions = {resolution:30|50|100;edge_width_m:number;include_mangroves:boolean;count_boundary_as_edge:boolean;source?:'default'|'uploaded';source_name?:string;years?:number[];rasters?:{year:number;upload_id:string}[];crosswalk?:Crosswalk[];forest_codes?:number[];protected_upload_id?:string;oecm_upload_id?:string;protection_note?:string};
export type LandManifest = {resolution_m:number;years:number[];crosswalk:Crosswalk[];forest_codes:number[];edge_width_m:number;count_boundary_as_edge:boolean;protection_note:string;protection_method:string;inputs:({role:string;year:number|null}&SourceUpload)[]};
export type DiagnosticRequest = {mode:"ganjam"|"custom";name:string;modules:ModuleId[];boundary?:VectorCollection;config?:Job;land_cover?:LandOptions};
export type DiagnosticJob = {id:string;request:DiagnosticRequest;status:"queued"|"running"|"succeeded"|"partial"|"failed"|"cancelled"|"expired";stage:string;created:number;updated:number;error:string|null;cancel_requested:boolean};
export type DiagnosticCapabilities = {analyst:string;worker_online:boolean;sample_ready:boolean;retention_days:number;uploads_enabled?:boolean;max_raster_bytes?:number;max_vector_bytes?:number;max_area_km2:number;land_cover_max_area_km2:number;max_climate_requests:number;modules:{id:ModuleId;title:string;custom_enabled:boolean;reason:string|null}[]};
export type OnlineLayer = {id:string;module:ModuleId;spec:LayerResult["spec"];file:string;grid:NumericGrid;stats:LayerResult["stats"];nativeResolution:string};
export type OnlineModule = {id:ModuleId;title:string;status:"available"|"needs-data";reason_code?:string;method?:string[];limitations?:string[];sources?:string[];missing?:string[];series?:{title:string;unit:string;points:SeriesPoint[]}[]};
export type DiagnosticResult = {schema:"nbs-online-diagnostics/v1";name:string;prepared_at:string;complete:boolean;scope:string;land?:LandManifest;boundary:VectorCollection;modules:OnlineModule[];layers:OnlineLayer[];sources:Source[];assets:WaterAsset[];validation:{status:"passed";checks:number;complete:boolean;completed_modules:ModuleId[]};tables:{module:ModuleId;title:string;file:string;rows:Record<string,string|number|null>[]}[]};

export class DiagnosticClient {
  private api: WaterClient;
  constructor(base:string,code=""){this.api=new WaterClient(base.replace(/\/$/,"")+"/diagnostics",code);}
  upload(file:Blob,name:string,kind:'raster'|'vector',signal?:AbortSignal){return this.api.request<SourceUpload>(`/uploads?kind=${kind}&name=${encodeURIComponent(name.slice(0,120))}`,{method:'POST',headers:{'Content-Type':'application/octet-stream'},body:file,signal});}
  discard(id:string){return this.api.request(`/uploads/${id}/discard`,{method:'POST'});}
  capabilities(signal?:AbortSignal){return this.api.request<DiagnosticCapabilities>("/capabilities",{signal});}
  jobs(signal?:AbortSignal){return this.api.request<DiagnosticJob[]>("/jobs",{signal});}
  submit(request:DiagnosticRequest,key:string){return this.api.request<DiagnosticJob>("/jobs",{method:"POST",headers:{"Content-Type":"application/json","Idempotency-Key":key},body:JSON.stringify(request)});}
  cancel(id:string){return this.api.request<DiagnosticJob>(`/jobs/${id}/cancel`,{method:"POST"});}
  result(id:string,signal?:AbortSignal){return this.api.request<DiagnosticResult>(`/jobs/${id}/result`,{signal});}
  asset(id:string,asset:WaterAsset,signal?:AbortSignal){return this.api.asset(id,asset,signal);}
}

export async function readOnlineLayer(bytes:ArrayBuffer,layer:OnlineLayer,asset:WaterAsset):Promise<LayerResult>{
  const raster=await readNumericRaster(bytes,{id:layer.id,file:asset.file,sha256:asset.sha256,source:"online",grid:layer.grid,bands:["Result","Eligible area (km2)"],areaBand:2,nativeResolution:layer.nativeResolution,processing:"Computed and checked on the server."});
  return {spec:layer.spec,grid:raster.grid,values:raster.bands[0],areas:raster.bands[1],stats:layer.stats};
}
