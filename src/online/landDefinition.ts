import type { Crosswalk } from './client';
import { PALETTE } from '../analysis/presets';

// A high source code must not accidentally merge with another class when it is
// assigned a target within the server's 0–999 range.
export function sourceCrosswalk(sources:number[], existing:Crosswalk[]=[], legend:Crosswalk[]=[]):Crosswalk[]{
  const codes=[...new Set(sources)].sort((a,b)=>a-b);
  const known=new Map(codes.map(source=>[source,existing.find(r=>r.source===source)??legend.find(r=>r.source===source)]));
  const assigned=new Set([...known.values()].filter((r):r is Crosswalk=>!!r).map(r=>r.code));
  const reserved=new Set([...assigned,...codes.filter(c=>c<=999)]);
  return codes.map((source,i)=>{
    const row=known.get(source);if(row)return row;
    let code=source;
    if(code>999||assigned.has(code)){code=1;while(reserved.has(code))code++;}
    assigned.add(code);reserved.add(code);
    return {source,code,name:`Class ${source}`,color:PALETTE[i%PALETTE.length]};
  });
}
