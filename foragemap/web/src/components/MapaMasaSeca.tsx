import { useEffect, useRef, useState } from 'react';
import {
  Map, NavigationControl, ScaleControl,
  type FilterSpecification, type GeoJSONSource, type RequestParameters,
  type StyleSpecification, type VectorTileSource,
} from 'maplibre-gl';
import type { FeatureCollection, MultiPolygon, Polygon, Position } from 'geojson';
import 'maplibre-gl/dist/maplibre-gl.css';
import { getToken, type PotreroProps, type TipoDensidad } from '../lib/api';
import { rampaMapLibre } from '../lib/masaSeca';

export interface PotreroFeature {
  type: 'Feature';
  geometry: Polygon | MultiPolygon;
  properties: PotreroProps;
}

export interface ExclusionOverlayFeature {
  type: 'Feature';
  geometry: Polygon | MultiPolygon;
  properties: { id: number; nombre?: string; etiqueta?: string; [k: string]: unknown };
}

interface Props {
  features: PotreroFeature[];
  selectedId: number | null;
  onSelect: (id: number | null) => void;
  finca: string;
  fecha: string;
  tipo: TipoDensidad;
  onTipo: (t: TipoDensidad) => void;
  /** Zonas de exclusión: ya recortadas en el tile, acá solo overlay neutro. */
  exclusiones?: ExclusionOverlayFeature[];
  /** Id del usuario (cache-buster: la URL del tile es igual entre cuentas,
      el auth va en el header y MapLibre cachea por URL). */
  uid: number;
  /** Al incrementarse, encuadra el lote seleccionado (búsqueda). */
  focusSignal: number;
}

type BBox = [[number, number], [number, number]];

function bboxDe(coords: unknown): BBox | null {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  const walk = (c: unknown): void => {
    if (Array.isArray(c) && typeof c[0] === 'number') {
      const [x, y] = c as Position;
      if (x < minX) minX = x;
      if (y < minY) minY = y;
      if (x > maxX) maxX = x;
      if (y > maxY) maxY = y;
      return;
    }
    if (Array.isArray(c)) c.forEach(walk);
  };
  walk(coords);
  return minX === Infinity ? null : [[minX, minY], [maxX, maxY]];
}

function bboxFeatures(feats: PotreroFeature[]): BBox | null {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const f of feats) {
    const bb = bboxDe(f.geometry.coordinates);
    if (!bb) continue;
    minX = Math.min(minX, bb[0][0]); minY = Math.min(minY, bb[0][1]);
    maxX = Math.max(maxX, bb[1][0]); maxY = Math.max(maxY, bb[1][1]);
  }
  return minX === Infinity ? null : [[minX, minY], [maxX, maxY]];
}

// Rampa de densidad (g/m²): rojo (poco) → verde (mucho).
// Fuente única en lib/masaSeca.ts.
// Se mantiene RAMPA_PUNTOS como alias plano para compatibilidad.
export const RAMPA_PUNTOS = [0, '#dc2626', 15, '#f97316', 30, '#fb923c', 45, '#fbbf24', 60, '#facc15', 75, '#a3e635', 90, '#22c55e', 105, '#16a34a', 120, '#15803d'] as const;

const ESRI_TILES = [
  'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
];
const ESRI_ATTR = 'Imágenes © Esri World Imagery — Maxar, Earthstar Geographics';

const INITIAL_CENTER: [number, number] = [-61.048, -15.955];
const INITIAL_ZOOM = 13;

const API_URL = ((import.meta.env.VITE_API_URL as string | undefined) ?? '').replace(/\/$/, '');

// Único modo: satélite Esri (el modo calles no existe).
function buildStyle(): StyleSpecification {
  return {
    version: 8,
    glyphs: 'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf',
    sources: {
      'esri-sat': { type: 'raster', tiles: ESRI_TILES, tileSize: 256, maxzoom: 19, attribution: ESRI_ATTR },
    },
    layers: [
      { id: 'bg', type: 'background', paint: { 'background-color': '#0b1f0b' } },
      { id: 'satelite', type: 'raster', source: 'esri-sat', paint: { 'raster-opacity': 1 } },
    ],
  };
}

