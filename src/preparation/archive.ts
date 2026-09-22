import { strFromU8, strToU8, Unzip, UnzipInflate, zipSync, type Zippable } from "fflate";
import { digest, validateCatalog } from "../step2/io";
import type { Catalog } from "../step2/model";
import type { VectorCollection } from "../analysis/model";
import { validateVector } from "../analysis/io";
import { validateBoundary, validateJob, type Job } from "./config";

const safeName = (name: string) => /^[A-Za-z0-9_-]+\.(tif|geojson|json)$/.test(name);
export async function buildPythonPackage(job: Job, boundary: VectorCollection, base: string): Promise<Uint8Array<ArrayBuffer>> {
  validateBoundary(boundary);
  const bytes=strToU8(JSON.stringify(boundary,null,2)+"\n");
  const config=validateJob({...job,boundarySha256:await digest(bytes.slice().buffer)});
  const response=await fetch(`${base}python-toolkit/manifest.json`);
  if(!response.ok) throw new Error("The Python toolkit could not be loaded. Reload the page and retry.");
  const manifest=await response.json() as {schema:string;files:{path:string;sha256:string}[]};
  if(manifest.schema!=="nbs-python-toolkit/v1" || !Array.isArray(manifest.files) || manifest.files.length>40) throw new Error("Unsupported Python toolkit manifest.");
  const files:Zippable={"config.json":strToU8(JSON.stringify(config,null,2)+"\n"),"aoi.geojson":bytes};
  await Promise.all(manifest.files.map(async f=>{
    if(!/^(?:nbs_prepare\/)?[A-Za-z0-9_. -]+$/.test(f.path) || f.path.includes("..") || Object.hasOwn(files,f.path)) throw new Error("Invalid toolkit file path.");
    const r=await fetch(`${base}python-toolkit/${f.path}`);
    if(!r.ok) throw new Error(`Could not load ${f.path}. Retry the download.`);
    const data=await r.arrayBuffer();
    if(data.byteLength>2_000_000 || await digest(data)!==f.sha256) throw new Error("The Python toolkit changed while downloading. Reload and retry.");
    files[f.path]=[new Uint8Array(data),{os:3,attrs:(f.path.endsWith(".command") || f.path==="run.py" ? 0o100755 : 0o100644)<<16}];
  }));
  return zipSync(files,{level:6}).slice();
}

