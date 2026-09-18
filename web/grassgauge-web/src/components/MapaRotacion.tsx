import { useEffect, useRef, useState } from 'react';
import {
  Map as MapLibre, Marker, NavigationControl, ScaleControl,
  type FilterSpecification, type GeoJSONSource,
} from 'maplibre-gl';
import type { FeatureCollection, MultiPolygon, Position, Polygon } from 'geojson';
import 'maplibre-gl/dist/maplibre-gl.css';
import {
  INITIAL_CENTER, INITIAL_ZOOM, bboxDe, buildStyleEsri,
  encuadrar, transformRequestTiles,
} from '../lib/mapCommon';
import type { ExclusionOverlayFeature, PotreroFeature } from './MapaMasaSeca';

export interface MapaRotacionParcelaFeature {
  type: 'Feature';
  geometry: Polygon | MultiPolygon;
  properties: {
    id: number;
    nombre: string;
    finca: string;
    potrero_id: number;
    estado: string;
    area_ha: number | null;
    [k: string]: unknown;
  };
}

/** Datos de un pin de secuencia de trayectoria. */
export interface SecuenciaPin {
  numero: number;
  color: string;
  estado: 'cerrada' | 'vigente' | 'programada';
  cabezas?: number;
}

/** Centroide simple: promedio de bounding box. */
function centroide(coords: Position[][]): [number, number] {
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  for (const ring of coords) {
    for (const [x, y] of ring) {
      if (x < minX) minX = x;
      if (x > maxX) maxX = x;
      if (y < minY) minY = y;
      if (y > maxY) maxY = y;
    }
  }
  return [(minX + maxX) / 2, (minY + maxY) / 2];
}

/** Polígono más grande de una MultiPolygon. */
function polyPrincipal(geo: Polygon | MultiPolygon): Position[][] {
  if (geo.type === 'Polygon') return geo.coordinates;
  return geo.coordinates.reduce((a, b) => {
    const areaA = Math.abs(a[0].reduce((s, p, i, arr) => {
      const nxt = arr[(i + 1) % arr.length];
      return s + p[0] * nxt[1] - nxt[0] * p[1];
    }, 0));
    const areaB = Math.abs(b[0].reduce((s, p, i, arr) => {
      const nxt = arr[(i + 1) % arr.length];
      return s + p[0] * nxt[1] - nxt[0] * p[1];
    }, 0));
    return areaA > areaB ? a : b;
  });
}

/** SVG de pin normal: gota con borde del color del rodeo, interior blanco, círculo coloreado con número. */
function pinSvg(color: string, numero: number): string {
  return `<svg width="30" height="38" viewBox="-1 -1 30 38" xmlns="http://www.w3.org/2000/svg">
  <path d="M14 0C6.268 0 0 6.268 0 14c0 10.5 14 22 14 22s14-11.5 14-22C28 6.268 21.732 0 14 0z" fill="${color}"/>
  <path d="M14 3.5C8.2 3.5 3.5 8.2 3.5 14c0 9 10.5 18.5 10.5 18.5s10.5-9.5 10.5-18.5C24.5 8.2 19.8 3.5 14 3.5z" fill="white"/>
  <circle cx="14" cy="13" r="8" fill="${color}"/>
  <text x="14" y="17" text-anchor="middle" fill="white" font-size="12" font-weight="700" font-family="system-ui,sans-serif">${numero}</text>
</svg>`;
}

/** Logo de vaca (cabeza de frente, disenada para legibilidad en pequeno). */
function vaquitaSvg(color: string): string {
  return `<g>
    <path d="M5.2 0.6 L7.2 3.4 L4.9 3.2 L4.1 1.2 Z" fill="${color}"/>
    <path d="M14.8 0.6 L12.8 3.4 L15.1 3.2 L15.9 1.2 Z" fill="${color}"/>
    <ellipse cx="3" cy="6.2" rx="2.4" ry="1.7" transform="rotate(-22 3 6.2)" fill="${color}"/>
    <ellipse cx="17" cy="6.2" rx="2.4" ry="1.7" transform="rotate(22 17 6.2)" fill="${color}"/>
    <path d="M10 2.6 C5.7 2.6 4.2 6 4.7 9.4 C5.1 12.2 6.6 13.8 10 13.8 C13.4 13.8 14.9 12.2 15.3 9.4 C15.8 6 14.3 2.6 10 2.6 Z" fill="${color}"/>
    <ellipse cx="7.4" cy="8" rx="1" ry="1.3" fill="white"/>
    <ellipse cx="12.6" cy="8" rx="1" ry="1.3" fill="white"/>
    <rect x="6.4" y="10.2" width="7.2" height="3.9" rx="1.95" fill="white"/>
    <ellipse cx="8.2" cy="12.1" rx="0.55" ry="0.7" fill="${color}"/>
    <ellipse cx="11.8" cy="12.1" rx="0.55" ry="0.7" fill="${color}"/>
  </g>`;
}