export default function MapaMasaSeca({ features, selectedId, onSelect, finca, fecha, tipo, onTipo, exclusiones = [], focusSignal, uid }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<Map | null>(null);
  const dataRef = useRef<PotreroFeature[]>(features);
  const excRef = useRef<ExclusionOverlayFeature[]>(exclusiones);
  const selRef = useRef<number | null>(selectedId);
  const filtroRef = useRef({ finca, fecha, tipo, uid });
  const onSelectRef = useRef(onSelect);
  const healTries = useRef(0);
  const healKey = useRef('');
  const lastTilesRef = useRef<string | null>(null);
  const [status, setStatus] = useState<'cargando' | 'listo'>('cargando');
  const [mapError, setMapError] = useState<string | null>(null);

  dataRef.current = features;
  excRef.current = exclusiones;
  selRef.current = selectedId;
  onSelectRef.current = onSelect;
  filtroRef.current = { finca, fecha, tipo, uid };

  // Sincroniza fuentes y capas SIN ciclo remove/add: si la capa existe se
  // actualiza con setData/setFilter/setTiles (no pierde estado ni orden).
  // Orden de dibujo: fill → densidad → exclusiones (neutro) → casing → línea → selección → hover → etiquetas.
  const syncCapas = (map: Map) => {
    const { finca: f, fecha: fe, tipo: t, uid: u } = filtroRef.current;
    const fc = { type: 'FeatureCollection', features: dataRef.current } as FeatureCollection;
    const sel = ['==', ['get', 'id'], selRef.current ?? -1] as FilterSpecification;
    try {
      const pot = map.getSource('potreros') as GeoJSONSource | undefined;
      if (!map.getLayer('potreros-fill')) {
        if (!pot) map.addSource('potreros', { type: 'geojson', data: fc });
        else pot.setData(fc);
        map.addLayer({
          id: 'potreros-fill',
          type: 'fill',
          source: 'potreros',
          // Sin relleno de color: el dato siempre se ve en modo puntos.
          // El fill transparente mantiene el clic por potrero.
          paint: { 'fill-color': '#ffffff', 'fill-opacity': 0 },
        });
        map.addLayer({
          id: 'potreros-casing',
          type: 'line',
          source: 'potreros',
        paint: { 'line-color': '#052e16', 'line-width': 3, 'line-opacity': 0.9 },
      });
      map.addLayer({
        id: 'potreros-line',
        type: 'line',
        source: 'potreros',
        paint: { 'line-color': '#ffffff', 'line-width': 1.5, 'line-opacity': 1 },
      });
        map.addLayer({
          id: 'potreros-sel-fill',
          type: 'fill',
          source: 'potreros',
          filter: sel,
          paint: { 'fill-color': '#ffffff', 'fill-opacity': 0.18 },
        });
        map.addLayer({
          id: 'potreros-sel',
          type: 'line',
          source: 'potreros',
          filter: sel,
          paint: { 'line-color': '#facc15', 'line-width': 3, 'line-opacity': 1 },
        });
        map.addLayer({
          id: 'potreros-hover',
          type: 'line',
          source: 'potreros',
          filter: ['==', ['get', 'id'], -1] as FilterSpecification,
          paint: { 'line-color': '#ffffff', 'line-width': 3, 'line-opacity': 0.9 },
        });
        map.addLayer({
          id: 'potreros-label',
          type: 'symbol',
          source: 'potreros',
          layout: {
            'text-field': ['get', 'etiqueta'],
            'text-size': 12,
            'text-allow-overlap': true,
          },
          paint: {
            'text-color': '#ffffff',
            'text-halo-color': 'rgba(0,0,0,0.65)',
            'text-halo-width': 1.5,
          },
        });
      } else {
        pot?.setData(fc);
        if (map.getLayer('potreros-sel')) map.setFilter('potreros-sel', sel);
        if (map.getLayer('potreros-sel-fill')) map.setFilter('potreros-sel-fill', sel);
      }

      // Densidad como superficie continua (celdas Voronoi del backend):
      // SIEMPRE visible, DEBAJO de bordes y etiquetas. Al ser polígonos
      // recortados por potrero no quedan huecos al hacer zoom.
      if (f && fe) {
        // `uid` solo rompe el caché de tiles entre cuentas (el backend lo
        // ignora; el auth viaja en el header vía transformRequest).
        const tiles = [`${API_URL}/api/mapa/tiles/{z}/{x}/{y}.pbf?finca=${encodeURIComponent(f)}&fecha=${encodeURIComponent(fe)}&tipo_densidad=${t}&uid=${u}`];
        const dex = map.getSource('densidad') as VectorTileSource | undefined;
        // Migración desde la capa vieja de puntos (si quedó en un mapa vivo).
        if (map.getLayer('densidad-pts')) map.removeLayer('densidad-pts');
        if (!map.getLayer('densidad-fill')) {
          if (!dex) map.addSource('densidad', { type: 'vector', tiles, minzoom: 0, maxzoom: 22 });
          else dex.setTiles(tiles);
          lastTilesRef.current = tiles[0];
          map.addLayer(
            {
              id: 'densidad-fill',
              type: 'fill',
              source: 'densidad',
              'source-layer': 'densidad',
              paint: {
                'fill-color': ['interpolate', ['linear'], ['to-number', ['get', 'valor']], ...rampaMapLibre()],
                'fill-opacity': 0.62,
                'fill-outline-color': 'rgba(0,0,0,0)',
                // Sin antialias: con relleno translúcido, el suavizado de bordes
                // oscurecía las costuras entre tiles al hacer zoom.
                'fill-antialias': false,
              },
            },
            'potreros-casing',
          );
        } else if (lastTilesRef.current !== tiles[0]) {
          // Solo recargar si cambió finca/fecha/tipo: si no, cada sync
          // (selección, heal) re-descargaría todos los tiles.
          dex?.setTiles(tiles);
          lastTilesRef.current = tiles[0];
        }
      } else {
        // Sin finca/fecha no hay densidad: retirar tiles anteriores.
        lastTilesRef.current = null;
        if (map.getLayer('densidad-fill')) map.removeLayer('densidad-fill');
        if (map.getSource('densidad')) map.removeSource('densidad');
      }

      // Exclusiones: máscara del mapa de color — solo visible con finca+fecha
      // (densidad activa). El tile ya viene recortado (hueco = satélite);
      // acá solo overlay neutro oscuro para que se lea como "sin forraje".
      // Debajo de bordes/etiquetas, encima de la densidad.
      if (f && fe && excRef.current.length > 0) {
        const fcExc = { type: 'FeatureCollection', features: excRef.current } as FeatureCollection;
        const exc = map.getSource('exclusiones') as GeoJSONSource | undefined;
        const before = map.getLayer('potreros-casing') ? 'potreros-casing' : undefined;
        if (!map.getLayer('exclusiones-fill')) {
          if (!exc) map.addSource('exclusiones', { type: 'geojson', data: fcExc });
          else exc.setData(fcExc);
          map.addLayer(
            {
              id: 'exclusiones-fill',
              type: 'fill',
              source: 'exclusiones',
              paint: { 'fill-color': '#111827', 'fill-opacity': 0.45 },
            },
            before,
          );
          map.addLayer(
            {
              id: 'exclusiones-line',
              type: 'line',
              source: 'exclusiones',
              paint: { 'line-color': '#e5e7eb', 'line-width': 1.5, 'line-dasharray': [3, 2], 'line-opacity': 0.9 },
            },
            before,
          );
          map.addLayer(
            {
              id: 'exclusiones-label',
              type: 'symbol',
              source: 'exclusiones',
              layout: { 'text-field': ['get', 'etiqueta'], 'text-size': 11, 'text-allow-overlap': true },
              paint: { 'text-color': '#e5e7eb', 'text-halo-color': 'rgba(0,0,0,0.7)', 'text-halo-width': 1.5 },
            },
            before,
          );
        } else {
          exc?.setData(fcExc);
        }
      } else {
        // Sin mapa de color no hay nada que enmascarar: retirar el overlay.
        for (const lid of ['exclusiones-label', 'exclusiones-line', 'exclusiones-fill']) {
          if (map.getLayer(lid)) map.removeLayer(lid);
        }
        if (map.getSource('exclusiones')) map.removeSource('exclusiones');
      }
    } catch (e) {
      setMapError(e instanceof Error ? e.message : 'No se pudieron agregar las capas');
    }
  };

  const fitAll = (map: Map) => {
    const bb = bboxFeatures(dataRef.current);
    if (bb) map.fitBounds(bb, { padding: 40, maxZoom: 15 });
  };

  // Crear mapa una sola vez
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    let cancelled = false;
    let map: Map | null = null;
    try {
      map = new Map({
        container: containerRef.current,
        style: buildStyle(),
        center: INITIAL_CENTER,
        zoom: INITIAL_ZOOM,
        attributionControl: { compact: true },
        transformRequest: (url: string): RequestParameters => {
          if (url.includes('/api/mapa/tiles/')) {
            const token = getToken();
            return { url, headers: token ? { Authorization: `Bearer ${token}` } : {} };
          }
          return { url };
        },
      });
    } catch (e) {
      setMapError(e instanceof Error ? e.message : 'No se pudo crear el mapa (¿WebGL disponible?)');
      return;
    }
    map.addControl(new NavigationControl({ visualizePitch: false }), 'top-right');
    map.addControl(new ScaleControl({ maxWidth: 120, unit: 'metric' }), 'bottom-right');
    map.on('error', (e) => {
      const msg = (e.error as Error | undefined)?.message ?? String(e.error ?? 'error del mapa');
      if (!/tile|404|empty/i.test(msg)) setMapError(msg);
    });
    map.on('load', () => {
      if (cancelled) return;
      setStatus('listo');
      syncCapas(map as Map);
      fitAll(map as Map);
    });
    map.on('click', 'potreros-fill', (e) => {
      const f = e.features?.[0];
      const id = f?.properties?.id;
      if (typeof id === 'number') onSelectRef.current(id);
    });
    map.on('mouseenter', 'potreros-fill', () => { map!.getCanvas().style.cursor = 'pointer'; });
    map.on('mousemove', 'potreros-fill', (e) => {
      const id = e.features?.[0]?.properties?.id;
      if (map!.getLayer('potreros-hover')) {
        map!.setFilter('potreros-hover', ['==', ['get', 'id'], typeof id === 'number' ? id : -1] as FilterSpecification);
      }
    });
    map.on('mouseleave', 'potreros-fill', () => {
      map!.getCanvas().style.cursor = '';
      if (map!.getLayer('potreros-hover')) {
        map!.setFilter('potreros-hover', ['==', ['get', 'id'], -1] as FilterSpecification);
      }
    });
    mapRef.current = map;
    // Exponer para diagnóstico (consola del navegador / tests): window.__fmMap
    (window as unknown as { __fmMap?: Map }).__fmMap = map;
    return () => {
      cancelled = true;
      map?.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Refrescar cuando cambian datos / selección / filtros.
  // NOTA: no usar isStyleLoaded() como compuerta — puede dar falso negativo
  // con el estilo ya cargado ('load' no se repite y quedaría atascado).
  // Se intenta directo y solo se difiere a 'load' si lanza excepción.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || status !== 'listo') return;
    let cancelled = false;
    const aplicar = () => {
      if (cancelled) return;
      syncCapas(map);
      fitAll(map);
    };
    try {
      aplicar();
    } catch {
      map.once('load', aplicar);
      return () => { cancelled = true; };
    }
    // Auto-reparación con reintentos acotados: si la fuente tiene datos pero
    // nada se renderiza estando a la vista (estilo que asienta tarde),
    // se re-sincroniza hasta 3 veces (una por idle).
    const key = `${filtroRef.current.uid}|${finca}|${fecha}|${features.length}`;
    if (healKey.current !== key) {
      healKey.current = key;
      healTries.current = 0;
    }
    const onIdle = () => {
      if (cancelled || dataRef.current.length === 0 || healTries.current >= 3) return;
      try {
        const bb = bboxFeatures(dataRef.current);
        const v = map.getBounds();
        const enVista = !bb || (bb[1][0] >= v.getWest() && bb[0][0] <= v.getEast() && bb[1][1] >= v.getSouth() && bb[0][1] <= v.getNorth());
        if (enVista && map.queryRenderedFeatures({ layers: ['potreros-fill'] }).length === 0) {
          healTries.current += 1;
          syncCapas(map);
        }
      } catch { /* estilo aún no listo */ }
    };
    map.on('idle', onIdle);
    return () => { cancelled = true; map.off('idle', onIdle); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [features, exclusiones, selectedId, finca, fecha, tipo, uid, status]);

  // Re-encuadrar al cambiar de finca/fecha
  useEffect(() => {
    const map = mapRef.current;
    if (map && status === 'listo' && features.length) fitAll(map);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [finca, fecha]);

  // Enfocar el lote seleccionado (búsqueda del topbar)
  useEffect(() => {
    const map = mapRef.current;
    if (!map || status !== 'listo' || focusSignal === 0) return;
    const feat = dataRef.current.find((f) => f.properties.id === selRef.current);
    if (!feat) return;
    const bb = bboxDe(feat.geometry.coordinates);
    if (bb) map.fitBounds(bb, { padding: 60, maxZoom: 15 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusSignal]);

  return (
    <div style={{ position: 'relative', height: '100%' }}>
      <div className="map-submenu" role="group" aria-label="Tipo de densidad">
        {(['verde', 'muerta', 'total'] as TipoDensidad[]).map((t) => (
          <button
            key={t}
            type="button"
            className={tipo === t ? 'active' : ''}
            onClick={() => onTipo(t)}
          >
            {t[0].toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      <div ref={containerRef} className="map-container tall" aria-label="Mapa de masa seca por lote" />

      {status === 'cargando' && <div className="map-overlay">Cargando mapa…</div>}
      {mapError && <div className="map-overlay error">Error del mapa: {mapError}</div>}
    </div>
  );
}
