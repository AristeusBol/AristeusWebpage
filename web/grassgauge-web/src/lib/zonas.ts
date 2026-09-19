// Franjas del ciclo de la pastura (t MS/ha): fuente única de verdad para
// Series Temporales (degradado de fondo, chips de estado y leyenda).
// Mismos cortes y colores que la escala del mapa (ver lib/masaSeca.ts):
// rojo = malo, verde = bueno, violeta = pasado.
// `op` moderado porque van de fondo del gráfico; `texto` es el tono legible
// sobre panel claro para los chips.

export interface ZonaCiclo {
  nombre: string;
  min: number;
  max: number;
  color: string;
  /** Opacidad del relleno en el gráfico. */
  op: number;
  /** Color de texto legible sobre fondo claro (chips). */
  texto: string;
}

export const ESTADOS: ZonaCiclo[] = [
  { nombre: 'Sobrepastoreo', min: 0.0, max: 1.49, color: '#ef4444', op: 0.7, texto: '#b91c1c' },
  { nombre: 'Recuperación', min: 1.5, max: 2.49, color: '#facc15', op: 0.7, texto: '#a16207' },
  { nombre: 'Aceptable', min: 2.5, max: 4.0, color: '#22c55e', op: 0.7, texto: '#15803d' },
  { nombre: 'Transición', min: 4.01, max: 4.5, color: '#8b5cf6', op: 0.7, texto: '#6d28d9' },
  { nombre: 'Envejecido', min: 4.51, max: Number.POSITIVE_INFINITY, color: '#86198f', op: 0.7, texto: '#86198f' },
];

/** Franja a la que pertenece un valor (t MS/ha). */
export function zonaDe(tha: number): ZonaCiclo {
  return ESTADOS.find((r) => tha >= r.min && tha <= r.max) ?? ESTADOS[ESTADOS.length - 1];
}

/** Ticks equidistantes "lindos" (pasos 1/2/2.5/5×10^n) que cubren dataMax. */
export function niceTicks(dataMax: number, intervals = 5): { ticks: number[]; top: number } {
  if (!(dataMax > 0)) return { ticks: [0, 1], top: 0.7 };
  const raw = dataMax / intervals;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const norm = raw / mag;
  const snap = norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 2.5 ? 2.5 : norm <= 5 ? 5 : 10;
  const step = snap * mag;
  const top = Math.max(Math.ceil(dataMax / step - 1e-9) * step, step);
  const ticks: number[] = [];
  for (let k = 0; k * step <= top + 1e-9; k++) ticks.push(Math.round(k * step * 1e9) / 1e9);
  return { ticks, top };
}
