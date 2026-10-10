import { useEffect, useRef, useState } from 'react';
import {
  Map, NavigationControl, ScaleControl,
  type FilterSpecification, type GeoJSONSource, type VectorTileSource,
} from 'maplibre-gl';
import type { FeatureCollection, MultiPolygon, Polygon } from 'geojson';
import 'maplibre-gl/dist/maplibre-gl.css';
import { type PotreroProps, type TipoDensidad } from '../lib/api';
import { degradadoMapLibre } from '../lib/masaSeca';
import { anillosDe, snapClic } from '../lib/snap';
import {
  INITIAL_CENTER, INITIAL_ZOOM, bboxCombinado, buildStyleEsri, encuadrar,
  tilesUrl, transformRequestTiles,
} from '../lib/mapCommon';
import { MAP_CHROME } from '../lib/mapPalette';

export interface PotreroFeature {
  type: 'Feature';
  geometry: Polygon | MultiPolygon;
  properties: PotreroProps;
}

export interface ParcelaMapFeature {
  type: 'Feature';
  geometry: Polygon | MultiPolygon;
  properties: { id: number; nombre: string; etiqueta?: string; [k: string]: unknown };
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
  /** Zonas de exclusión: ya recortadas en el tile, acá solo overlay neutro. */
  exclusiones?: ExclusionOverlayFeature[];
  /** Id del usuario (cache-buster: la URL del tile es igual entre cuentas,
      el auth va en el header y MapLibre cachea por URL). */
  uid: number;
  /** Parcelas (hijas de potreros): solo se dibujan si mostrarParcelas. */
  parcelas?: ParcelaMapFeature[];
  mostrarParcelas?: boolean;
  parcelaSelectedId?: number | null;
  onSelectParcela?: (id: number | null) => void;
  /** Modo dibujo de parcela: clicks suman vértices con imán. */
  dibujando?: boolean;
  vertices?: [number, number][];
  onDibujoClick?: (lngLat: [number, number]) => void;
  onDibujoDobleClick?: () => void;
}

