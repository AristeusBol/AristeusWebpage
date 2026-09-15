import { useEffect, useRef, useState } from 'react';
import {
  Map, NavigationControl, ScaleControl,
  type FilterSpecification, type GeoJSONSource, type VectorTileSource,
} from 'maplibre-gl';
import type { FeatureCollection, Polygon, MultiPolygon } from 'geojson';
import 'maplibre-gl/dist/maplibre-gl.css';
import { degradadoMapLibre } from '../lib/masaSeca';
import {
  INITIAL_CENTER, INITIAL_ZOOM, bboxDe, buildStyleEsri,
  encuadrar, tilesUrl, transformRequestTiles,
} from '../lib/mapCommon';
import type { PotreroFeature } from './MapaMasaSeca';

export interface ParcelaFeature {
  type: 'Feature';
  geometry: Polygon | MultiPolygon;
  properties: {
    id: number;
    tipo: 'parcela';
    nombre: string;
    finca: string;
    potrero_id: number;
    estado: string;
    area_ha: number | null;
    t_ha_total: number | null;
    etiqueta?: string;
    [k: string]: unknown;
  };
}

export interface ExclusionFeature {
  type: 'Feature';
  geometry: Polygon | MultiPolygon;
  properties: {
    id: number;
    tipo: 'exclusion';
    nombre: string;
    subtipo?: string;
    finca: string;
    potrero_id: number;
    area_ha: number | null;
    etiqueta?: string;
    [k: string]: unknown;
  };
}

export interface SeleccionGestion {
  tipo: 'potrero' | 'parcela';
  id: number;
}

interface Props {
  potreros: PotreroFeature[];
  parcelas: ParcelaFeature[];
  exclusiones: ExclusionFeature[];
  seleccion: SeleccionGestion | null;
  onSelect: (s: SeleccionGestion | null) => void;
  finca: string;
  fecha: string;
  mostrarDensidad: boolean;
  uid: number;
  dibujando: boolean;
  vertices: [number, number][];
  onMapClick: (lngLat: [number, number]) => void;
  focusSignal: number;
}

