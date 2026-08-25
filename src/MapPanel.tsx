import { useEffect, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import type {
  GeoJSONSource,
  GeoJSONSourceSpecification,
  StyleSpecification,
} from "maplibre-gl";
import { collectionBounds } from "./geo";
import type { AoiFeatureCollection } from "./types";

interface MapPanelProps {
  aoi: AoiFeatureCollection | null;
  loading: boolean;
  error: string | null;
}

const baseStyle: StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      minzoom: 0,
      maxzoom: 19,
      attribution: "© OpenStreetMap contributors",
    },
  },
  layers: [{ id: "osm", type: "raster", source: "osm" }],
};

export function MapPanel({ aoi, loading, error }: MapPanelProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [mapLoaded, setMapLoaded] = useState(false);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: baseStyle,
      center: [84.72, 19.38],
      zoom: 8.25,
      minZoom: 5,
      maxZoom: 16,
      attributionControl: false,
      cooperativeGestures: true,
    });

    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.addControl(new maplibregl.ScaleControl({ maxWidth: 120, unit: "metric" }), "bottom-left");
    map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");
    map.on("load", () => setMapLoaded(true));
    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapLoaded || !aoi) return;

    const data = aoi as unknown as GeoJSONSourceSpecification["data"];
    const existingSource = map.getSource("ganjam-aoi") as GeoJSONSource | undefined;

    if (existingSource) {
      existingSource.setData(data);
    } else {
      map.addSource("ganjam-aoi", { type: "geojson", data });
      map.addLayer({
        id: "ganjam-aoi-halo",
        type: "line",
        source: "ganjam-aoi",
        paint: { "line-color": "#ffffff", "line-width": 7, "line-opacity": 0.88 },
      });
      map.addLayer({
        id: "ganjam-aoi-fill",
        type: "fill",
        source: "ganjam-aoi",
        paint: { "fill-color": "#b8df71", "fill-opacity": 0.24 },
      });
      map.addLayer({
        id: "ganjam-aoi-line",
        type: "line",
        source: "ganjam-aoi",
        paint: { "line-color": "#174f43", "line-width": 3 },
      });
      map.on("mouseenter", "ganjam-aoi-fill", () => {
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", "ganjam-aoi-fill", () => {
        map.getCanvas().style.cursor = "";
      });
      map.on("click", "ganjam-aoi-fill", (event: maplibregl.MapMouseEvent) => {
        new maplibregl.Popup({ closeButton: false, offset: 10 })
          .setLngLat(event.lngLat)
          .setHTML(
            "<strong>Ganjam District</strong><br><span>Administrative level 2 boundary · 2021</span>",
          )
          .addTo(map);
      });
    }

    const bounds = collectionBounds(aoi);
    map.fitBounds(
      [
        [bounds.west, bounds.south],
        [bounds.east, bounds.north],
      ],
      { padding: 52, duration: 900, maxZoom: 10 },
    );
  }, [aoi, mapLoaded]);

  return (
    <div className="map-frame">
      <div
        ref={containerRef}
        className="map-canvas"
        aria-label="Interactive map of Ganjam District AOI"
      />
      <div className="map-layer-badge">
        <span className="layer-swatch" />
        Ganjam ADM2 boundary
      </div>
      <div className={`map-load-state ${error ? "error" : ""}`}>
        {error ? error : loading ? "Loading verified AOI…" : "Real boundary loaded"}
      </div>
    </div>
  );
}
