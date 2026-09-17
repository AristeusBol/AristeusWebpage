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
      exc: { type: 'geojson', data: { type: 'FeatureCollection', features: [] } },
      marca: { type: 'geojson', data: { type: 'FeatureCollection', features: [] } },
    },
    layers: [
      { id: 'esri', type: 'raster', source: 'esri' },
      { id: 'exc-fill', type: 'fill', source: 'exc', paint: { 'fill-color': '#dc2626', 'fill-opacity': 0.35 } },
      { id: 'exc-line', type: 'line', source: 'exc', paint: { 'line-color': '#fecaca', 'line-width': 1.5, 'line-dasharray': [3, 2] } },
      { id: 'pot-casing', type: 'line', source: 'pot', paint: { 'line-color': '#052e16', 'line-width': 5, 'line-opacity': 0.9 } },
      { id: 'pot-line', type: 'line', source: 'pot', paint: { 'line-color': '#ffffff', 'line-width': 2 } },
      {
        id: 'pot-label', type: 'symbol', source: 'pot',
        layout: { 'text-field': ['get', 'nombre'], 'text-size': 13, 'text-allow-overlap': true },
        paint: { 'text-color': '#ffffff', 'text-halo-color': 'rgba(0,0,0,0.7)', 'text-halo-width': 1.5 },
      },
      { id: 'marca', type: 'circle', source: 'marca', paint: { 'circle-radius': 8, 'circle-color': '#f59e0b', 'circle-stroke-color': '#fff', 'circle-stroke-width': 2 } },
    ],
  } as StyleSpecification;
}

/** Mini-mapa satelital para marcar el punto exacto de la foto dentro del potrero. */
export default function MapaPunto({ features, punto, onPunto }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<Map | null>(null);
  const cbRef = useRef(onPunto);
  useEffect(() => { cbRef.current = onPunto; });

  useEffect(() => {
    if (!ref.current || mapRef.current) return;
    const map = new Map({ container: ref.current, style: buildStyle(), center: [-61.048, -15.955], zoom: 13 });
    map.addControl(new NavigationControl(), 'top-right');
    map.on('click', (e) => cbRef.current(e.lngLat.lat, e.lngLat.lng));
    mapRef.current = map;
    return () => { map.remove(); mapRef.current = null; };
  }, []);

  // Encuadrar + dibujar potrero/exclusiones al cambiar de potrero.
  // Con reintento en 'load': los datos suelen llegar antes que el estilo.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const pot = features.find((f) => f.properties.tipo === 'potrero_base');
    const potFc = { type: 'FeatureCollection', features: features.filter((f) => f.properties.tipo !== 'exclusion') };
    const excFc = { type: 'FeatureCollection', features: features.filter((f) => f.properties.tipo === 'exclusion') };
    const aplicar = () => {
      const srcPot = map.getSource('pot') as GeoJSONSource | undefined;
      const srcExc = map.getSource('exc') as GeoJSONSource | undefined;
      if (!srcPot || !srcExc) return;
      void srcPot.setData(potFc as never);
      void srcExc.setData(excFc as never);
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
    };
    try {
      aplicar();
    } catch {
      map.once('load', aplicar);
    }
    if (!map.getSource('pot')) map.once('load', aplicar);
  }, [features]);

  // Dibujar la marca del punto (con el mismo reintento).
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const aplicar = () => {
      const src = map.getSource('marca') as GeoJSONSource | undefined;
      if (!src) return;
      void src.setData({
        type: 'FeatureCollection',
        features: punto
          ? [{ type: 'Feature', geometry: { type: 'Point', coordinates: [punto.lon, punto.lat] }, properties: {} }]
          : [],
      });
    };
    try {
      aplicar();
    } catch {
      map.once('load', aplicar);
    }
    if (!map.getSource('marca')) map.once('load', aplicar);
  }, [punto]);

  return <div ref={ref} className="map-container calib-map" />;
}
