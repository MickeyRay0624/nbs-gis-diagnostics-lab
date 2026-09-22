import { useEffect, useState } from 'react';
import { readOnlineLayer, type DiagnosticClient, type DiagnosticResult } from './client';
import { rasterImage } from '../step2/render';
export function MapComparison({result,client,jobId,moduleId}:{result:DiagnosticResult;client:DiagnosticClient;jobId:string;moduleId:'lulc'|'fragmentation'}){
  const [open,setOpen]=useState(false),[maps,setMaps]=useState<{title:string;url:string;coverage:number}[]>([]),[error,setError]=useState('');
  useEffect(()=>{
    const controller=new AbortController();setMaps([]);setError('');
    if(open)(async()=>{
      for(const l of result.layers.filter(l=>l.module===moduleId&&(moduleId==='fragmentation'||l.spec.id.startsWith('cover-')))){
        const asset=result.assets.find(a=>a.file===l.file);if(!asset)throw new Error('The comparison map is unavailable.');
        const layer=await readOnlineLayer(await client.asset(jobId,asset,controller.signal),l,asset);
        if(controller.signal.aborted)return;
        const image=rasterImage(layer,result.boundary);setMaps(v=>[...v,{title:l.spec.title,url:image.overlay.url,coverage:l.stats.coveragePct}]);
      }
    })().catch(e=>{if(!controller.signal.aborted)setError(e.message);});
    return()=>controller.abort();
  },[open,result,client,jobId,moduleId]);
  return <details className="map-comparison" onToggle={e=>setOpen(e.currentTarget.open)}><summary>Compare period maps <span>Same extent & class colours</span></summary>{open&&<><div className="comparison-maps">{maps.map(m=><figure key={m.title}><figcaption><strong>{m.title}</strong><small>{m.coverage.toFixed(1)}% valid coverage</small></figcaption><img src={m.url} alt={m.title+' classified map'}/></figure>)}</div>{!maps.length&&!error&&<p role="status">Loading comparison maps…</p>}{error&&<p role="alert">{error}</p>}<p>Transparent areas are missing or outside the boundary. Change charts use the overlap of valid observations, which may be smaller than either map.</p></>}</details>;
}
