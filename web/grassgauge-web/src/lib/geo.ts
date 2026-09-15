// Geometría mínima para validación local (sin dependencias).

export type Anillo = [number, number][]; // [lon, lat]

export interface GeomPoligonal {
  type: 'Polygon' | 'MultiPolygon';
  coordinates: unknown;
}

/** Ray casting: punto dentro de un anillo. */
function enAnillo(lon: number, lat: number, anillo: Anillo): boolean {
  let dentro = false;
  for (let i = 0, j = anillo.length - 1; i < anillo.length; j = i++) {
    const xi = anillo[i][0];
    const yi = anillo[i][1];
    const xj = anillo[j][0];
    const yj = anillo[j][1];
    if (yi > lat !== yj > lat && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) {
      dentro = !dentro;
    }
  }
  return dentro;
}

function enPoligono(lon: number, lat: number, coords: unknown): boolean {
  if (!Array.isArray(coords) || coords.length === 0) return false;
  const anillos = coords as Anillo[];
  if (!enAnillo(lon, lat, anillos[0])) return false;
  return !anillos.slice(1).some((h) => enAnillo(lon, lat, h));
}

/** Punto dentro de un Polygon/MultiPolygon (con huecos). */
export function contienePunto(geom: GeomPoligonal, lon: number, lat: number): boolean {
  if (geom.type === 'Polygon') return enPoligono(lon, lat, geom.coordinates);
  if (geom.type === 'MultiPolygon' && Array.isArray(geom.coordinates)) {
    return (geom.coordinates as unknown[]).some((p) => enPoligono(lon, lat, p));
  }
  return false;
}

export interface FeatureSimple {
  geometry: GeomPoligonal;
  properties: { tipo?: string };
}

/** Valida el punto de calibración: dentro del lote y fuera de exclusiones. */
export function validarPuntoCalibracion(
  lat: number,
  lon: number,
  features: FeatureSimple[],
): { ok: boolean; motivo: string } {
  const pot = features.find((f) => f.properties.tipo === 'potrero_base');
  if (!pot) return { ok: false, motivo: 'Sin geometría del potrero.' };
  if (!contienePunto(pot.geometry, lon, lat)) {
    return { ok: false, motivo: 'El punto está fuera del lote. Elegí otro dentro del lote.' };
  }
  const enExclusion = features
    .filter((f) => f.properties.tipo === 'exclusion')
    .some((f) => contienePunto(f.geometry, lon, lat));
  if (enExclusion) {
    return { ok: false, motivo: 'El punto cae en una zona de exclusión. Elegí otro.' };
  }
  return { ok: true, motivo: '' };
}
