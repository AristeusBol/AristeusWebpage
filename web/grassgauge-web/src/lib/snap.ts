// Imán (snap) para dibujo de parcelas en Mapa de Masa Seca.
// Prioridad: vértices (esquinas) > bordes. Solo potrero padre + parcelas hermanas.
// Trabaja en píxeles de pantalla: el llamador proyecta con map.project().

export interface PuntoPx { x: number; y: number }

export interface AnilloPx { anillo: PuntoPx[]; cerrar: boolean }

/** Distancia punto-segmento en px. Retorna {d, p} con p el punto más cercano. */
function puntoSegmento(p: PuntoPx, a: PuntoPx, b: PuntoPx): { d: number; p: PuntoPx } {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const len2 = dx * dx + dy * dy;
  let t = 0;
  if (len2 > 0) t = ((p.x - a.x) * dx + (p.y - a.y) * dy) / len2;
  t = Math.max(0, Math.min(1, t));
  const q = { x: a.x + t * dx, y: a.y + t * dy };
  return { d: Math.hypot(p.x - q.x, p.y - q.y), p: q };
}

export interface SnapResult {
  /** Coordenadas geográficas del punto pegado (o las originales si no hubo imán). */
  lngLat: [number, number];
  /** Qué pegó: nada | esquina | borde. */
  tipo: 'nada' | 'vertice' | 'borde';
  /** Segmento pegado (solo borde): sus 2 esquinas para resaltarlo. */
  seg: [[number, number], [number, number]] | null;
}

/**
 * Busca imán para un clic.
 * @param clicPx punto clickeado en píxeles
 * @param clicLngLat coords originales del clic
 * @param anillos anillos ya proyectados a px con su correspondencia lngLat
 * @param tolVertice px para esquinas, tolBorde px para líneas
 */
export function snapClic(
  clicPx: PuntoPx,
  clicLngLat: [number, number],
  anillos: { px: AnilloPx; lngLat: [number, number][] }[],
  tolVertice: number,
  tolBorde: number,
): SnapResult {
  let mejorV: { d: number; ll: [number, number] } | null = null;
  for (const a of anillos) {
    const n = a.px.anillo.length;
    for (let i = 0; i < n; i++) {
      const q = a.px.anillo[i];
      const d = Math.hypot(clicPx.x - q.x, clicPx.y - q.y);
      if (d <= tolVertice && (!mejorV || d < mejorV.d)) {
        mejorV = { d, ll: a.lngLat[i] };
      }
    }
  }
  if (mejorV) return { lngLat: mejorV.ll, tipo: 'vertice', seg: null };

  let mejorB: { d: number; ll: [number, number]; seg: [[number, number], [number, number]] } | null = null;
  for (const a of anillos) {
    const pts = a.px.anillo;
    const lls = a.lngLat;
    const m = pts.length;
    if (m < 2) continue;
    const segs = a.px.cerrar ? m : m - 1;
    for (let i = 0; i < segs; i++) {
      const p0 = pts[i];
      const p1 = pts[(i + 1) % m];
      const { d, p } = puntoSegmento(clicPx, p0, p1);
      if (d <= tolBorde && (!mejorB || d < mejorB.d)) {
        // Interpolación lineal en lngLat con el mismo t del segmento en px.
        const dx = p1.x - p0.x;
        const dy = p1.y - p0.y;
        const len2 = dx * dx + dy * dy;
        let t = 0;
        if (len2 > 0) t = ((p.x - p0.x) * dx + (p.y - p0.y) * dy) / len2;
        t = Math.max(0, Math.min(1, t));
        const q0 = lls[i];
        const q1 = lls[(i + 1) % m];
        mejorB = { d, ll: [q0[0] + t * (q1[0] - q0[0]), q0[1] + t * (q1[1] - q0[1])], seg: [q0, q1] };
      }
    }
  }
  if (mejorB) return { lngLat: mejorB.ll, tipo: 'borde', seg: mejorB.seg };
  return { lngLat: clicLngLat, tipo: 'nada', seg: null };
}

/** Extrae anillos exteriores [lng,lat][] de Polygon/MultiPolygon. */
export function anillosDe(geom: { type: string; coordinates: unknown }): [number, number][][] {
  try {
    if (geom.type === 'Polygon' && Array.isArray(geom.coordinates)) {
      const coords = geom.coordinates as unknown[];
      if (coords.length === 0) return [];
      return [coords[0] as [number, number][]];
    }
    if (geom.type === 'MultiPolygon' && Array.isArray(geom.coordinates)) {
      return (geom.coordinates as unknown[][][]).map((p) => (p[0] ?? []) as [number, number][]);
    }
  } catch {
    /* geometría inesperada */
  }
  return [];
}
