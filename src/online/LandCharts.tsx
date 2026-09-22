import { useMemo, useRef, useState } from 'react';
import type { DiagnosticResult } from './client';
import { download } from '../analysis/presets';
import { number } from '../step2/NumericResults';

type Row=Record<string,string|number|null>;
const n=(r:Row,key:string)=>Number(r[key]??0),short=(s:string,max=27)=>s.length>max?s.slice(0,max-1)+'…':s;
export async function svgPng(svg:SVGSVGElement,name:string){
  const copy=svg.cloneNode(true) as SVGSVGElement;copy.setAttribute('xmlns','http://www.w3.org/2000/svg');
  const w=svg.viewBox.baseVal.width,h=svg.viewBox.baseVal.height;
  copy.setAttribute('width',String(w));copy.setAttribute('height',String(h));
  const url=URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(copy)],{type:'image/svg+xml'}));
  try{
    const img=new Image();img.src=url;await img.decode();const canvas=document.createElement('canvas'),scale=Math.min(2,Math.sqrt(16_000_000/(w*h)));canvas.width=Math.ceil(w*scale);canvas.height=Math.ceil(h*scale);
    const ctx=canvas.getContext('2d')!;ctx.fillStyle='#fffefa';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.drawImage(img,0,0,canvas.width,canvas.height);
    const blob=await new Promise<Blob>((resolve,reject)=>canvas.toBlob(b=>b?resolve(b):reject(new Error('PNG export failed.')),'image/png'));download(name,blob,'image/png');
  }finally{URL.revokeObjectURL(url);}
}
function ExportChart({svg,name}:{svg:React.RefObject<SVGSVGElement|null>;name:string}){
  const [busy,setBusy]=useState(false),[error,setError]=useState('');
  return <><button className="chart-export" disabled={busy} onClick={async()=>{if(!svg.current)return;setBusy(true);try{await svgPng(svg.current,name);setError('');}catch(e){setError((e as Error).message);}finally{setBusy(false);}}}>Chart PNG ↓</button>{error&&<p role="alert">{error}</p>}</>;
}
export function ChangeChart({rows,label,title,subtitle}:{rows:Row[];label:string;title:string;subtitle:string}){
  const ref=useRef<SVGSVGElement>(null),max=Math.max(1,...rows.flatMap(r=>[n(r,'gross_gain_ha'),n(r,'gross_loss_ha'),Math.abs(n(r,'net_ha'))]));
  const height=125+rows.length*54,scale=240/max,center=480;
  return <div className="land-chart"><div className="chart-title"><h4>{title}</h4><ExportChart svg={ref} name="change-balance.png"/></div><div className="chart-scroll"><svg ref={ref} viewBox={`0 0 840 ${height}`} role="img" aria-label={title} fontFamily="Arial, sans-serif" fontSize={12} fill="#234d3f">
    <rect width="840" height={height} fill="#fffefa"/><text x="20" y="27" fontSize="17" fontWeight="bold">{title}</text><text x="20" y="49" fontSize="11" fill="#697b70">{subtitle}</text>
    <text x={center-110} y="76" textAnchor="middle" fill="#b9654e">Gross loss (ha)</text><text x={center+110} y="76" textAnchor="middle" fill="#458264">Gross gain (ha)</text><text x="825" y="76" textAnchor="end">◆ Net (ha)</text>
    <line x1={center} y1="86" x2={center} y2={height-24} stroke="#b9cbbb"/>
    {rows.map((r,i)=>{const y=100+i*54,gain=n(r,'gross_gain_ha'),loss=n(r,'gross_loss_ha'),net=n(r,'net_ha'),x=center+net*scale;return <g key={i}><title>{String(r[label])}: gain {gain} ha; loss {loss} ha; net {net} ha</title><text x="20" y={y+8}>{short(String(r[label]))}</text><rect x={center-loss*scale} y={y-5} width={loss*scale} height="16" rx="2" fill="#cb836b"/><rect x={center} y={y-5} width={gain*scale} height="16" rx="2" fill="#6c9d75"/><path d={`M${x} ${y+16}l5 5-5 5-5-5Z`} fill="#234d3f"/><text x="825" y={y+8} textAnchor="end" fontSize="11">{net>0?'+':''}{number(net,1)}</text><text x={center-8} y={y+34} textAnchor="end" fill="#9d614e" fontSize="10">{number(loss,1)}</text><text x={center+8} y={y+34} fill="#477a58" fontSize="10">{number(gain,1)}</text></g>;})}
  </svg></div><small>Gains and losses exclude persistence. Net = gain − loss. All values use the same valid comparison footprint.</small></div>;
}
function Matrix({rows,classes,title}:{rows:Row[];classes:{code:number;name:string;color:string}[];title:string}){
  const ref=useRef<SVGSVGElement>(null),lookup=new Map(rows.map(r=>[`${r.from_code}:${r.to_code}`,n(r,'area_ha')]));
  const max=Math.max(1,...lookup.values()),cell=62,w=180+classes.length*cell,h=170+classes.length*(cell+15);
  return <div className="land-chart"><div className="chart-title"><h4>Land-cover change matrix</h4><ExportChart svg={ref} name="change-matrix.png"/></div><p className="chart-caption">Rows = earlier class · columns = later class · hectares. Diagonal cells stayed in the same class.</p>
    <div className="table-scroll matrix-table"><table><caption className="sr-only">{title} · change matrix in hectares</caption><thead><tr><th>From ↓ / To →</th>{classes.map(c=><th key={c.code}><i style={{background:c.color}}/>{c.name}</th>)}<th>Earlier area</th></tr></thead><tbody>{classes.map(a=><tr key={a.code}><th><i style={{background:a.color}}/>{a.name}</th>{classes.map(b=>{const value=lookup.get(`${a.code}:${b.code}`)??0;return <td key={b.code} className={a.code===b.code?'matrix-diagonal':''} style={{background:`rgba(106, 154, 113, ${value?0.09+0.35*Math.sqrt(value/max):0})`}}>{number(value,1)}</td>})}<td>{number(rows.filter(r=>r.from_code===a.code).reduce((s,r)=>s+n(r,'area_ha'),0),1)}</td></tr>)}</tbody><tfoot><tr><th>Later area</th>{classes.map(c=><td key={c.code}>{number(rows.filter(r=>r.to_code===c.code).reduce((s,r)=>s+n(r,'area_ha'),0),1)}</td>)}<td>{number(rows.reduce((s,r)=>s+n(r,'area_ha'),0),1)}</td></tr></tfoot></table></div>
    <svg ref={ref} className="export-only-chart" viewBox={`0 0 ${w} ${h}`} aria-hidden="true" fontFamily="Arial, sans-serif" fontSize="11" fill="#234d3f"><rect width={w} height={h} fill="#fffefa"/><text x="20" y="26" fontSize="16">Change matrix · {title}</text><text x="20" y="49">Hectares · earlier codes ↓ / later codes →</text>{classes.map((a,i)=><g key={a.code}><text x="85" y={91+i*cell} textAnchor="end">{a.code}</text><text x={131+i*cell} y="70" textAnchor="middle">{a.code}</text>{classes.map((b,j)=>{const v=lookup.get(`${a.code}:${b.code}`)??0;return <g key={b.code}><rect x={100+j*cell} y={77+i*cell} width={cell-2} height={cell-2} fill={v?'#dce9d8':'#f5f6f0'}/><text x={130+j*cell} y={110+i*cell} textAnchor="middle" fontSize="10">{number(v,1)}</text></g>})}<text x="20" y={105+classes.length*cell+i*15}>{a.code}: {a.name}</text></g>)}</svg>
  </div>;
}
function ForestGroups({rows,title}:{rows:Row[];title:string}){
  const ref=useRef<SVGSVGElement>(null),max=Math.max(1,...rows.flatMap(r=>[n(r,'before_ha'),n(r,'after_ha')])),h=115+rows.length*75;
  return <div className="land-chart"><div className="chart-title"><h4>Forest area by spatial group</h4><ExportChart svg={ref} name="forest-spatial-groups.png"/></div><div className="chart-scroll"><svg ref={ref} viewBox={`0 0 840 ${h}`} role="img" aria-label="Earlier and later forest area by spatial group" fontFamily="Arial, sans-serif" fontSize="12" fill="#234d3f"><rect width="840" height={h} fill="#fffefa"/><text x="20" y="27" fontSize="17">Forest area by spatial group</text><text x="20" y="50" fontSize="11">{title} · common valid cells · hectares</text><rect x="580" y="20" width="12" height="12" fill="#b9cfa9"/><text x="600" y="31">Earlier</text><rect x="680" y="20" width="12" height="12" fill="#477953"/><text x="700" y="31">Later</text>{rows.map((r,i)=><g key={i}><text x="20" y={95+i*75}>{short(String(r.stratum))}</text>{(['before_ha','after_ha'] as const).map((k,j)=><g key={k}><rect x="225" y={76+i*75+j*23} width={n(r,k)/max*470} height="16" rx="2" fill={j?'#477953':'#b9cfa9'}/><text x={235+n(r,k)/max*470} y={89+i*75+j*23} fontSize="11">{number(n(r,k),1)}</text></g>)}</g>)}</svg></div><small>Areas are allocated by pixel. Administrative lines do not create forest edges. “All” overlaps its subgroups and must not be added to them.</small></div>;
}
export function LandCharts({result,moduleId}:{result:DiagnosticResult;moduleId:'lulc'|'fragmentation'}){
  const filename=moduleId==='lulc'?'land-cover-balance.csv':'forest-changes.csv';
  const all=result.tables.find(t=>t.file===filename)?.rows??[];
  const periods=[...new Set(all.map(r=>`${r.start_year}–${r.end_year}`))],groups=[...new Set(all.map(r=>String(r.stratum)))];
  const [period,setPeriod]=useState(''),[group,setGroup]=useState('All');
  const chosen=periods.includes(period)?period:periods[0],stratum=groups.includes(group)?group:groups[0];
  const rows=all.filter(r=>`${r.start_year}–${r.end_year}`===chosen&&r.stratum===stratum);
  const transitions=result.tables.find(t=>t.file==='land-cover-transitions.csv')?.rows.filter(r=>`${r.start_year}–${r.end_year}`===chosen&&r.stratum===stratum)??[];
  const classes=useMemo(()=>[...new Map(result.land?.crosswalk.filter(r=>r.code!==0).map(r=>[r.code,r])??[]) .values()].sort((a,b)=>a.code-b.code),[result.land]);
  if(!all.length)return null;
  const common=n(rows[0]??{},'common_valid_ha'),title=`${chosen} · ${stratum} · common area ${number(common,1)} ha`;
  return <section className="land-insights" aria-label="Landscape change insights"><div className="insights-heading"><span className="lab-kicker">CHANGE IN CONTEXT</span><h3>{moduleId==='lulc'?'Where the landscape changed.':'How forest structure changed.'}</h3><p>Compare the same observed area in both periods.</p></div><div className="insight-controls"><label>Comparison<select value={chosen} onChange={e=>setPeriod(e.target.value)}>{periods.map(p=><option key={p}>{p}</option>)}</select></label><label>Spatial group<select value={stratum} onChange={e=>setGroup(e.target.value)}>{groups.map(g=><option key={g}>{g}</option>)}</select></label><div><small>COMMON VALID AREA</small><strong>{number(common,1)} <em>ha</em></strong></div></div>
    {common>0?<>{moduleId==='lulc'?<><ChangeChart rows={rows} label="class_name" title="Gross gain, loss & net change" subtitle={title}/><Matrix rows={transitions} classes={classes} title={title}/></>:<><ForestGroups title={chosen} rows={all.filter(r=>`${r.start_year}–${r.end_year}`===chosen&&r.component==='Forest')}/><ChangeChart rows={rows} label="component" title="Forest structure balance" subtitle={title}/></>}</>:<p className="prep-callout">No cells have valid observations in both periods for this group. Change cannot be estimated.</p>}
  </section>;
}
