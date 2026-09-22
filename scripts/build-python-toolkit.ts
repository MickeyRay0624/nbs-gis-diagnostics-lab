import { mkdir, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
const source=new URL("../engine/localprep/",import.meta.url), destination=new URL("../public/python-toolkit/",import.meta.url);
const {version}=JSON.parse(await readFile(new URL("../package.json",import.meta.url),"utf8")) as {version:string};
await rm(destination,{recursive:true,force:true});await mkdir(destination,{recursive:true});
const files:{path:string;sha256:string}[]=[];
async function copy(dir:string){
  for(const entry of await readdir(new URL(dir,source),{withFileTypes:true})){
    const path=dir+entry.name;
    if(entry.isDirectory()){if(entry.name==="nbs_prepare"){await mkdir(new URL(path+"/",destination),{recursive:true});await copy(path+"/");}continue;}
    if(!/\.(py|md|txt|bat|command)$/.test(path))continue;
    let data=await readFile(new URL(path,source));
    if(path.endsWith(".bat"))data=Buffer.from(data.toString().replace(/\r?\n/g,"\r\n"));
    await writeFile(new URL(path,destination),data);files.push({path,sha256:createHash("sha256").update(data).digest("hex")});
  }
}
await copy("");
await writeFile(new URL("manifest.json",destination),JSON.stringify({schema:"nbs-python-toolkit/v1",version,files},null,2)+"\n");
console.log(`Prepared ${files.length} portable Python toolkit files.`);
