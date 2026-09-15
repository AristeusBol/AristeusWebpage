// Utilidades de rotación compartidas entre la lista y el mapa.
// Sin dependencias pesadas para no arrastrar maplibre al bundle de la lista.

import type { Asignacion, Rodeo, SemaforoBalance } from './api';

/**
 * Paleta categórica por rodeo (orden estable por primer uso en estado_actual).
 * Okabe-Ito: 8 colores de alto contraste, aptos para daltónicos y fieles al
 * estilo de una figura científica (nada estridente sobre el verde del pasto).
 */
export const PALETA_ROTACION = [
  '#E69F00', // naranja
  '#56B4E9', // celeste
  '#009E73', // verde azulado
  '#F0E442', // amarillo
  '#0072B2', // azul
  '#D55E00', // bermellón
  '#CC79A7', // púrpura rosado
  '#999999', // gris
];

const GRIS = '#6b7280';

/** Índice estable de un rodeo en la paleta, según su aparición en estado_actual. */
export function indiceRodeo(asignaciones: Asignacion[], rodeoId: number): number {
  const orden = Array.from(new Set(asignaciones.map((a) => a.rodeo_id)));
  const i = orden.indexOf(rodeoId);
  return i >= 0 ? i : 0;
}

/** Color estable de un rodeo dado el estado actual. */
export function colorDeRodeo(asignaciones: Asignacion[], rodeoId: number): string {
  if (!asignaciones.some((a) => a.rodeo_id === rodeoId)) return GRIS;
  return PALETA_ROTACION[indiceRodeo(asignaciones, rodeoId) % PALETA_ROTACION.length];
}

/** Color de un rodeo: respeta el color fijo del lote; si no, paleta del estado actual. */
export function colorDeRodeoRegistrado(
  rodeos: Pick<Rodeo, 'id' | 'color'>[],
  estadoActual: Asignacion[],
  rodeoId: number,
): string {
  const r = rodeos.find((x) => x.id === rodeoId);
  if (r?.color) return r.color;
  return colorDeRodeo(estadoActual, rodeoId);
}

/** Fecha local de hoy en YYYY-MM-DD (input date). */
export function isoHoy(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

/** dd/mm/yyyy para mostrar una fecha ISO. */
export function fmtFecha(iso: string): string {
  if (!iso) return '';
  const [y, m, d] = iso.split('-');
  return `${d}/${m}/${y}`;
}

/** Color de cada estado del semáforo de balance (días de pastoreo). */
export const SEMAFORO_BALANCE_COLOR: Record<SemaforoBalance, string> = {
  urgente: '#dc2626',
  atento: '#f59e0b',
  ok: '#16a34a',
  sin_dato: '#9ca3af',
  libre: '#6b7280',
};

/** Etiqueta corta de cada estado. */
export const SEMAFORO_BALANCE_LABEL: Record<SemaforoBalance, string> = {
  urgente: 'Urgente',
  atento: 'Atento',
  ok: 'Ok',
  sin_dato: 'Sin datos',
  libre: 'Libre',
};

/** Orden estable para leyenda y lista (urgentes primero). */
export const SEMAFORO_BALANCE_ORDEN: { s: SemaforoBalance; label: string }[] = [
  { s: 'urgente', label: '< 7 días' },
  { s: 'atento', label: '7–21 días' },
  { s: 'ok', label: '≥ 21 días' },
  { s: 'sin_dato', label: 'Sin datos' },
  { s: 'libre', label: 'Libre (reserva)' },
];