export default function GestionMapa({
  potreros, parcelas, exclusiones, seleccion, onSelect,
  finca, fecha, mostrarDensidad, uid, dibujando, vertices, onMapClick, focusSignal,
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<Map | null>(null);
  const dataRef = useRef({ potreros, parcelas, exclusiones, seleccion, finca, fecha, mostrarDensidad, uid, vertices, dibujando });
  const onSelectRef = useRef(onSelect);
  const onMapClickRef = useRef(onMapClick);
  const lastTilesRef = useRef<string | null>(null);
  const [status, setStatus] = useState<'cargando' | 'listo'>('cargando');
  const [mapError, setMapError] = useState<string | null>(null);

  dataRef.current = { potreros, parcelas, exclusiones, seleccion, finca, fecha, mostrarDensidad, uid, vertices, dibujando };
  onSelectRef.current = onSelect;
  onMapClickRef.current = onMapClick;

  const syncCapas = (map: Map) => {
    const d = dataRef.current;
    const fcPot = { type: 'FeatureCollection', features: d.potreros } as FeatureCollection;
    const fcPar = { type: 'FeatureCollection', features: d.parcelas } as FeatureCollection;
    const fcExc = { type: 'FeatureCollection', features: d.exclusiones } as FeatureCollection;
    const selPot = ['==', ['get', 'id'], d.seleccion?.tipo === 'potrero' ? d.seleccion.id : -1] as FilterSpecification;
    const selPar = ['==', ['get', 'id'], d.seleccion?.tipo === 'parcela' ? d.seleccion.id : -1] as FilterSpecification;

    // Dibujo en curso: línea + relleno + vértices
    let dibujoFC: FeatureCollection;
    if (d.vertices.length === 1) {
      dibujoFC = { type: 'FeatureCollection', features: [{ type: 'Feature', geometry: { type: 'Point', coordinates: d.vertices[0] }, properties: {} }] } as FeatureCollection;
    } else if (d.vertices.length >= 2) {
      const ring = [...d.vertices, d.vertices[0]];
      dibujoFC = {
        type: 'FeatureCollection',
        features: [
          { type: 'Feature', geometry: { type: 'Polygon', coordinates: [ring] }, properties: {} },
          { type: 'Feature', geometry: { type: 'LineString', coordinates: d.vertices }, properties: {} },
          ...d.vertices.map((v) => ({ type: 'Feature', geometry: { type: 'Point', coordinates: v }, properties: {} })),
        ],
      } as unknown as FeatureCollection;
    } else {
      dibujoFC = { type: 'FeatureCollection', features: [] };
    }

    try {
      const pot = map.getSource('g-potreros') as GeoJSONSource | undefined;
      if (!map.getLayer('g-potreros-fill')) {
        if (!pot) map.addSource('g-potreros', { type: 'geojson', data: fcPot });
        else pot.setData(fcPot);
        map.addLayer({ id: 'g-potreros-fill', type: 'fill', source: 'g-potreros', paint: { 'fill-color': '#ffffff', 'fill-opacity': 0.06 } });
        map.addLayer({ id: 'g-potreros-line', type: 'line', source: 'g-potreros', paint: { 'line-color': '#ffffff', 'line-width': 2, 'line-opacity': 1 } });
        map.addLayer({ id: 'g-potreros-sel', type: 'line', source: 'g-potreros', filter: selPot, paint: { 'line-color': '#facc15', 'line-width': 4 } });
        map.addLayer({
          id: 'g-potreros-label', type: 'symbol', source: 'g-potreros',
          layout: { 'text-field': ['get', 'etiqueta'], 'text-size': 12, 'text-allow-overlap': true },
          paint: { 'text-color': '#fff', 'text-halo-color': 'rgba(0,0,0,0.65)', 'text-halo-width': 1.5 },
        });
      } else {
        pot?.setData(fcPot);
        if (map.getLayer('g-potreros-sel')) map.setFilter('g-potreros-sel', selPot);
      }

      // Zonas de exclusión: siempre visibles en rojo (objeto editable),
      // debajo de parcelas y dibujo. En el mapa de masa seca (MapaMasaSeca)
      // van en gris neutro porque ahí son solo máscara del dato forrajero.
      // Las parcelas solo pueden dibujarse fuera de estas áreas.
      const exc = map.getSource('g-exclusiones') as GeoJSONSource | undefined;
      if (!map.getLayer('g-exclusiones-fill')) {
        if (!exc) map.addSource('g-exclusiones', { type: 'geojson', data: fcExc });
        else exc.setData(fcExc);
        map.addLayer({ id: 'g-exclusiones-fill', type: 'fill', source: 'g-exclusiones', paint: { 'fill-color': '#dc2626', 'fill-opacity': 0.35 } });
        map.addLayer({ id: 'g-exclusiones-line', type: 'line', source: 'g-exclusiones', paint: { 'line-color': '#fecaca', 'line-width': 1.5, 'line-dasharray': [3, 2] } });
        map.addLayer({
          id: 'g-exclusiones-label', type: 'symbol', source: 'g-exclusiones',
          layout: { 'text-field': ['get', 'etiqueta'], 'text-size': 11, 'text-allow-overlap': true },
          paint: { 'text-color': '#fecaca', 'text-halo-color': 'rgba(0,0,0,0.7)', 'text-halo-width': 1.5 },
        });
      } else {
        exc?.setData(fcExc);
      }

      const par = map.getSource('g-parcelas') as GeoJSONSource | undefined;
      const noSelPar = ['!=', ['get', 'id'], d.seleccion?.tipo === 'parcela' ? d.seleccion.id : -1] as FilterSpecification;
      if (!map.getLayer('g-parcelas-fill')) {
        if (!par) map.addSource('g-parcelas', { type: 'geojson', data: fcPar });
        else par.setData(fcPar);
        map.addLayer({ id: 'g-parcelas-fill', type: 'fill', source: 'g-parcelas', paint: { 'fill-color': '#facc15', 'fill-opacity': 0 } });
        map.addLayer({ id: 'g-parcelas-line', type: 'line', source: 'g-parcelas', filter: noSelPar, paint: { 'line-color': '#000000', 'line-width': 2, 'line-dasharray': [2, 1] } });
        map.addLayer({ id: 'g-parcelas-sel', type: 'line', source: 'g-parcelas', filter: selPar, paint: { 'line-color': '#22d3ee', 'line-width': 2 } });
        map.addLayer({
          id: 'g-parcelas-label', type: 'symbol', source: 'g-parcelas',
          layout: { 'text-field': ['get', 'etiqueta'], 'text-size': 11, 'text-allow-overlap': true },
          paint: { 'text-color': '#fefce8', 'text-halo-color': 'rgba(0,0,0,0.7)', 'text-halo-width': 1.5 },
        });
      } else {
        par?.setData(fcPar);
        if (map.getLayer('g-parcelas-line')) map.setFilter('g-parcelas-line', noSelPar);
        if (map.getLayer('g-parcelas-sel')) map.setFilter('g-parcelas-sel', selPar);
      }

      const dib = map.getSource('g-dibujo') as GeoJSONSource | undefined;
      if (!map.getLayer('g-dibujo-fill')) {
        if (!dib) map.addSource('g-dibujo', { type: 'geojson', data: dibujoFC });
        else dib.setData(dibujoFC);
        map.addLayer({ id: 'g-dibujo-fill', type: 'fill', source: 'g-dibujo', paint: { 'fill-color': '#22c55e', 'fill-opacity': 0.25 } });
        map.addLayer({ id: 'g-dibujo-line', type: 'line', source: 'g-dibujo', paint: { 'line-color': '#22c55e', 'line-width': 2 } });
        map.addLayer({ id: 'g-dibujo-pt', type: 'circle', source: 'g-dibujo', paint: { 'circle-color': '#22c55e', 'circle-radius': 5, 'circle-stroke-color': '#fff', 'circle-stroke-width': 2 } });
      } else {
        dib?.setData(dibujoFC);
      }

      // Capa forrajera total (toggle, debajo de bordes).
      // Esta sección siempre muestra masa total (ver TIPO en syncCapas).
      if (d.mostrarDensidad && d.finca && d.fecha) {
        const tiles = [tilesUrl(d.finca, d.fecha, 'total', d.uid)];
        const dex = map.getSource('g-densidad') as VectorTileSource | undefined;
        if (!map.getLayer('g-densidad-fill')) {
          if (!dex) map.addSource('g-densidad', { type: 'vector', tiles, minzoom: 0, maxzoom: 22 });
          else dex.setTiles(tiles);
          lastTilesRef.current = tiles[0];
          map.addLayer(
            {
              id: 'g-densidad-fill', type: 'fill', source: 'g-densidad', 'source-layer': 'densidad',
              paint: {
                'fill-color': degradadoMapLibre(),
                'fill-opacity': 0.62, 'fill-outline-color': 'rgba(0,0,0,0)',
                'fill-antialias': false,
              },
            },
            'g-potreros-line',
          );
        } else if (lastTilesRef.current !== tiles[0]) {
          dex?.setTiles(tiles);
          lastTilesRef.current = tiles[0];
        }
      } else {
        lastTilesRef.current = null;
        if (map.getLayer('g-densidad-fill')) map.removeLayer('g-densidad-fill');
        if (map.getSource('g-densidad')) map.removeSource('g-densidad');
      }
    } catch (e) {
      setMapError(e instanceof Error ? e.message : 'No se pudieron agregar las capas');
    }
  };

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
      setMapError(e instanceof Error ? e.message : 'No se pudo crear el mapa');
      return;
    }
    map.addControl(new NavigationControl({ visualizePitch: false }), 'top-right');
    map.addControl(new ScaleControl({ maxWidth: 120, unit: 'metric' }), 'bottom-right');
    map.on('load', () => {
      if (cancelled) return;
      setStatus('listo');
      syncCapas(map as Map);
      const d = dataRef.current;
      const all = [...d.potreros.map((f) => f.geometry.coordinates), ...d.parcelas.map((f) => f.geometry.coordinates), ...d.exclusiones.map((f) => f.geometry.coordinates)];
      encuadrar(map as Map, all);
    });
    // Parcelas arriba: se testean primero
    map.on('click', 'g-parcelas-fill', (e) => {
      if (dataRef.current.dibujando) return;
      const id = e.features?.[0]?.properties?.id;
      if (typeof id === 'number') onSelectRef.current({ tipo: 'parcela', id });
    });
    map.on('click', 'g-potreros-fill', (e) => {
      if (dataRef.current.dibujando) return;
      // La parcela está encima del potrero: si el clic cayó sobre una parcela,
      // el handler de parcelas ya seleccionó; no pisar con el potrero.
      try {
        const sobreParcela = map!.queryRenderedFeatures(e.point, { layers: ['g-parcelas-fill'] });
        if (sobreParcela.length > 0) return;
      } catch {
        /* capa aún no lista: seguir con potrero */
      }
      const id = e.features?.[0]?.properties?.id;
      if (typeof id === 'number') onSelectRef.current({ tipo: 'potrero', id });
      else onSelectRef.current(null);
    });
    map.on('click', (e) => {
      const d = dataRef.current;
      if (!d.dibujando) return;
      // Si cayó sobre una capa existente, los handlers de capa ya actuaron; igual sumamos vértice
      onMapClickRef.current([e.lngLat.lng, e.lngLat.lat]);
    });
    map.on('mouseenter', 'g-potreros-fill', () => { map!.getCanvas().style.cursor = dataRef.current.dibujando ? 'crosshair' : 'pointer'; });
    map.on('mouseleave', 'g-potreros-fill', () => { map!.getCanvas().style.cursor = dataRef.current.dibujando ? 'crosshair' : ''; });
    mapRef.current = map;
    (window as unknown as { __fmGestionMap?: Map }).__fmGestionMap = map;
    return () => {
      cancelled = true;
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
    map.getCanvas().style.cursor = dibujando ? 'crosshair' : '';
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [potreros, parcelas, exclusiones, seleccion, finca, fecha, mostrarDensidad, uid, vertices, dibujando, status]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || status !== 'listo' || focusSignal === 0) return;
    const s = dataRef.current.seleccion;
    if (!s) return;
    const feat =
      s.tipo === 'potrero'
        ? dataRef.current.potreros.find((f) => f.properties.id === s.id)
        : dataRef.current.parcelas.find((f) => f.properties.id === s.id);
    if (!feat) return;
    const bb = bboxDe(feat.geometry.coordinates);
    if (bb) map.fitBounds(bb, { padding: 60, maxZoom: 15 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusSignal]);

  return (
    <div style={{ position: 'relative', height: '100%' }}>
      <div className="map-submenu" role="group" aria-label="Mapa total">
        <button type="button" className="active" title="Esta sección siempre muestra masa total">Total</button>
      </div>
      <div ref={containerRef} className="map-container tall" aria-label="Mapa de gestión de potreros y parcelas" />
      {dibujando && (
        <div className="map-overlay">
          Clic para agregar vértices ({vertices.length}) · doble-clic o “Cerrar” para terminar · Esc cancela
        </div>
      )}
      {status === 'cargando' && !dibujando && <div className="map-overlay">Cargando mapa…</div>}
      {mapError && <div className="map-overlay error">Error del mapa: {mapError}</div>}
    </div>
  );
}
