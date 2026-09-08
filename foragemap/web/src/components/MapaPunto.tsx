import { useEffect, useRef } from 'react';
import { Map, NavigationControl, type GeoJSONSource, type StyleSpecification } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import type { PotreroDetalleFeature } from '../lib/api';

interface Props {
  features: PotreroDetalleFeature[];
  punto: { lat: number; lon: number } | null;
  onPunto: (lat: number, lon: number) => void;
}

function buildStyle(): StyleSpecification {
  return {
    version: 8,
    sources: {
      esri: {
        type: 'raster',
        tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'],
        tileSize: 256,
        attribution: 'Imágenes © Esri World Imagery',
      },
      pot: { type: 'geojson', data: { type: 'FeatureCollection', features: [] } },
      marca: { type: 'geojson', data: { type: 'FeatureCollection', features: [] } },
    },
    layers: [
      { id: 'esri', type: 'raster', source: 'esri' },
      { id: 'pot-fill', type: 'fill', source: 'pot', paint: { 'fill-color': '#22c55e', 'fill-opacity': 0.15 } },
      { id: 'pot-line', type: 'line', source: 'pot', paint: { 'line-color': '#22c55e', 'line-width': 2 } },
      { id: 'marca', type: 'circle', source: 'marca', paint: { 'circle-radius': 8, 'circle-color': '#f59e0b', 'circle-stroke-color': '#fff', 'circle-stroke-width': 2 } },
    ],
  } as StyleSpecification;
}

/** Mini-mapa satelital para marcar el punto exacto de la foto dentro del potrero. */
export default function MapaPunto({ features, punto, onPunto }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<Map | null>(null);
  const cbRef = useRef(onPunto);
  cbRef.current = onPunto;

  useEffect(() => {
    if (!ref.current || mapRef.current) return;
    const map = new Map({ container: ref.current, style: buildStyle(), center: [-61.048, -15.955], zoom: 13 });
    map.addControl(new NavigationControl(), 'top-right');
    map.on('click', (e) => cbRef.current(e.lngLat.lat, e.lngLat.lng));
    mapRef.current = map;
    return () => { map.remove(); mapRef.current = null; };
  }, []);

  // Encuadrar + dibujar potrero/exclusiones al cambiar de potrero
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const pot = features.find((f) => f.properties.tipo === 'potrero_base');
    const src = map.getSource('pot') as GeoJSONSource | undefined;
    if (src) {
      void src.setData({ type: 'FeatureCollection', features: features as never[] });
    }
    if (pot) {
      const coords: number[][] = [];
      const walk = (c: unknown): void => {
        if (Array.isArray(c) && typeof c[0] === 'number') { coords.push(c as number[]); return; }
        if (Array.isArray(c)) c.forEach(walk);
      };
      walk((pot.geometry as { coordinates: unknown }).coordinates);
      if (coords.length > 0) {
        const xs = coords.map((c) => c[0]);
        const ys = coords.map((c) => c[1]);
        map.fitBounds([[Math.min(...xs), Math.min(...ys)], [Math.max(...xs), Math.max(...ys)]], { padding: 40, maxZoom: 17 });
      }
    }
  }, [features]);

  // Dibujar la marca del punto
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const src = map.getSource('marca') as GeoJSONSource | undefined;
    if (src) {
      void src.setData({
        type: 'FeatureCollection',
        features: punto
          ? [{ type: 'Feature', geometry: { type: 'Point', coordinates: [punto.lon, punto.lat] }, properties: {} }]
          : [],
      });
    }
  }, [punto]);

  return <div ref={ref} className="map-container calib-map" />;
}