/** SVG de pin activo: gota del color del lote con círculo blanco y número. */
function pinActivoSvg(color: string, numero: number): string {
  return `<svg width="30" height="38" viewBox="-1 -1 30 38" xmlns="http://www.w3.org/2000/svg">
  <path d="M14 0C6.268 0 0 6.268 0 14c0 10.5 14 22 14 22s14-11.5 14-22C28 6.268 21.732 0 14 0z" fill="${color}"/>
  <circle cx="14" cy="13" r="9" fill="white"/>
  <text x="14" y="17" text-anchor="middle" fill="${color}" font-size="13" font-weight="700" font-family="system-ui,sans-serif">${numero}</text>
</svg>`;
}

/** PRNG determinista (mulberry32): las vaquitas no saltan entre renders. */
function prng(semilla: number): () => number {
  let a = semilla >>> 0;
  return () => {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Punto dentro del anillo (ray casting). */
function dentroDe([x, y]: [number, number], anillo: Position[]): boolean {
  let dentro = false;
  for (let i = 0, j = anillo.length - 1; i < anillo.length; j = i++) {
    const [xi, yi] = anillo[i];
    const [xj, yj] = anillo[j];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) dentro = !dentro;
  }
  return dentro;
}

/** N puntos desparramados dentro del anillo, cerca del centroide. */
function puntosEnParcela(anillo: Position[], centro: [number, number], n: number, semilla: number): [number, number][] {
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  for (const [x, y] of anillo) {
    if (x < minX) minX = x;
    if (x > maxX) maxX = x;
    if (y < minY) minY = y;
    if (y > maxY) maxY = y;
  }
  const diag = Math.hypot(maxX - minX, maxY - minY);
  if (!(diag > 0)) return [];
  const rnd = prng(semilla);
  const pts: [number, number][] = [];
  let radio = diag * 0.22;
  let intentos = 0;
  while (pts.length < n && radio <= diag * 2) {
    intentos++;
    if (intentos > n * 80) { radio *= 1.6; intentos = 0; }
    const p: [number, number] = [minX + rnd() * (maxX - minX), minY + rnd() * (maxY - minY)];
    if (!dentroDe(p, anillo)) continue;
    if (Math.hypot(p[0] - centro[0], p[1] - centro[1]) > radio) continue;
    pts.push(p);
  }
  return pts;
}

interface Props {
  potreros: PotreroFeature[];
  parcelas: MapaRotacionParcelaFeature[];
  parcelaSeleccionada: number | null;
  onSeleccionarParcela: (id: number | null) => void;
  secuencias?: Map<number, SecuenciaPin>;
  /** Zonas de exclusión: se pintan de blanco sólido (sin forraje). */
  exclusiones?: ExclusionOverlayFeature[];
}

export default function MapaRotacion({
  potreros, parcelas, parcelaSeleccionada, onSeleccionarParcela, secuencias, exclusiones = [],
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibre | null>(null);
  const markersRef = useRef<Marker[]>([]);
  const dataRef = useRef({ potreros, parcelas, parcelaSeleccionada, secuencias, exclusiones });
  const onSelectRef = useRef(onSeleccionarParcela);
  const [status, setStatus] = useState<'cargando' | 'listo'>('cargando');
  const [mapError, setMapError] = useState<string | null>(null);

  dataRef.current = { potreros, parcelas, parcelaSeleccionada, secuencias, exclusiones };
  onSelectRef.current = onSeleccionarParcela;

  const syncCapas = (map: MapLibre) => {
    const d = dataRef.current;

    const fcPot = { type: 'FeatureCollection', features: d.potreros } as FeatureCollection;
    const fcPar: FeatureCollection = {
      type: 'FeatureCollection',
      features: d.parcelas.map((f) => ({
        type: 'Feature',
        geometry: f.geometry,
        properties: { id: f.properties.id, nombre: f.properties.nombre, estado: f.properties.estado },
      })),
    } as unknown as FeatureCollection;

    const selFilter = ['==', ['get', 'id'], d.parcelaSeleccionada ?? -1] as FilterSpecification;

    try {
      const pot = map.getSource('rot-potreros') as GeoJSONSource | undefined;
      if (!map.getLayer('rot-potreros-fill')) {
        if (!pot) map.addSource('rot-potreros', { type: 'geojson', data: fcPot });
        map.addLayer({ id: 'rot-potreros-fill', type: 'fill', source: 'rot-potreros', paint: { 'fill-color': '#233D39', 'fill-opacity': 1 } });
      } else {
        pot?.setData(fcPot);
      }

      const par = map.getSource('rot-parcelas') as GeoJSONSource | undefined;
      if (!map.getLayer('rot-parcelas-fill')) {
        if (!par) map.addSource('rot-parcelas', { type: 'geojson', data: fcPar });
        else par.setData(fcPar);
        map.addLayer({
          id: 'rot-parcelas-fill', type: 'fill', source: 'rot-parcelas',
          paint: {
            'fill-color': [
              'match',
              ['get', 'estado'],
              'critico', '#ef4444',
              'desarrollo', '#facc15',
              'optimo', '#22c55e',
              'maduro', '#8b5cf6',
              'pasado', '#86198f',
              '#9ca3af',
            ],
            'fill-opacity': 0.6,
          },
        });
        map.addLayer({
          id: 'rot-parcelas-line', type: 'line', source: 'rot-parcelas',
          paint: { 'line-color': '#e2e8f0', 'line-width': 1, 'line-opacity': 0.9 },
        });
        map.addLayer({
          id: 'rot-parcelas-sel', type: 'line', source: 'rot-parcelas',
          filter: selFilter,
          paint: { 'line-color': '#22d3ee', 'line-width': 3 },
        });
        map.addLayer({
          id: 'rot-parcelas-label', type: 'symbol', source: 'rot-parcelas', minzoom: 15,
          layout: { 'text-field': ['get', 'nombre'], 'text-size': 11, 'text-allow-overlap': false },
          paint: { 'text-color': '#fefce8', 'text-halo-color': 'rgba(0,0,0,0.7)', 'text-halo-width': 1.5 },
        });
      } else {
        par?.setData(fcPar);
        if (map.getLayer('rot-parcelas-sel')) map.setFilter('rot-parcelas-sel', selFilter);
      }

      if (!map.getLayer('rot-potreros-line')) {
        map.addLayer({ id: 'rot-potreros-line', type: 'line', source: 'rot-potreros', paint: { 'line-color': '#ffffff', 'line-width': 2.5, 'line-opacity': 1 } });
      }
      // Exclusiones: blanco sólido encima de parcelas/potreros, debajo de
      // líneas y etiquetas (igual que en los demás mapas, acá sin overlay).
      const fcExc = { type: 'FeatureCollection', features: d.exclusiones } as FeatureCollection;
      const exc = map.getSource('rot-exclusiones') as GeoJSONSource | undefined;
      if (d.exclusiones.length > 0) {
        if (!map.getLayer('rot-exclusiones-fill')) {
          if (!exc) map.addSource('rot-exclusiones', { type: 'geojson', data: fcExc });
          else exc.setData(fcExc);
          map.addLayer(
            {
              id: 'rot-exclusiones-fill', type: 'fill', source: 'rot-exclusiones',
              paint: { 'fill-color': '#ffffff', 'fill-opacity': 1 },
            },
            map.getLayer('rot-potreros-line') ? 'rot-potreros-line' : undefined,
          );
        } else {
          exc?.setData(fcExc);
        }
      } else {
        if (map.getLayer('rot-exclusiones-fill')) map.removeLayer('rot-exclusiones-fill');
        if (map.getSource('rot-exclusiones')) map.removeSource('rot-exclusiones');
      }
      if (!map.getLayer('rot-potreros-label')) {
        map.addLayer({
          id: 'rot-potreros-label', type: 'symbol', source: 'rot-potreros',
          layout: { 'text-field': ['get', 'nombre'], 'text-size': 12, 'text-allow-overlap': true },
          paint: { 'text-color': '#ffffff', 'text-halo-color': 'rgba(0,0,0,0.65)', 'text-halo-width': 1.5 },
        });
      }
    } catch (e) {
      setMapError(e instanceof Error ? e.message : 'No se pudieron agregar las capas');
    }
  };

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    let cancelled = false;
    let map: MapLibre | null = null;
    try {
      map = new MapLibre({
        container: containerRef.current,
        style: buildStyleEsri(),
        center: INITIAL_CENTER,
        zoom: INITIAL_ZOOM,
        attributionControl: { compact: true },
        transformRequest: transformRequestTiles,
      });
    } catch (e) {
      setMapError(e instanceof Error ? e.message : 'No se pudo crear el mapa');
      return;
    }
    map.addControl(new NavigationControl({ visualizePitch: false }), 'top-right');
    map.addControl(new ScaleControl({ maxWidth: 120, unit: 'metric' }), 'bottom-right');
    map.on('load', () => {
      if (cancelled) return;
      setStatus('listo');
      syncCapas(map as MapLibre);
      const d = dataRef.current;
      const todas = [...d.potreros.map((f) => f.geometry.coordinates), ...d.parcelas.map((f) => f.geometry.coordinates)];
      encuadrar(map as MapLibre, todas);
    });
    map.on('click', 'rot-parcelas-fill', (e) => {
      const id = e.features?.[0]?.properties?.id as number | undefined;
      if (typeof id === 'number') onSelectRef.current(id);
    });
    map.on('mouseenter', 'rot-parcelas-fill', () => { map!.getCanvas().style.cursor = 'pointer'; });
    map.on('mouseleave', 'rot-parcelas-fill', () => { map!.getCanvas().style.cursor = ''; });
    mapRef.current = map;
    return () => {
      cancelled = true;
      for (const m of markersRef.current) m.remove();
      markersRef.current = [];
      map?.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || status !== 'listo') return;
    try {
      syncCapas(map);
    } catch {
      map.once('load', () => syncCapas(map));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [potreros, parcelas, parcelaSeleccionada, exclusiones, status]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || status !== 'listo') return;
    const id = dataRef.current.parcelaSeleccionada;
    if (id == null) return;
    const feat = dataRef.current.parcelas.find((f) => f.properties.id === id);
    if (!feat) return;
    const bb = bboxDe(feat.geometry.coordinates);
    if (bb) map.fitBounds(bb, { padding: 60, maxZoom: 16 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [parcelaSeleccionada, status]);

  /** Sincroniza los markers de secuencia de trayectoria. */
  useEffect(() => {
    const map = mapRef.current;
    if (!map || status !== 'listo') return;

    // Limpiar markers anteriores
    for (const m of markersRef.current) m.remove();
    markersRef.current = [];

    const sec = dataRef.current.secuencias;
    if (!sec || sec.size === 0) return;

    const parcelasMap = new Map(dataRef.current.parcelas.map((p) => [p.properties.id, p]));

    for (const [parcelaId, info] of sec) {
      const feat = parcelasMap.get(parcelaId);
      if (!feat) continue;
      const coords = polyPrincipal(feat.geometry);
      const [lng, lat] = centroide(coords);

      // Vaquitas primero (abajo): desparramadas dentro de la parcela vigente.
      if (info.estado === 'vigente') {
        const n = Math.ceil((info.cabezas ?? 20) / 20);
        const rnd = prng(parcelaId * 31 + 13);
        for (const [vlng, vlat] of puntosEnParcela(coords[0], [lng, lat], n, parcelaId * 1000 + 7)) {
          const rot = Math.round(rnd() * 24 - 12);
          const vel = document.createElement('div');
          vel.className = 'vaca-suelta';
          vel.innerHTML = `<svg width="24" height="18" viewBox="0 0 20 15" xmlns="http://www.w3.org/2000/svg"><g transform="rotate(${rot} 10 7.5)">${vaquitaSvg(info.color)}</g></svg>`;
          markersRef.current.push(
            new Marker({ element: vel, anchor: 'center' }).setLngLat([vlng, vlat]).addTo(map),
          );
        }
      }

      // Pin último (arriba): la punta toca el centroide.
      const el = document.createElement('div');
      el.className = 'pin-trayectoria';
      el.innerHTML = info.estado === 'vigente'
        ? pinActivoSvg(info.color, info.numero)
        : pinSvg(info.color, info.numero);

      const marker = new Marker({ element: el, anchor: 'bottom' })
        .setLngLat([lng, lat])
        .addTo(map);
      markersRef.current.push(marker);
    }

    return () => {
      for (const m of markersRef.current) m.remove();
      markersRef.current = [];
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [secuencias, status]);

  return (
    <div style={{ position: 'relative', height: '100%' }}>
      <div ref={containerRef} className="map-container tall" aria-label="Mapa de trayectorias (potreros y parcelas)" />
      {status === 'cargando' && <div className="map-overlay">Cargando mapa…</div>}
      {mapError && <div className="map-overlay error">Error del mapa: {mapError}</div>}
    </div>
  );
}