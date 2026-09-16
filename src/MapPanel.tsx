import { useEffect, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import mapWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import type { GeoJSONSource, GeoJSONSourceSpecification, StyleSpecification } from "maplibre-gl";
import { collectionBounds } from "./geo";
import type { VectorCollection } from "./analysis/model";
import type { MapOverlay } from "./step2/model";

// MapLibre 6 has a separate ESM worker. Bundle its shared imports for GitHub Pages.
maplibregl.setWorkerUrl(mapWorkerUrl);

interface MapPanelProps {
  aoi: VectorCollection | null;
  label: string;
  loading: boolean;
  error: string | null;
  extentOnly?: boolean;
  overlay?: MapOverlay | null;
  opacity?: number;
}

// The study-area layer must not wait for remote basemap tiles to finish loading.
const baseStyle: StyleSpecification = {
  version: 8,
  sources: {},
  layers: [{ id: "background", type: "background", paint: { "background-color": "#e5ebe1" } }],
};

export function MapPanel({ aoi, label, loading, error, extentOnly = false, overlay, opacity = .8 }: MapPanelProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [map, setMap] = useState<maplibregl.Map | null>(null);
  const [layerReady, setLayerReady] = useState(false);
  const [mapError, setMapError] = useState<string | null>(null);
  const [basemapError, setBasemapError] = useState(false);
  const geometryKey = JSON.stringify(aoi?.features.map(f=>f.geometry) ?? null);
  const fittedGeometry = useRef<string | null>(null);
  const focusRef = useRef<(context?: boolean) => void>(() => {});

  useEffect(() => {
    if (!containerRef.current) return;
    let active = true;
    let instance: maplibregl.Map;
    setMapError(null);
    try {
      instance = new maplibregl.Map({
        container: containerRef.current, style: baseStyle, center: [0, 15], zoom: 1.5,
        minZoom: 0, maxZoom: 18, attributionControl: false, cooperativeGestures: true,
      });
    } catch {
      setMapError("Interactive map unavailable. Enable WebGL or try another browser. Analysis still works.");
      return;
    }
    instance.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    instance.addControl(new maplibregl.ScaleControl({ maxWidth: 120, unit: "metric" }), "bottom-left");
    instance.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");
    instance.on("style.load", () => {
      if (!active) return;
      instance.addSource("osm", { type: "raster", tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"], tileSize: 256,
        attribution: '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap contributors</a>' });
      instance.addLayer({ id: "osm", type: "raster", source: "osm", paint: { "raster-opacity": .8 } });
      instance.addSource("study-area", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      instance.addLayer({ id: "study-area-fill", type: "fill", source: "study-area", paint: { "fill-color": "#b8df71", "fill-opacity": .32 } });
      instance.addLayer({ id: "study-area-halo", type: "line", source: "study-area", paint: { "line-color": "#ffffff", "line-width": 7 } });
      instance.addLayer({ id: "study-area-line", type: "line", source: "study-area", paint: { "line-color": "#174f43", "line-width": 3 } });
      setMap(instance);
    });
    instance.on("error", event => {
      if (!active) return;
      if ("sourceId" in event && event.sourceId === "osm") setBasemapError(true);
      else setMapError("The boundary layer could not be drawn. Reload the page to retry.");
    });
    return () => { active = false; setMap(null); instance.remove(); };
  }, []);

  useEffect(() => {
    if (!map) return;
    let active = true;
    let autoFit = fittedGeometry.current !== geometryKey;
    let marker: maplibregl.Marker | undefined;
    setLayerReady(false);
    const source = map.getSource("study-area") as GeoJSONSource;
    const data = (aoi ?? { type: "FeatureCollection", features: [] }) as GeoJSONSourceSpecification["data"];
    // setData resolves after the GeoJSON worker has processed this exact boundary.
    source.setData(data as Parameters<GeoJSONSource["setData"]>[0]).then(() => {
      if (active) setLayerReady(!!aoi);
    }).catch(() => { if (active) setMapError("The selected boundary could not be drawn. Check the GeoJSON and retry."); });

    const focus = (context = false) => {
      if (!aoi) return;
      const b = collectionBounds(aoi), x = context ? (b.east - b.west) * 1.5 : 0, y = context ? (b.north - b.south) * 1.5 : 0;
      map.resize();
      map.fitBounds([[b.west - x, Math.max(-85, b.south - y)], [b.east + x, Math.min(85, b.north + y)]],
        { padding: { top: 70, bottom: 48, left: 38, right: 48 }, duration: 0, maxZoom: 16 });
    };
    focusRef.current = context => { autoFit = !context; focus(context); };
    if (aoi) {
      const b = collectionBounds(aoi);
      const element = document.createElement("div");
      element.className = "study-area-marker";
      element.textContent = label;
      element.title = extentOnly ? "Centre of the input raster extent" : "Selected study area";
      marker = new maplibregl.Marker({ element, anchor: "bottom" })
        .setLngLat([(b.west + b.east) / 2, (b.south + b.north) / 2]).addTo(map);
      if (fittedGeometry.current !== geometryKey) { focus(); fittedGeometry.current = geometryKey; }
    } else map.jumpTo({ center: [0, 15], zoom: 1.5 });

    const onMove = (event: maplibregl.MapLibreEvent) => { if (event.originalEvent) autoFit = false; };
    map.on("movestart", onMove);
    const resize = new ResizeObserver(() => { map.resize(); if (autoFit) focus(); });
    if (containerRef.current) resize.observe(containerRef.current);
    return () => { active = false; marker?.remove(); resize.disconnect(); map.off("movestart", onMove); focusRef.current = () => {}; };
  }, [map, aoi, label, extentOnly, geometryKey]);

  useEffect(() => {
    if (!map) return;
    if (!overlay) {
      if (map.getLayer("diagnostic")) map.removeLayer("diagnostic");
      if (map.getSource("diagnostic")) map.removeSource("diagnostic");
      return;
    }
    const coordinates = overlay.coordinates as [[number, number], [number, number], [number, number], [number, number]];
    const source = map.getSource("diagnostic") as maplibregl.ImageSource | undefined;
    if (source) source.updateImage({ url: overlay.url, coordinates });
    else {
      map.addSource("diagnostic", { type: "image", url: overlay.url, coordinates });
      map.addLayer({ id: "diagnostic", type: "raster", source: "diagnostic", paint: { "raster-opacity": opacity, "raster-resampling": "nearest", "raster-fade-duration": 0 } }, "study-area-halo");
    }
  }, [map, overlay]);
  useEffect(() => { if (map?.getLayer("diagnostic")) map.setPaintProperty("diagnostic", "raster-opacity", opacity); }, [map, opacity, overlay]);

  const b = aoi ? collectionBounds(aoi) : null;
  return <>
    <div className="map-toolbar">
      <span>{extentOnly ? "Outline = earliest-year raster extent" : "Green outline = selected boundary"}</span>
      <div><button type="button" disabled={!aoi || !map} onClick={() => focusRef.current()}>Locate study area</button>
        <button type="button" disabled={!aoi || !map} onClick={() => focusRef.current(true)}>Regional context</button></div>
    </div>
    <div className="map-frame">
      <div ref={containerRef} className="map-canvas" aria-label={`Interactive study-area map: ${label}`} />
      <div className="map-layer-badge"><span className="layer-swatch" />{overlay?.label ?? (aoi ? label : "No study area selected")}</div>
      <div className={`map-load-state ${error || mapError ? "error" : ""}`} role="status">
        {error || mapError || (loading ? "Reading study-area boundary…" : !aoi ? "Select a GeoTIFF or upload an AOI" : layerReady ? "Boundary layer ready" : "Drawing selected boundary…")}
      </div>
    </div>
    <p className="map-coordinate-note">{b ? `${b.south.toFixed(4)}° to ${b.north.toFixed(4)}° latitude · ${b.west.toFixed(4)}° to ${b.east.toFixed(4)}° longitude` : "Your uploaded AOI takes priority over the raster extent."}
      {basemapError && " · Some background tiles are unavailable; the boundary and analysis remain independent."}</p>
  </>;
}
