import type { ExpressionSpecification } from 'maplibre-gl';
import type { PotreroProps } from './api';
import { ESTADOS } from './zonas';

// Rangos de Masa Seca: la fuente única de verdad son las zonas de series
// temporales (ESTADOS en lib/zonas.ts). Este módulo deriva de ahí la rampa
// del mapa (g/m²) y helpers de formato.
export const DENSIDAD_CEILING = 500;

// Escalones fijos [min g/m², color] derivados de ESTADOS: cada valor toma el
// color plano de su zona, sin fundidos.
export const RAMPA_DENSIDAD: { v: number; color: string }[] = ESTADOS.map((e) => ({
  v: Math.round(e.min * 100),
  color: e.color,
}));

/** Paradas con tramos sólidos por zona y fundido corto solo en cada corte:
 *  cada zona mantiene su color plano en el interior y se mezcla con la
 *  vecina únicamente en ±M alrededor del límite. */
const MARGEN_FUNDIDO = 20; // g/m² a cada lado del corte

export function paradasDegradado(): { v: number; color: string }[] {
  const out: { v: number; color: string }[] = [{ v: 0, color: RAMPA_DENSIDAD[0].color }];
  for (let i = 1; i < RAMPA_DENSIDAD.length; i++) {
    const v = RAMPA_DENSIDAD[i].v;
    out.push(
      { v: v - MARGEN_FUNDIDO, color: RAMPA_DENSIDAD[i - 1].color },
      { v: v + MARGEN_FUNDIDO, color: RAMPA_DENSIDAD[i].color },
    );
  }
  return out;
}

/** Expresión `interpolate` de MapLibre para fill-color con degradado suave
 *  según `valor` (g/m²). Zonas sólidas por dentro, fundido corto en cortes. */
export function degradadoMapLibre(): ExpressionSpecification {
  return [
    'interpolate',
    ['linear'],
    ['to-number', ['get', 'valor']],
    ...paradasDegradado().flatMap((s): (number | string)[] => [s.v, s.color]),
  ] as ExpressionSpecification;
}

/** Posición 0–100% de un valor en t MS/ha dentro de la leyenda/mapa. */
export function tHaAPct(tHa: number): number {
  return ((tHa * 100) / DENSIDAD_CEILING) * 100;
}

export function fmtTHa(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined || Number.isNaN(v)) return 's/d';
  return `${v.toLocaleString('es-AR', { minimumFractionDigits: digits, maximumFractionDigits: digits })} t/ha`;
}

export function fmtHa(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined || Number.isNaN(v)) return 's/d';
  return `${v.toLocaleString('es-AR', { minimumFractionDigits: digits, maximumFractionDigits: digits })} ha`;
}

export function fmtFechaCorta(iso: string): string {
  // '2026-08-31' -> '31/08/2026' sin problemas de timezone (parseo manual).
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  return m ? `${m[3]}/${m[2]}/${m[1]}` : iso;
}

/** "Hace X min/h" para la tarjeta de sincronización. */
export function haceCuanto(ts: number | null): string {
  if (!ts) return '—';
  const s = Math.max(0, Math.floor((Date.now() - ts) / 1000));
  if (s < 10) return 'ahora mismo';
  if (s < 60) return `Hace ${s} segundos`;
  const m = Math.floor(s / 60);
  if (m < 60) return m === 1 ? 'Hace 1 minuto' : `Hace ${m} minutos`;
  const h = Math.floor(m / 60);
  return h === 1 ? 'Hace 1 hora' : `Hace ${h} horas`;
}

/** Campaña (año) derivada de una fecha ISO. */
export function campaniaDe(fechaIso: string): string {
  const m = /^(\d{4})/.exec(fechaIso);
  return m ? m[1] : '';
}

export function etiquetaPotrero(p: PotreroProps): string {
  return p.nombre;
}
