import type { AnalysisModule } from './workflow';
const paths:Record<AnalysisModule,string[]>={
  lulc:['M3 5h7v7H3zM14 5h7v4h-7zM3 16h7v5H3zM14 13h7v8h-7z'],
  fragmentation:['m7 3-5 9h3l-3 5h10l-3-5h3L7 3ZM7 17v4M18 5l4 8h-3l3 5h-7M18 18v3'],
  groundwater:['M3 5h18M3 10c3-3 6 3 9 0s6-3 9 0M3 16c3-3 6 3 9 0s6-3 9 0M5 21h14'],
  drought:['M12 3v3M4 5l2 2M20 5l-2 2M2 12h3M19 12h3M8 14a5 5 0 1 1 8 0M5 20c3-4 5 3 8-1s4 0 6-3'],
  climate:['M12 2v2M3 6l2 1M21 6l-2 1M8 12a5 5 0 1 1 9-3M6 18a4 4 0 1 1 2-7 5 5 0 0 1 9 1 3 3 0 1 1 1 6ZM8 21v1M14 21v1'],
  flood:['M4 3l4 5-3 5 4 5M15 3l4 5-3 5 4 5M2 21c3-3 5 3 8 0s5-3 8 0 3 0 4-1'],
  degradation:['M3 6h18M3 12h7l3 4 3-4h5M3 20h7l3-4M16 20h5'],
  water:['M8 2C6 6 2 9 2 13a6 6 0 0 0 12 0c0-4-4-7-6-11ZM14 21c0-8 3-12 8-12 0 6-2 9-7 9M6 13v2'],
};
export function ModuleIcon({id}:{id:AnalysisModule}){return <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[id].map((d,i)=><path d={d} key={i}/>)}</svg>;}