export default function MapaMasaSeca({ features, selectedId, onSelect, finca, fecha, tipo, exclusiones = [], uid, parcelas = [], mostrarParcelas = false, parcelaSelectedId = null, onSelectParcela, dibujando = false, vertices = [], onDibujoClick, onDibujoDobleClick }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const cursorRef = useRef<HTMLDivElement | null>(null);
  const puntoRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<Map | null>(null);
  const dataRef = useRef<PotreroFeature[]>(features);
  const excRef = useRef<ExclusionOverlayFeature[]>(exclusiones);
  const selRef = useRef<number | null>(selectedId);
  const filtroRef = useRef({ finca, fecha, tipo, uid });
  const onSelectRef = useRef(onSelect);
  const parcRef = useRef<ParcelaMapFeature[]>(parcelas);
  const mostrarParcRef = useRef(mostrarParcelas);
  const parcSelRef = useRef<number | null>(parcelaSelectedId);
  const onSelectParcRef = useRef(onSelectParcela);
  const dibRef = useRef({ dibujando, vertices });
  const onDibClickRef = useRef(onDibujoClick);
  const onDibDblRef = useRef(onDibujoDobleClick);
  const healTries = useRef(0);
  const healKey = useRef('');
  const fitKey = useRef('');
  const lastTilesRef = useRef<string | null>(null);
  const [status, setStatus] = useState<'cargando' | 'listo'>('cargando');
  const [mapError, setMapError] = useState<string | null>(null);

  dataRef.current = features;
  excRef.current = exclusiones;
  selRef.current = selectedId;
  onSelectRef.current = onSelect;
  filtroRef.current = { finca, fecha, tipo, uid };
  parcRef.current = parcelas;
  mostrarParcRef.current = mostrarParcelas;
  parcSelRef.current = parcelaSelectedId;
  onSelectParcRef.current = onSelectParcela;
  dibRef.current = { dibujando, vertices };
  onDibClickRef.current = onDibujoClick;
  onDibDblRef.current = onDibujoDobleClick;

  // Sincroniza fuentes y capas SIN ciclo remove/add: si la capa existe se
  // actualiza con setData/setFilter/setTiles (no pierde estado ni orden).
  // Orden de dibujo: fill → densidad → exclusiones (neutro) → casing → línea → selección → hover → etiquetas.
  const syncCapas = (map: Map) => {
    const { finca: f, fecha: fe, tipo: t, uid: u } = filtroRef.current;
    const fc = { type: 'FeatureCollection', features: dataRef.current } as FeatureCollection;
    const sel = ['==', ['get', 'id'], selRef.current ?? -1] as FilterSpecification;
    try {
      // Migración desde el velo blanco de selección (ya no se usa).
      if (map.getLayer('potreros-sel-fill')) map.removeLayer('potreros-sel-fill');
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
          paint: { 'fill-color': MAP_CHROME.potreroFill, 'fill-opacity': 0 },
        });
        map.addLayer({
          id: 'potreros-line',
          type: 'line',
          source: 'potreros',
          paint: { 'line-color': MAP_CHROME.potreroLine, 'line-width': 2.5, 'line-opacity': 1 },
        });
        map.addLayer({
          id: 'potreros-sel-halo',
          type: 'line',
          source: 'potreros',
          filter: sel,
          layout: { 'line-cap': 'round', 'line-join': 'round' },
          paint: { 'line-color': MAP_CHROME.potreroCasing, 'line-width': 5.5, 'line-opacity': 0.6 },
        });
        map.addLayer({
          id: 'potreros-sel',
          type: 'line',
          source: 'potreros',
          filter: sel,
          paint: { 'line-color': MAP_CHROME.seleccionAmarilloLuz, 'line-width': 4, 'line-opacity': 1 },
        });
        map.addLayer({
          id: 'potreros-hover',
          type: 'line',
          source: 'potreros',
          filter: ['==', ['get', 'id'], -1] as FilterSpecification,
          paint: { 'line-color': MAP_CHROME.potreroLine, 'line-width': 3, 'line-opacity': 0.9 },
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
            'text-color': MAP_CHROME.textoSatelite,
            'text-halo-color': MAP_CHROME.halo,
            'text-halo-width': 1.5,
          },
        });
      } else {
        pot?.setData(fc);
        if (map.getLayer('potreros-sel')) map.setFilter('potreros-sel', sel);
        if (map.getLayer('potreros-sel-halo')) map.setFilter('potreros-sel-halo', sel);
      }

      // Densidad como superficie continua (celdas Voronoi del backend):
      // SIEMPRE visible, DEBAJO de bordes y etiquetas. Al ser polígonos
      // recortados por potrero no quedan huecos al hacer zoom.
      if (f && fe) {
        const tiles = [tilesUrl(f, fe, t, u)];
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
                'fill-color': degradadoMapLibre(),
                'fill-opacity': 1,
                'fill-outline-color': 'rgba(0,0,0,0)',
                // Sin antialias: con relleno translúcido, el suavizado de bordes
                // oscurecía las costuras entre tiles al hacer zoom.
                'fill-antialias': false,
              },
            },
            'potreros-line',
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
      // NOTA: en gestión (GestionMapa) las exclusiones van en rojo porque ahí
      // son el objeto editable; acá son solo máscara del dato forrajero.
      if (f && fe && excRef.current.length > 0) {
        const fcExc = { type: 'FeatureCollection', features: excRef.current } as FeatureCollection;
        const exc = map.getSource('exclusiones') as GeoJSONSource | undefined;
        const before = map.getLayer('potreros-line') ? 'potreros-line' : undefined;
        if (!map.getLayer('exclusiones-fill')) {
          if (!exc) map.addSource('exclusiones', { type: 'geojson', data: fcExc });
          else exc.setData(fcExc);
          map.addLayer(
            {
              id: 'exclusiones-fill',
              type: 'fill',
              source: 'exclusiones',
              paint: { 'fill-color': MAP_CHROME.exclusionesOscuro, 'fill-opacity': 0.45 },
            },
            before,
          );
          map.addLayer(
            {
              id: 'exclusiones-line',
              type: 'line',
              source: 'exclusiones',
              paint: { 'line-color': MAP_CHROME.potreroLine, 'line-width': 2.5, 'line-opacity': 1 },
            },
            before,
          );
        } else {
          exc?.setData(fcExc);
        }
      } else {
        // Sin mapa de color no hay nada que enmascarar: retirar el overlay.
        for (const lid of ['exclusiones-line', 'exclusiones-fill']) {
          if (map.getLayer(lid)) map.removeLayer(lid);
        }
        if (map.getSource('exclusiones')) map.removeSource('exclusiones');
      }

      // Parcelas hijas: solo si el toggle está activo. Etiqueta solo con zoom
      // (minzoom 14) para no tapar el mapa con A1_1, A1_2...
      const selPar = ['==', ['get', 'id'], parcSelRef.current ?? -1] as FilterSpecification;
      const noSelPar = ['!=', ['get', 'id'], parcSelRef.current ?? -1] as FilterSpecification;
      if (mostrarParcRef.current && parcRef.current.length > 0) {
        const fcPar = { type: 'FeatureCollection', features: parcRef.current } as FeatureCollection;
        const par = map.getSource('parcelas') as GeoJSONSource | undefined;
        const beforePar = map.getLayer('potreros-line') ? 'potreros-line' : undefined;
        if (!map.getLayer('parcelas-fill')) {
          if (!par) map.addSource('parcelas', { type: 'geojson', data: fcPar });
          else par.setData(fcPar);
          map.addLayer({ id: 'parcelas-fill', type: 'fill', source: 'parcelas', paint: { 'fill-color': MAP_CHROME.seleccionAmarillo, 'fill-opacity': 0 } }, beforePar);
          map.addLayer({ id: 'parcelas-line', type: 'line', source: 'parcelas', filter: noSelPar, paint: { 'line-color': MAP_CHROME.parcelaLinea, 'line-width': 1, 'line-opacity': 0.9 } }, beforePar);
          map.addLayer({ id: 'parcelas-sel', type: 'line', source: 'parcelas', filter: selPar, paint: { 'line-color': MAP_CHROME.seleccionCyan, 'line-width': 3 } }, beforePar);
          map.addLayer({
            id: 'parcelas-label', type: 'symbol', source: 'parcelas', minzoom: 14,
            layout: { 'text-field': ['get', 'etiqueta'], 'text-size': 11, 'text-allow-overlap': false },
            paint: { 'text-color': MAP_CHROME.textoParcela, 'text-halo-color': MAP_CHROME.haloFuerte, 'text-halo-width': 1.5 },
          });
        } else {
          par?.setData(fcPar);
          if (map.getLayer('parcelas-line')) map.setFilter('parcelas-line', noSelPar);
          if (map.getLayer('parcelas-sel')) map.setFilter('parcelas-sel', selPar);
        }
      } else {
        for (const lid of ['parcelas-label', 'parcelas-sel', 'parcelas-line', 'parcelas-fill']) {
          if (map.getLayer(lid)) map.removeLayer(lid);
        }
        if (map.getSource('parcelas')) map.removeSource('parcelas');
      }

      // Dibujo en curso: polígono + línea + vértices (verde).
      const vv = dibRef.current.vertices;
      let dibujoFC: FeatureCollection;
      if (vv.length === 1) {
        dibujoFC = { type: 'FeatureCollection', features: [{ type: 'Feature', geometry: { type: 'Point', coordinates: vv[0] }, properties: {} }] } as FeatureCollection;
      } else if (vv.length >= 2) {
        const ring = [...vv, vv[0]];
        dibujoFC = {
          type: 'FeatureCollection',
          features: [
            { type: 'Feature', geometry: { type: 'Polygon', coordinates: [ring] }, properties: {} },
            { type: 'Feature', geometry: { type: 'LineString', coordinates: vv }, properties: {} },
            ...vv.map((v) => ({ type: 'Feature', geometry: { type: 'Point', coordinates: v }, properties: {} })),
          ],
        } as unknown as FeatureCollection;
      } else {
        dibujoFC = { type: 'FeatureCollection', features: [] };
      }
      const dib = map.getSource('dibujo') as GeoJSONSource | undefined;
      if (!map.getLayer('dibujo-fill')) {
        if (!dib) map.addSource('dibujo', { type: 'geojson', data: dibujoFC });
        else dib.setData(dibujoFC);
        map.addLayer({ id: 'dibujo-fill', type: 'fill', source: 'dibujo', paint: { 'fill-color': MAP_CHROME.dibujoVerde, 'fill-opacity': 0.25 } });
        map.addLayer({ id: 'dibujo-line', type: 'line', source: 'dibujo', paint: { 'line-color': MAP_CHROME.dibujoVerde, 'line-width': 2 } });
        map.addLayer({ id: 'dibujo-pt', type: 'circle', source: 'dibujo', paint: { 'circle-color': MAP_CHROME.dibujoVerde, 'circle-radius': 5, 'circle-stroke-color': MAP_CHROME.textoSatelite, 'circle-stroke-width': 2 } });
      } else {
        dib?.setData(dibujoFC);
      }
      for (const lid of ['snap-pt', 'snap-seg-halo', 'snap-seg']) {
        if (map.getLayer(lid)) map.removeLayer(lid);
      }
      for (const sid of ['snap', 'snapseg']) {
        if (map.getSource(sid)) map.removeSource(sid);
      }
    } catch (e) {
      setMapError(e instanceof Error ? e.message : 'No se pudieron agregar las capas');
    }
  };

  const fitAll = (map: Map) => {
    encuadrar(map, dataRef.current.map((f) => f.geometry.coordinates));
  };

  // Crear mapa una sola vez
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    let cancelled = false;
    let map: Map | null = null;
    try {
      map = new Map({
        container: containerRef.current,
        style: buildStyleEsri(),
        center: INITIAL_CENTER,
        zoom: INITIAL_ZOOM,
        attributionControl: { compact: true },
        transformRequest: transformRequestTiles,
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
      fitKey.current = `${filtroRef.current.finca}|${filtroRef.current.fecha}|${dataRef.current.length}`;
      fitAll(map as Map);
    });
    const aplicarIman = (lng: number, lat: number, point: { x: number; y: number }): { ll: [number, number]; tipo: 'nada' | 'vertice' | 'borde'; seg: [[number, number], [number, number]] | null } => {
      try {
        const m = map as Map;
        const touch = typeof window !== 'undefined' && window.matchMedia?.('(pointer: coarse)').matches;
        const tolV = touch ? 30 : 24;
        const tolB = touch ? 22 : 18;
        const anillos: { px: { anillo: { x: number; y: number }[]; cerrar: boolean }; lngLat: [number, number][] }[] = [];
        const padre = dataRef.current.find((f) => f.properties.id === selRef.current);
        const geoms: { type: string; coordinates: unknown }[] = [];
        if (padre) geoms.push(padre.geometry as unknown as { type: string; coordinates: unknown });
        for (const p of parcRef.current) {
          if (padre && (p.properties as { potrero_id?: number }).potrero_id !== undefined
            && (p.properties as { potrero_id?: number }).potrero_id !== padre.properties.id) continue;
          geoms.push(p.geometry as unknown as { type: string; coordinates: unknown });
        }
        for (const g of geoms) {
          for (const ring of anillosDe(g)) {
            if (ring.length < 2) continue;
            const px = ring.map((ll) => { const pt = m.project([ll[0], ll[1]]); return { x: pt.x, y: pt.y }; });
            anillos.push({ px: { anillo: px, cerrar: true }, lngLat: ring });
          }
        }
        if (anillos.length === 0) return { ll: [lng, lat], tipo: 'nada' as const, seg: null };
        const s = snapClic({ x: point.x, y: point.y }, [lng, lat], anillos, tolV, tolB);
        return { ll: s.lngLat, tipo: s.tipo, seg: s.seg };
      } catch {
        return { ll: [lng, lat], tipo: 'nada' as const, seg: null };
      }
    };
    map.on('click', 'parcelas-fill', (e) => {
      if (dibRef.current.dibujando) return;
      const id = e.features?.[0]?.properties?.id;
      if (typeof id === 'number') onSelectParcRef.current?.(id);
    });
    map.on('click', 'potreros-fill', (e) => {
      if (dibRef.current.dibujando) return;
      try {
        if (mostrarParcRef.current) {
          const sobre = (map as Map).queryRenderedFeatures(e.point, { layers: ['parcelas-fill'] });
          if (sobre.length > 0) return;
        }
      } catch { /* capa aún no lista */ }
      const f = e.features?.[0];
      const id = f?.properties?.id;
      if (typeof id === 'number') onSelectRef.current(id);
    });
    map.on('click', (e) => {
      if (!dibRef.current.dibujando) return;
      onDibClickRef.current?.(aplicarIman(e.lngLat.lng, e.lngLat.lat, e.point).ll);
    });
    // Cursor-anillo: fino por defecto, se ensancha al pegar (verde = esquina,
    // naranja = borde). El canvas oculta su cursor nativo mientras se dibuja.
    // Puntito en la coordenada exacta donde quedará el vértice si clickeás.
    const anillo = cursorRef.current;
    const punto = puntoRef.current;
    map.on('mousemove', (e) => {
      if (!anillo || !punto) return;
      if (!dibRef.current.dibujando) {
        anillo.style.display = 'none';
        punto.style.display = 'none';
        return;
      }
      const s = aplicarIman(e.lngLat.lng, e.lngLat.lat, e.point);
      const d = s.tipo === 'vertice' ? 34 : s.tipo === 'borde' ? 28 : 16;
      const col = s.tipo === 'vertice' ? MAP_CHROME.dibujoVerde : s.tipo === 'borde' ? MAP_CHROME.dibujoBorde : MAP_CHROME.verticeStroke;
      anillo.style.display = 'block';
      anillo.style.width = `${d}px`;
      anillo.style.height = `${d}px`;
      anillo.style.left = `${e.point.x}px`;
      anillo.style.top = `${e.point.y}px`;
      anillo.style.borderColor = col;
      if (s.tipo === 'nada') {
        punto.style.display = 'none';
      } else {
        const pp = (map as Map).project(s.ll);
        punto.style.display = 'block';
        punto.style.left = `${pp.x}px`;
        punto.style.top = `${pp.y}px`;
        punto.style.background = col;
      }
    });
    map.on('mouseout', () => {
      if (cursorRef.current) cursorRef.current.style.display = 'none';
      if (puntoRef.current) puntoRef.current.style.display = 'none';
    });
    map.on('mouseenter', 'parcelas-fill', () => { map!.getCanvas().style.cursor = dibRef.current.dibujando ? 'none' : 'pointer'; });
    map.on('mouseleave', 'parcelas-fill', () => { map!.getCanvas().style.cursor = dibRef.current.dibujando ? 'none' : 'pointer'; });
    map.on('dblclick', (e) => {
      if (!dibRef.current.dibujando) return;
      e.preventDefault();
      onDibDblRef.current?.();
    });
    map.on('mouseenter', 'potreros-fill', () => { map!.getCanvas().style.cursor = dibRef.current.dibujando ? 'none' : 'pointer'; });
    map.on('mousemove', 'potreros-fill', (e) => {
      const id = e.features?.[0]?.properties?.id;
      if (map!.getLayer('potreros-hover')) {
        map!.setFilter('potreros-hover', ['==', ['get', 'id'], typeof id === 'number' ? id : -1] as FilterSpecification);
      }
    });
    map.on('mouseleave', 'potreros-fill', () => {
      map!.getCanvas().style.cursor = dibRef.current.dibujando ? 'none' : '';
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
  // El encuadre solo ocurre cuando cambia el conjunto de datos
  // (finca/fecha/cantidad de lotes): la selección no mueve el mapa.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || status !== 'listo') return;
    let cancelled = false;
    const dataKey = `${finca}|${fecha}|${features.length}`;
    const debeEncuadrar = fitKey.current !== dataKey;
    if (debeEncuadrar) fitKey.current = dataKey;
    const aplicar = () => {
      if (cancelled) return;
      syncCapas(map);
      if (debeEncuadrar) fitAll(map);
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
        const bb = bboxCombinado(dataRef.current.map((f) => f.geometry.coordinates));
        const v = map.getBounds();
        const enVista = !bb || (bb[1][0] >= v.getWest() && bb[0][0] <= v.getEast() && bb[1][1] >= v.getSouth() && bb[0][1] <= v.getNorth());
        if (enVista && map.queryRenderedFeatures({ layers: ['potreros-fill'] }).length === 0) {
          healTries.current += 1;
          syncCapas(map);
        }
      } catch { /* estilo aún no listo */ }
    };
    map.on('idle', onIdle);
    try {
      map.getCanvas().style.cursor = dibujando ? 'none' : '';
      if (cursorRef.current) cursorRef.current.style.display = 'none';
      if (puntoRef.current) puntoRef.current.style.display = 'none';
    } catch { /* sin canvas */ }
    return () => { cancelled = true; map.off('idle', onIdle); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [features, exclusiones, selectedId, finca, fecha, tipo, uid, status, parcelas, mostrarParcelas, parcelaSelectedId, dibujando, vertices]);

  return (
    <div style={{ position: 'relative', height: '100%' }}>
      <div ref={containerRef} className="map-container tall" aria-label="Mapa de masa seca por lote" />
      <div ref={cursorRef} className="dibujo-cursor" style={{ display: 'none' }} aria-hidden="true" />
      <div ref={puntoRef} className="dibujo-punto" style={{ display: 'none' }} aria-hidden="true" />

      {status === 'cargando' && !dibujando && <div className="map-overlay">Cargando mapa…</div>}
      {mapError && <div className="map-overlay error">Error del mapa: {mapError}</div>}
    </div>
  );
}
