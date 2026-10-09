import {
  Map,
  config as maplibreConfig,
  type RequestParameters,
  type StyleSpecification,
} from 'maplibre-gl';
import type { Position } from 'geojson';
import { getToken, type TipoDensidad } from './api';
import { uiPalette } from '../hooks/useUiPalette';

export type BBox = [[number, number], [number, number]];

/** Bounding box de coordenadas GeoJSON arbitrarias (Polygon/MultiPolygon/colecciones). */
export function bboxDe(coords: unknown): BBox | null {
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

/** Bounding box combinado de varias geometrías (se pasa `geometry.coordinates` de cada feature). */
export function bboxCombinado(listasDeCoords: unknown[]): BBox | null {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const coords of listasDeCoords) {
    const bb = bboxDe(coords);
    if (!bb) continue;
    minX = Math.min(minX, bb[0][0]); minY = Math.min(minY, bb[0][1]);
    maxX = Math.max(maxX, bb[1][0]); maxY = Math.max(maxY, bb[1][1]);
  }
  return minX === Infinity ? null : [[minX, minY], [maxX, maxY]];
}

/** Encuadra el mapa a las geometrías dadas (sin-op si están vacías). */
export function encuadrar(map: Map, listasDeCoords: unknown[], maxZoom = 15): void {
  const bb = bboxCombinado(listasDeCoords);
  if (bb) map.fitBounds(bb, { padding: 40, maxZoom });
}

export const ESRI_TILES = [
  'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
];
export const ESRI_ATTR = 'Imágenes © Esri World Imagery — Maxar, Earthstar Geographics';

export const INITIAL_CENTER: [number, number] = [-61.048, -15.955];
export const INITIAL_ZOOM = 13;

export const API_URL = ((import.meta.env.VITE_API_URL as string | undefined) ?? '').replace(/\/$/, '');

/** Worker de maplibre-gl: el bundle resuelve `./maplibre-gl-worker.mjs`
 *  relativo al chunk, que Vite no emite (caía al fallback SPA del index y
 *  el dispatcher nunca iniciaba: sin bordes ni densidad, sin errores).
 *  Se sirven copias fijas desde `public/` (deben coincidir con la versión
 *  instalada de maplibre-gl; el worker importa `./maplibre-gl-shared.mjs`
 *  como hermano) y se apunta WORKER_URL ahí. */
maplibreConfig.WORKER_URL = `${import.meta.env.BASE_URL}maplibre-gl-worker.mjs`;

/** Único modo: satélite Esri (el modo calles no existe). */
export function buildStyleEsri(): StyleSpecification {
  return {
    version: 8,
    glyphs: 'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf',
    sources: {
      'esri-sat': { type: 'raster', tiles: ESRI_TILES, tileSize: 256, maxzoom: 19, attribution: ESRI_ATTR },
    },
    layers: [
      { id: 'bg', type: 'background', paint: { 'background-color': uiPalette().mapBg } },
      { id: 'satelite', type: 'raster', source: 'esri-sat', paint: { 'raster-opacity': 1 } },
    ],
  };
}

/** URL de tiles MVT de densidad. `uid` solo rompe el caché entre cuentas
 *  (el backend lo ignora; el auth viaja en el header vía transformRequest). */
export function tilesUrl(finca: string, fecha: string, tipo: TipoDensidad, uid: number): string {
  return `${API_URL}/api/mapa/tiles/{z}/{x}/{y}.pbf?finca=${encodeURIComponent(finca)}&fecha=${encodeURIComponent(fecha)}&tipo_densidad=${tipo}&uid=${uid}`;
}

/** Inyecta el JWT en los tiles propios; el resto de URLs pasa intacto. */
export function transformRequestTiles(url: string): RequestParameters {
  if (url.includes('/api/mapa/tiles/')) {
    const token = getToken();
    return { url, headers: token ? { Authorization: `Bearer ${token}` } : {} };
  }
  return { url };
}
