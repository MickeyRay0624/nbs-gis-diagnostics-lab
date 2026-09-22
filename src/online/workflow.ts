import { bboxBoundary, climateRequests, validateJob, type Job } from '../preparation/config';
import { collectionBounds } from '../geo';
import type { VectorCollection } from '../analysis/model';
import type { ModuleId } from '../step2/model';
import type { DiagnosticRequest, DiagnosticJob } from './client';
import { WaterClient, type WaterRequest, type WaterJob } from '../water/client';

export type AnalysisModule = ModuleId | 'water';
export type Preset = 'custom' | 'ganjam' | 'fayoum';
export const MODULES: {id:AnalysisModule; title:string; description:string; source:string; category:string}[] = [
  {id:'lulc',title:'Land-cover change',description:'See how land use and cover are changing.',source:'ESA WorldCover',category:'Landscape'},
  {id:'fragmentation',title:'Forest fragmentation',description:'Explore forest patches, edges and core habitat.',source:'ESA WorldCover',category:'Landscape'},
  {id:'groundwater',title:'Groundwater storage',description:'Track changes in modelled groundwater reserves.',source:'NASA GLDAS',category:'Water'},
  {id:'drought',title:'Drought & vegetation',description:'Compare seasonal vegetation health and stress.',source:'NASA MODIS',category:'Vegetation'},
  {id:'climate',title:'Climate extremes',description:'Explore heat, rainfall and future climate scenarios.',source:'NASA NEX-GDDP-CMIP6',category:'Climate'},
  {id:'flood',title:'River flood hazard',description:'Map river inundation under selected return periods.',source:'JRC · CEMS-GloFAS',category:'Water'},
  {id:'degradation',title:'Land degradation',description:'Assess land condition, productivity and soil carbon.',source:'Trends.Earth',category:'Landscape'},
  {id:'water',title:'Water & productivity',description:'Calculate evapotranspiration, root-zone moisture and NPP.',source:'pyWaPOR · SE_ROOT & ETLook',category:'Water'},
];
export const FAYOUM: WaterRequest = {mode:'sample',name:'Fayoum, Egypt',bbox:[31,28.9,31.2,29.1],start:'2021-07-01',end:'2021-07-31'};
export const fayoumBoundary=()=>bboxBoundary(31,28.9,31.2,29.1);
export type AnalysisRequest = {name:string;diagnostics?:DiagnosticRequest;water?:WaterRequest};
export type AnalysisChild = {kind:'diagnostics';job:DiagnosticJob|null;modules:ModuleId[]}|{kind:'water';job:WaterJob|null;modules:['water']};
export type Analysis = {id:string;name:string;created:number;updated:number;status:DiagnosticJob['status'];stage:string;modules:AnalysisModule[];children:AnalysisChild[];cancel_requested:boolean;legacy:boolean};
export class AnalysisClient extends WaterClient {
  analyses(signal?:AbortSignal){return this.request<Analysis[]>('/analyses',{signal});}
  submitAnalysis(body:AnalysisRequest,key:string){return this.request<Analysis>('/analyses',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':key},body:JSON.stringify(body)});}
  cancelAnalysis(id:string){return this.request<Analysis>(`/analyses/${encodeURIComponent(id)}/cancel`,{method:'POST'});}
}

export function buildAnalysis(input:{preset:Preset;name:string;boundary:VectorCollection|null;modules:AnalysisModule[];config:Job;land:NonNullable<DiagnosticRequest['land_cover']>;waterDates:{start:string;end:string};waterCustom:boolean;waterReady:boolean;maxClimateRequests:number}):AnalysisRequest {
  const {preset,name,boundary,modules,config,land,waterDates}=input;
  if(!name.trim()||name.length>80)throw new Error('Enter a study-area name of 1–80 characters.');
  if(!modules.length)throw new Error('Select at least one diagnostic.');
  if(!boundary)throw new Error('Choose a valid study-area boundary.');
  if(new TextEncoder().encode(JSON.stringify(boundary)).length>190000)throw new Error('Simplify the boundary to under 190 KB.');
  const result:AnalysisRequest={name:name.trim()};
  const diagnosticModules=modules.filter((m):m is ModuleId=>m!=='water');
  if(diagnosticModules.length){
    if(preset==='ganjam')result.diagnostics={mode:'ganjam',name:result.name,modules:diagnosticModules};
    else {
      const numeric=diagnosticModules.filter(m=>m!=='lulc'&&m!=='fragmentation');
      const job={...config,name:result.name,modules:numeric.length?numeric:['flood']} as Job;
      validateJob(job,false);
      if(diagnosticModules.includes('climate')&&climateRequests(job)>input.maxClimateRequests)throw new Error(`Climate selections require ${climateRequests(job)} annual subsets; this server allows ${input.maxClimateRequests}. Keep meaningful periods and select fewer models or indices.`);
      result.diagnostics={mode:'custom',name:result.name,modules:diagnosticModules,boundary,config:job,land_cover:land};
    }
  }
  if(modules.includes('water')){
    if(preset==='ganjam')throw new Error('The Ganjam reference inputs do not include water modelling. Choose the Fayoum sample to try all eight diagnostics on one region.');
    if(preset==='fayoum'){
      if(!input.waterReady)throw new Error('The Fayoum water inputs are being prepared.');
      result.water={...FAYOUM,name:result.name};
    } else {
      if(!input.waterCustom)throw new Error('Water & productivity currently supports the Fayoum sample; custom-area source access is awaiting verification.');
      const b=collectionBounds(boundary),days=(Date.parse(waterDates.end)-Date.parse(waterDates.start))/86400000+1;
      const area=6371.0088**2*(b.east-b.west)*Math.PI/180*(Math.sin(b.north*Math.PI/180)-Math.sin(b.south*Math.PI/180));
      if(!Number.isFinite(days)||days<1||days>31)throw new Error('Water analysis supports 1–31 days per task.');
      if(area>500)throw new Error('Water analysis supports an enclosing rectangle up to 500 km².');
      result.water={mode:'custom',name:result.name,bbox:[b.west,b.south,b.east,b.north],...waterDates,...(!result.diagnostics?{boundary}:{})};
    }
  }
  return result;
}