export function unpackResultZip(bytes: Uint8Array): Record<string, Uint8Array<ArrayBuffer>> {
  if(bytes.length>200_000_000) throw new Error("Result ZIP limit is 200 MB.");
  const view=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength);
  let end=-1;
  for(let i=bytes.length-22;i>=Math.max(0,bytes.length-65557);i--) {
    if(view.getUint32(i,true)===0x06054b50 && i+22+view.getUint16(i+20,true)===bytes.length){end=i;break;}
  }
  if(end<0)throw new Error("The result ZIP is incomplete or damaged.");
  const expected=view.getUint16(end+10,true);
  if(view.getUint16(end+4,true)!==0 || view.getUint16(end+6,true)!==0 || expected!==view.getUint16(end+8,true) || expected>40 || expected===0 || view.getUint32(end+12,true)+view.getUint32(end+16,true)!==end)throw new Error("Use a complete, single-volume result ZIP with at most 40 files.");
  const result:Record<string,Uint8Array<ArrayBuffer>>=Object.create(null);
  let total=0,count=0,completed=0,failure:Error|null=null;
  const fail=(message:string)=>{failure=new Error(message);};
  const unzip=new Unzip(file=>{
    if(failure)return;
    if(!safeName(file.name) || Object.hasOwn(result,file.name) || ++count>40) {fail("Use a result ZIP with unique top-level catalog, boundary and TIFF files.");return;}
    const limit=file.name.endsWith(".tif")?100_000_000:file.name.endsWith(".geojson")?10_000_000:2_000_000;
    if(file.originalSize!==undefined && file.originalSize>limit){fail(`${file.name}: unpacked file is too large.`);return;}
    result[file.name]=new Uint8Array();
    const chunks:Uint8Array[]=[];let size=0;
    file.ondata=(error,data,final)=>{
      if(failure){file.terminate();return;}
      if(error){fail("The result ZIP is damaged or uses unsupported compression.");return;}
      size+=data.length;total+=data.length;
      if(size>limit || total>350_000_000){file.terminate();fail("Unpacked results exceed the browser memory limit.");return;}
      chunks.push(data);
      if(final){const output=new Uint8Array(size);let offset=0;for(const chunk of chunks){output.set(chunk,offset);offset+=chunk.length;}result[file.name]=output;completed++;}
    };
    file.start();
  });
  unzip.register(UnzipInflate);
  try {for(let i=0;i<bytes.length && !failure;i+=65536) unzip.push(bytes.subarray(i,i+65536),i+65536>=bytes.length);}
  catch {throw new Error("The result ZIP is damaged or incomplete.");}
  if(failure)throw failure;
  if(completed!==count || count!==expected)throw new Error("The result ZIP is incomplete.");
  if(!Object.hasOwn(result,"catalog.json"))throw new Error("The result ZIP must contain catalog.json.");
  return result;
}
export async function validateResultFiles(files: Record<string, Uint8Array<ArrayBuffer>>, fallback?: {catalog:Catalog;aoi:VectorCollection}): Promise<{catalog:Catalog;aoi:VectorCollection;files:Record<string,File>}> {
  const catalogFile=files["catalog.json"];
  if(!catalogFile || catalogFile.length>2_000_000)throw new Error("Select one catalog.json file (up to 2 MB).");
  const catalog=validateCatalog(JSON.parse(strFromU8(catalogFile)));
  if(!safeName(catalog.studyArea.boundary) || !catalog.studyArea.boundary.endsWith(".geojson"))throw new Error("The catalog must name a top-level GeoJSON boundary.");
  const boundary=files[catalog.studyArea.boundary];let aoi:VectorCollection;
  if(boundary){
    if(boundary.length>10_000_000 || await digest(boundary.buffer)!==catalog.studyArea.sha256)throw new Error("The boundary checksum does not match this catalog.");
    aoi=validateVector(JSON.parse(strFromU8(boundary)));
  }else if(fallback && fallback.catalog.studyArea.sha256===catalog.studyArea.sha256){aoi=fallback.aoi;}
  else throw new Error("Include the GeoJSON boundary named in the catalog.");
  const rasters:Record<string,File>={};
  for(const asset of catalog.rasters){
    const data=files[asset.file];
    if(!data || data.length>100_000_000)throw new Error(`Include ${asset.file} (up to 100 MB).`);
    if(await digest(data.buffer)!==asset.sha256)throw new Error(`${asset.file}: checksum mismatch. Select files from the same run.`);
    rasters[asset.file]=new File([data.buffer],asset.file,{type:"image/tiff"});
  }
  return {catalog,aoi,files:rasters};
}
export async function importResults(list: File[], fallback?: {catalog:Catalog;aoi:VectorCollection}) {
  if(list.length===1 && /\.zip$/i.test(list[0].name)) {
    if(list[0].size>200_000_000)throw new Error("Result ZIP limit is 200 MB.");
    return validateResultFiles(unpackResultZip(new Uint8Array(await list[0].arrayBuffer())),fallback);
  }
  let total=0;const entries:Record<string,Uint8Array<ArrayBuffer>>=Object.create(null);
  for(const f of list){
    total+=f.size;
    if(!safeName(f.name) || Object.hasOwn(entries,f.name) || f.size>100_000_000 || total>350_000_000 || list.length>40)throw new Error("Select unique catalog.json, boundary GeoJSON and TIFF files within the package size limits.");
    entries[f.name]=new Uint8Array(await f.arrayBuffer());
  }
  return validateResultFiles(entries,fallback);
}
