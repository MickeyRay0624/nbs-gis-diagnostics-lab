import { useEffect, useRef, useState } from "react";
import type { Grid, LandClass } from "./analysis/model";
import { geoTiff } from "./analysis/io";
import { download } from "./analysis/presets";

export function RasterView({ data, grid, classes, title, nodata, attribution }: {
  data: Uint16Array | Uint8Array; grid: Grid; classes: LandClass[]; title: string; nodata: number; attribution: string;
}) {
  const canvas = useRef<HTMLCanvasElement>(null), [hover, setHover] = useState("Move over the map to inspect classes");
  const mapWidth = Math.round(490 * grid.width / Math.max(grid.width, grid.height));
  const mapHeight = Math.round(490 * grid.height / Math.max(grid.width, grid.height));
  const x0 = Math.round((560 - mapWidth) / 2), y0 = 50;
  const exportPng = () => {
    if (!canvas.current) return;
    const output = document.createElement("canvas");
    output.width = 560; output.height = 624 + Math.ceil(classes.length / 2) * 25 + 78;
    const ctx = output.getContext("2d")!;
    ctx.fillStyle = "#f6f6ef"; ctx.fillRect(0, 0, output.width, output.height);
    ctx.drawImage(canvas.current, 0, 0);
    ctx.font = "12px Arial";
    classes.forEach((c, i) => {
      const x = 20 + (i % 2) * 270, y = 638 + Math.floor(i / 2) * 25;
      ctx.fillStyle = c.color; ctx.fillRect(x, y - 10, 12, 12);
      ctx.fillStyle = "#37513d"; ctx.fillText(`${c.code} · ${c.name}`, x + 19, y, 240);
    });
    ctx.font = "10px Arial";
    if (attribution.includes("WorldCover")) {
      ctx.fillText("© ESA WorldCover project 2020/2021 / Contains modified Copernicus Sentinel", 20, output.height - 42);
      ctx.fillText("data processed by ESA WorldCover consortium. CC BY 4.0. Boundary: gbOpen, ODbL 1.0.", 20, output.height - 27, 520);
    }
    ctx.fillText("Technical analysis. Source quality and processing choices affect interpretation.", 20, output.height - 12);
    output.toBlob(blob => { if (blob) download(`${title.replaceAll(" ", "_")}.png`, blob, "image/png"); });
  };
  useEffect(() => {
    const c = canvas.current, context = c?.getContext("2d"); if (!c || !context) return;
    context.fillStyle = "#f6f6ef"; context.fillRect(0, 0, c.width, c.height);
    context.fillStyle = "#173b31"; context.font = "600 19px Arial"; context.fillText(title, 20, 30);
    const rgba = new Map(classes.map(v => [v.code, [parseInt(v.color.slice(1, 3), 16), parseInt(v.color.slice(3, 5), 16), parseInt(v.color.slice(5, 7), 16)]]));
    const pixels = context.createImageData(mapWidth, mapHeight);
    for (let y = 0; y < mapHeight; y++) for (let x = 0; x < mapWidth; x++) {
      const value = data[Math.min(grid.height - 1, Math.floor((y + .5) * grid.height / mapHeight)) * grid.width + Math.min(grid.width - 1, Math.floor((x + .5) * grid.width / mapWidth))];
      const color = rgba.get(value); if (value === nodata || !color) continue;
      const offset = (y * mapWidth + x) * 4;
      pixels.data[offset] = color[0]; pixels.data[offset + 1] = color[1]; pixels.data[offset + 2] = color[2]; pixels.data[offset + 3] = 255;
    }
    context.putImageData(pixels, x0, y0);
    context.fillStyle = "#36584a"; context.font = "14px Arial"; context.fillText("N ↑", 23, 73);
    const scaleMetres = grid.width * grid.cell / 5, scalePx = mapWidth / 5;
    context.fillRect(x0, y0 + mapHeight + 14, scalePx, 3);
    context.font = "11px Arial"; context.fillText(`${(scaleMetres / 1000).toFixed(1)} km`, x0, y0 + mapHeight + 32);
    context.fillText(`${grid.crs} · ${grid.cell} m grid · pixel-centre preview`, 20, 588);
    context.fillStyle = "#6e7a72"; context.font = "10px Arial";
    context.fillText(attribution, 20, 608, 520);
  }, [data, grid, classes, title, nodata, attribution, mapWidth, mapHeight, x0]);
  return <article className="raster-card">
    <canvas ref={canvas} width={560} height={624} aria-label={title}
      onPointerMove={e => { const rect = e.currentTarget.getBoundingClientRect(); const x = (e.clientX - rect.left) / rect.width * 560 - x0, y = (e.clientY - rect.top) / rect.height * 624 - y0;
        if (x < 0 || y < 0 || x >= mapWidth || y >= mapHeight) { setHover("Outside mapped extent"); return; }
        const value = data[Math.floor(y / mapHeight * grid.height) * grid.width + Math.floor(x / mapWidth * grid.width)];
        setHover(value === nodata ? "NoData / outside AOI" : `${classes.find(c => c.code === value)?.name ?? value} · code ${value}`);
      }} />
    <p className="map-inspect">{hover}</p>
    <div className="output-actions">
      <button onClick={() => download(`${title.replaceAll(" ", "_")}.tif`, geoTiff(data, grid, nodata), "image/tiff")}>Download GeoTIFF ↓</button>
      <button onClick={exportPng}>Map PNG ↓</button>
    </div>
  </article>;
}
