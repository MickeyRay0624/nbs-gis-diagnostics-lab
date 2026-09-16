import type { CrosswalkRow } from "./model";

export const WORLDCOVER: CrosswalkRow[] = [
  [10, "Tree cover", "#006400"], [20, "Shrubland", "#ffbb22"], [30, "Grassland", "#ffff4c"],
  [40, "Cropland", "#f096ff"], [50, "Built-up", "#fa0000"], [60, "Bare / sparse vegetation", "#b4b4b4"],
  [70, "Snow and ice", "#f0f0f0"], [80, "Permanent water bodies", "#0064c8"],
  [90, "Herbaceous wetland", "#0096a0"], [95, "Mangroves", "#00cf75"], [100, "Moss and lichen", "#fae6a0"],
].map(([code, name, color]) => ({ source: Number(code), code: Number(code), name: String(name), color: String(color) }));

export const ESRI: CrosswalkRow[] = [
  [1, "Water", "#1a5bab"], [2, "Trees", "#358221"], [4, "Flooded vegetation", "#87d19e"],
  [5, "Crops", "#ffdb5c"], [7, "Built area", "#ed022a"], [8, "Bare ground", "#ede9e4"],
  [9, "Snow / ice", "#f2faff"], [10, "Clouds", "#c8c8c8"], [11, "Rangeland", "#c6ad8d"],
].map(([code, name, color]) => ({ source: Number(code), code: Number(code), name: String(name), color: String(color) }));

// Explicit project legend for GLC-FCS30D; orchards are cropland, mangroves forest.
export const GLCFCS: CrosswalkRow[] = [
  {code:1,name:"Cropland",color:"#deb85b",sources:[10,11,12,20]},
  {code:2,name:"Forest (including mangroves)",color:"#246445",sources:[51,52,61,62,71,72,81,82,91,92,185]},
  {code:3,name:"Shrubland",color:"#b6ac51",sources:[120,121,122]},
  {code:4,name:"Grassland",color:"#98bd61",sources:[130]},
  {code:5,name:"Wetland",color:"#63b6a4",sources:[181,182,183,184,186,187]},
  {code:6,name:"Built-up",color:"#cf7058",sources:[190]},
  {code:7,name:"Bare land",color:"#b2aaa0",sources:[200,201,202]},
  {code:8,name:"Water",color:"#589dc4",sources:[210]},
  {code:9,name:"Snow and ice",color:"#d7e9ed",sources:[220]},
  {code:10,name:"Other / sparse vegetation",color:"#c5bca1",sources:[140,150,152,153]},
].flatMap(({sources,...c})=>sources.map(source=>({...c,source})));

export const PALETTE = ["#286845", "#deb85b", "#589dc4", "#af7ac5", "#cf7058", "#7aab86", "#8a9283", "#caa77e"];

export function csv(rows: (string | number | boolean)[][]): string {
  return rows.map(row => row.map(value => {
    let text = String(value);
    // Escape text formula prefixes when exporting to spreadsheets.
    if (typeof value === "string" && /^[=+@\-\t\r]/.test(text)) text = `'${text}`;
    return /[",\n\r]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
  }).join(",")).join("\r\n") + "\r\n";
}

export function parseCrosswalk(text: string): CrosswalkRow[] {
  const records: string[][] = []; let record: string[] = [], field = "", quoted = false;
  const source = text.replace(/^\uFEFF/, "");
  for (let i = 0; i < source.length; i++) {
    const c = source[i];
    if (c === '"') { if (quoted && source[i + 1] === '"') { field += '"'; i++; } else quoted = !quoted; }
    else if (c === "," && !quoted) { record.push(field); field = ""; }
    else if ((c === "\n" || c === "\r") && !quoted) {
      if (c === "\r" && source[i + 1] === "\n") i++;
      record.push(field); if (record.some(v => v.trim())) records.push(record); record = []; field = "";
    } else field += c;
  }
  if (quoted) throw new Error("Crosswalk CSV contains an unclosed quote.");
  record.push(field); if (record.some(v => v.trim())) records.push(record);
  const header = records.shift()?.map(v => v.trim()) ?? [];
  const fields = ["source_code", "target_code", "target_name", "color"];
  if (fields.some(f => !header.includes(f))) throw new Error(`Crosswalk CSV needs ${fields.join(", ")}.`);
  return records.map(r => ({ source: Number(r[header.indexOf(fields[0])]), code: Number(r[header.indexOf(fields[1])]), name: r[header.indexOf(fields[2])]?.trim() ?? "", color: r[header.indexOf(fields[3])]?.trim() ?? "" }));
}

export function download(filename: string, content: BlobPart, type = "application/json") {
  const url = URL.createObjectURL(new Blob([content], { type })), a = document.createElement("a");
  a.href = url; a.download = filename; a.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
