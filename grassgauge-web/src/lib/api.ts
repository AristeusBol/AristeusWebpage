// Cliente tipado para la API GrassGauge.
// Contratos verificados contra api/routers/*.py y tests/test_*.py

export const API_URL = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') ?? '';

const TOKEN_KEY = 'grassgauge_token';
// Clave anterior (ForageMap): se lee una vez para migrar la sesión existente.
const LEGACY_TOKEN_KEY = 'foragemap_token';

/** Evento global al recibir 401: AuthProvider lo escucha y cierra sesión. */
export const LOGOUT_EVENT = 'grassgauge:logout';
// Evento anterior: se despacha también por compatibilidad con pestañas viejas.
export const LEGACY_LOGOUT_EVENT = 'foragemap:logout';

function forzarLogout() {
  setToken(null);
  window.dispatchEvent(new Event(LOGOUT_EVENT));
  window.dispatchEvent(new Event(LEGACY_LOGOUT_EVENT));
}

export function getToken(): string | null {
  const token = localStorage.getItem(TOKEN_KEY) ?? localStorage.getItem(LEGACY_TOKEN_KEY);
  if (token && !localStorage.getItem(TOKEN_KEY)) {
    // Migración automática a la nueva key.
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.removeItem(LEGACY_TOKEN_KEY);
  }
  return token;
}

export function setToken(token: string | null) {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.removeItem(LEGACY_TOKEN_KEY);
  } else {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(LEGACY_TOKEN_KEY);
  }
}

export type TipoDensidad = 'verde' | 'muerta' | 'total';

export interface FiltrosResponse {
  fincas: string[];
  fechas: string[];
  tipos_densidad: TipoDensidad[];
  filtros_aplicados: { finca: string | null };
}

export interface ParcelaProps {
  id: number;
  tipo: 'parcela';
  nombre: string;
  finca: string;
  potrero_id: number;
  estado: string;
  fecha: string | null;
  area_ha: number | null;
  masa_verde_kg: number | null;
  masa_muerta_kg: number | null;
  masa_total_kg: number | null;
  t_ha_verde: number | null;
  t_ha_muerta: number | null;
  t_ha_total: number | null;
  tiene_calculo: boolean;
  estimado_por_prorrateo?: boolean;
}

export interface ParcelasResponse {
  type: 'FeatureCollection';
  features: { type: 'Feature'; geometry: unknown; properties: ParcelaProps }[];
  metadata: { potrero_id?: number; potrero?: string; finca: string; fecha: string | null; count: number; con_calculo?: number; nota?: string | null };
}

export interface ExclusionProps {
  id: number;
  tipo: 'exclusion';
  nombre: string;
  subtipo?: string;
  finca: string;
  potrero_id: number;
  area_ha: number | null;
}

export interface ExclusionesResponse {
  type: 'FeatureCollection';
  features: { type: 'Feature'; geometry: unknown; properties: ExclusionProps }[];
  metadata: { finca: string; count: number };
}

export interface ParcelaDetalle {
  id: number;
  nombre: string;
  estado: string;
  potrero_id: number;
  potrero: string | null;
  finca: string | null;
  fecha: string | null;
  area_ha: number | null;
  masa_verde_kg: number | null;
  masa_muerta_kg: number | null;
  masa_total_kg: number | null;
  t_ha_verde: number | null;
  t_ha_muerta: number | null;
  t_ha_total: number | null;
  tiene_calculo: boolean;
  estimado_zonal?: boolean;
  estimado_por_prorrateo?: boolean;
  n_puntos?: number;
  densidad_promedio_verde_g_m2?: number | null;
  densidad_promedio_muerta_g_m2?: number | null;
  densidad_promedio_total_g_m2?: number | null;
  geom: unknown;
}

export interface PotreroProps {
  id: number;
  nombre: string;
  finca: string;
  fecha: string | null;
  area_bruta_ha: number | null;
  area_neta_ha: number | null;
  masa_verde_kg: number | null;
  masa_muerta_kg: number | null;
  masa_total_kg: number | null;
  t_ha_verde: number | null;
  t_ha_muerta: number | null;
  t_ha_total: number | null;
  tiene_calculo: boolean;
  /** Etiqueta precalculada para el mapa: "A5\n6.2 t/ha" */
  etiqueta?: string;
}

export interface PotrerosResponse {
  type: 'FeatureCollection';
  features: { type: 'Feature'; geometry: unknown; properties: PotreroProps }[];
  metadata: { finca: string; fecha: string; count: number; con_calculo: number };
}

export interface SeriePunto {
  fecha: string;
  area_ha: number;
  verde_kg: number;
  muerta_kg: number;
  total_kg: number;
  t_ha: number | null;
  potreros: number;
}

export interface SerieResponse {
  filtros: { finca: string; potrero_id: number | null; parcela_id?: number | null; usuario_id: number };
  puntos: SeriePunto[];
}

export interface HistoSerie {
  min: number | null;
  max: number | null;
  mean: number | null;
  count: number;
  counts: number[];
  pcts: number[];
}

export interface HistogramaResponse {
  filtros: { finca: string; fecha: string; bins: number; potrero_id: number | null; parcela_id?: number | null; usuario_id: number; area_ha: number };
  stats: { count: number };
  /** Bordes de bin comunes a las 3 series (misma unidad que las medias). */
  edges: number[];
  series: Record<TipoDensidad, HistoSerie>;
  sin_datos: boolean;
}

export interface Rodeo {
  id: number;
  nombre: string;
  categoria: string;
  categoria_label: string;
  cabezas: number;
  peso_prom_kg: number;
  consumo_pct: number;
  notas: string | null;
  color: string | null;
  consumo_diario_ms_kg: number | null;
}

export interface RodeosResponse {
  rodeos: Rodeo[];
  total_cabezas: number;
  total_consumo_diario_ms_kg: number;
}

export interface Asignacion {
  id: number;
  rodeo_id: number;
  rodeo: string;
  categoria: string;
  categoria_label: string;
  cabezas: number;
  peso_prom_kg: number;
  consumo_pct: number;
  consumo_diario_ms_kg: number | null;
  parcela_id: number;
  parcela: string;
  estado_parcela: string;
  potrero_id: number;
  potrero: string;
  finca: string;
  fecha_entrada: string;
  fecha_salida: string | null;
  notas: string | null;
}

export interface ResumenRotacion {
  rodeos_pastoreando: number;
  cabezas_pastoreando: number;
  consumo_diario_ms_kg: number;
  parcelas_ocupadas: number;
  parcelas_total: number;
}

export interface RotacionResponse {
  asignaciones: Asignacion[];
  /** Pastoreo vigente hoy (entrada <= hoy y salida NULL o >= hoy). */
  estado_actual: Asignacion[];
  resumen: ResumenRotacion;
}

/** Etapa de una trayectoria de un lote (una asignación con su estado). */
export interface EtapaTrayectoria extends Asignacion {
  /** Inicio de la trayectoria a la que pertenece la etapa. */
  trayectoria_inicio: string | null;
  estado_etapa: 'cerrada' | 'vigente' | 'programada';
  /** Días de pastoreo (fin - inicio + 1), null si la etapa está abierta. */
  dias_planificados: number | null;
  /** Días transcurridos hasta hoy si la etapa ya empezó. */
  dias_transcurridos: number | null;
}

/** Una trayectoria (ventana de hasta 7 días desde `inicio`) de un lote. */
export interface Trayectoria {
  inicio: string | null;
  /** Ventana de 7 días desde inicio (para el editor); null en filas legadas. */
  dias: string[] | null;
  etapas: EtapaTrayectoria[];
  /** Si está marcada como finalizada → pasó al historial (Rotaciones finalizadas). */
  finalizada: boolean;
  /** Cuándo se finalizó (ISO); null si aún está en curso. */
  finalizada_en: string | null;
}

/** Lote con sus trayectorias independientes (no se repiten días entre ellas). */
export interface TrayectoriaLote {
  rodeo_id: number;
  rodeo: string;
  color: string | null;
  cabezas: number;
  peso_prom_kg: number;
  consumo_pct: number;
  consumo_diario_ms_kg: number;
  trayectorias: Trayectoria[];
}

export interface TrayectoriaResponse {
  trayectoria: TrayectoriaLote[];
}

/** Un día del camino semanal: las parcelas asignadas ese día (pueden ser varias). */
export interface DiaSemana {
  fecha: string;
  parcelas: { parcela_id: number; parcela: string | null }[];
}

export interface SemanaResponse {
  guardado: boolean;
  inicio: string;
  dias: DiaSemana[];
}

/** Semáforo de días de pastoreo por parcela (espejo del backend). */
export type SemaforoBalance = 'urgente' | 'atento' | 'ok' | 'sin_dato' | 'libre';

export interface RodeoBalance {
  rodeo_id: number;
  rodeo: string;
  cabezas: number;
  consumo_diario_kg: number;
}

export interface ParcelaBalance {
  parcela_id: number;
  parcela: string;
  potrero_id: number;
  potrero: string | null;
  finca: string;
  estado: string;
  area_ha: number | null;
  masa_total_kg: number | null;
  t_ha_total: number | null;
  tiene_calculo: boolean;
  estimado_por_prorrateo: boolean;
  consumo_diario_kg: number | null;
  ocupada: boolean;
  rodeos: RodeoBalance[];
  dias_pastoreo: number | null;
  semaforo: SemaforoBalance;
}

export interface ResumenBalance {
  parcelas_total: number;
  consumo_diario_total_kg: number;
  oferta_total_kg: number;
  parcelas_pastoreo: number;
  dias_promedio: number | null;
}

export interface BalanceResponse {
  fecha: string | null;
  finca: string;
  utilizacion_pct: number;
  resumen: ResumenBalance;
  parcelas: ParcelaBalance[];
}

/** Categorías fijas (espejo del backend): al elegir precargan peso y consumo. */
export const CATEGORIAS_RODEO: { id: string; label: string; peso: number; consumo: number }[] = [
  { id: 'vaca_lactancia', label: 'Vaca con cría', peso: 450, consumo: 2.8 },
  { id: 'vaca_seca', label: 'Vaca seca', peso: 420, consumo: 2.0 },
  { id: 'vaquillona', label: 'Vaquillona', peso: 300, consumo: 2.5 },
  { id: 'novillo', label: 'Novillo', peso: 380, consumo: 2.6 },
  { id: 'toro', label: 'Toro', peso: 650, consumo: 2.0 },
  { id: 'ternero', label: 'Ternero/a destete', peso: 180, consumo: 3.0 },
];

export interface LoginResponse {
  access_token: string;
  token_type: string;
  id: number;
  nombre: string;
  email: string;
}

export interface PotreroItem {
  id: number;
  nombre: string;
  finca: string;
}

export interface PotreroDetalleFeature {
  type: 'Feature';
  geometry: unknown;
  properties: { id: number; tipo: string; nombre: string; finca: string; subtipo?: string };
}

export interface PotreroDetalleResponse {
  type: 'FeatureCollection';
  features: PotreroDetalleFeature[];
}

export interface FotoCalibracion {
  id: number;
  url: string;
  fecha: string;
  latitud: number;
  longitud: number;
  mime: string;
  created_at: string;
}

export interface FotosCalibracionResponse {
  potrero_id: number;
  count: number;
  fotos: FotoCalibracion[];
}

export interface SubidaFotoResponse {
  id: number;
  url: string;
  usuario_id: number;
  potrero_id: number;
  potrero: string;
  finca: string;
  fecha: string;
  latitud: number;
  longitud: number;
  created_at: string;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers ?? {}),
    },
  });
  if (res.status === 401) {
    forzarLogout();
    // Dejar que el router redirija; lanzamos para que la UI lo maneje.
    throw new Error('No autenticado (401). Iniciá sesión de nuevo.');
  }
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* body no JSON */
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

export const api = {
  health(): Promise<{ status: string; db: string }> {
    return request('/health');
  },
  registro(email: string, password: string): Promise<{ id: number; nombre: string; email: string }> {
    return request('/api/auth/registro', { method: 'POST', body: JSON.stringify({ email, password }) });
  },
  async login(email: string, password: string): Promise<LoginResponse> {
    const data = await request<LoginResponse>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    setToken(data.access_token);
    return data;
  },
  logout() {
    setToken(null);
  },
  filtros(finca?: string | null): Promise<FiltrosResponse> {
    const q = finca ? `?finca=${encodeURIComponent(finca)}` : '';
    return request(`/api/mapa/filtros${q}`);
  },
  /** Potreros de la finca con su cálculo (t/ha) para colorear el mapa. Fecha opcional en gestión. */
  potreros(finca: string, fecha?: string | null): Promise<PotrerosResponse> {
    const q = fecha ? `&fecha=${encodeURIComponent(fecha)}` : '';
    return request(`/api/potreros/geojson?finca=${encodeURIComponent(finca)}${q}`);
  },
  /** Fincas que ya tienen potreros (existen en potreros_base, sin importar cálculos). */
  fincasConPotreros(): Promise<{ fincas: string[] }> {
    return request('/api/potreros/fincas');
  },
  /** Todas las parcelas de una finca (una llamada para el mapa). */
  parcelasFinca(finca: string, fecha?: string | null): Promise<ParcelasResponse> {
    const q = fecha ? `&fecha=${encodeURIComponent(fecha)}` : '';
    return request(`/api/parcelas/geojson?finca=${encodeURIComponent(finca)}${q}`);
  },
  sugerirNombreParcela(potreroId: number): Promise<{ potrero_id: number; nombre_sugerido: string }> {
    return request(`/api/parcelas/sugerir-nombre?potrero_id=${potreroId}`);
  },
  /** Zonas de exclusión de una finca (se dibujan en el mapa de gestión). */
  exclusiones(finca: string): Promise<ExclusionesResponse> {
    return request(`/api/exclusiones/geojson?finca=${encodeURIComponent(finca)}`);
  },
  crearParcela(potreroId: number, geom: unknown, estado = 'optimo', nombre?: string | null): Promise<{ id: number; potrero_id: number; nombre: string; estado: string; area_ha: number }> {
    return request(`/api/potreros/${potreroId}/parcelas`, { method: 'POST', body: JSON.stringify({ nombre: nombre ?? null, estado, geom }) });
  },
  actualizarParcela(id: number, datos: { estado?: string; geom?: unknown }): Promise<{ id: number; potrero_id: number; nombre: string; estado: string; area_ha: number }> {
    return request(`/api/parcelas/${id}`, { method: 'PATCH', body: JSON.stringify(datos) });
  },
  eliminarParcela(id: number): Promise<{ id: number; eliminado: boolean }> {
    return request(`/api/parcelas/${id}`, { method: 'DELETE' });
  },
  detalleParcela(id: number, fecha?: string | null): Promise<ParcelaDetalle> {
    const q = fecha ? `?fecha=${encodeURIComponent(fecha)}` : '';
    return request(`/api/parcelas/${id}${q}`);
  },
  /** Serie temporal de stock: agregada por finca, de un lote o de una parcela. */
  serie(finca: string, potreroId?: number | null, parcelaId?: number | null): Promise<SerieResponse> {
    const q = potreroId != null ? `&potrero_id=${potreroId}` : '';
    const qp = parcelaId != null ? `&parcela_id=${parcelaId}` : '';
    return request(`/api/dashboard/serie?finca=${encodeURIComponent(finca)}${q}${qp}`);
  },
  /** Histograma comparado verde/muerta/total sobre bines comunes (finca, lote o parcela). */
  histograma(finca: string, fecha: string, bins = 20, potreroId?: number | null, parcelaId?: number | null): Promise<HistogramaResponse> {
    const pot = potreroId != null ? `&potrero_id=${potreroId}` : '';
    const par = parcelaId != null ? `&parcela_id=${parcelaId}` : '';
    return request(`/api/mapa/histograma?finca=${encodeURIComponent(finca)}&fecha=${encodeURIComponent(fecha)}&bins=${bins}${pot}${par}`);
  },
  /** Parcelas de un potrero (liviano, sin zonal: para sub-selectores). */
  parcelasDePotrero(potreroId: number): Promise<ParcelasResponse> {
    return request(`/api/potreros/${potreroId}/parcelas`);
  },
  /** Rodeos propios con consumo diario calculado. */
  rodeosLista(): Promise<RodeosResponse> {
    return request('/api/rodeos');
  },
  /** Crea un rodeo (sin consumo_pct usa el sugerido de la categoría). */
  crearRodeo(datos: { nombre: string; categoria: string; cabezas: number; peso_prom_kg: number; consumo_pct?: number | null; notas?: string | null; color?: string | null }): Promise<Rodeo> {
    return request('/api/rodeos', { method: 'POST', body: JSON.stringify(datos) });
  },
  /** Actualiza un rodeo propio. */
  actualizarRodeo(id: number, datos: { nombre?: string; categoria?: string; cabezas?: number; peso_prom_kg?: number; consumo_pct?: number | null; notas?: string | null; color?: string | null }): Promise<Rodeo> {
    return request(`/api/rodeos/${id}`, { method: 'PATCH', body: JSON.stringify(datos) });
  },
  /** Elimina un rodeo propio. */
  eliminarRodeo(id: number): Promise<{ id: number; eliminado: boolean }> {
    return request(`/api/rodeos/${id}`, { method: 'DELETE' });
  },
  /** Rotación: historial + estado actual del pastoreo + resumen. */
  rotacionLista(): Promise<RotacionResponse> {
    return request('/api/rotacion');
  },
  /** Trayectoria de la semana por lote (para la vista Rotación). */
  trayectoriaRotacion(): Promise<TrayectoriaResponse> {
    return request('/api/rotacion/trayectoria');
  },
  /** Reescribe una trayectoria (ventana de 1 a 7 días desde inicio) de un rodeo.
   *  reemplazar_inicio: al editar, inicio de la trayectoria anterior a reemplazar. */
  semana(rodeo_id: number, inicio: string, dias: number[][], reemplazar_inicio?: string | null): Promise<SemanaResponse> {
    return request('/api/rotacion/semana', { method: 'POST', body: JSON.stringify({ rodeo_id, inicio, dias, reemplazar_inicio }) });
  },
  /** Borra una trayectoria completa de un lote (ventana de 7 días desde inicio). */
  eliminarTrayectoria(rodeo_id: number, inicio: string): Promise<{ inicio: string; eliminado: boolean; asignaciones: number }> {
    return request(`/api/rotacion/trayectoria/${rodeo_id}/${inicio}`, { method: 'DELETE' });
  },
  /** Marca una trayectoria como finalizada → pasa al historial. Si
 *  enviar_critico, además todas sus parcelas pasan a estado 'critico'. */
  finalizarTrayectoria(rodeo_id: number, inicio: string, enviar_critico = false): Promise<{ inicio: string; finalizada: true; parcelas_a_critico: number }> {
    return request(`/api/rotacion/trayectoria/${rodeo_id}/${inicio}/finalizar`, {
      method: 'POST',
      body: JSON.stringify({ enviar_critico }),
    });
  },
  /** Cierra un pastoreo (fecha_salida) o edita notas. */
  actualizarAsignacion(id: number, datos: { fecha_salida?: string; notas?: string }): Promise<Asignacion> {
    return request(`/api/rotacion/${id}`, { method: 'PATCH', body: JSON.stringify(datos) });
  },
  /** Balance forrajero por parcela: oferta (fecha) vs consumo actual de los rodeos. */
  balance(finca: string, fecha?: string | null, utilizacion = 50): Promise<BalanceResponse> {
    const q = fecha ? `&fecha=${encodeURIComponent(fecha)}` : '';
    return request(`/api/balance?finca=${encodeURIComponent(finca)}${q}&utilizacion=${utilizacion}`);
  },
  /** Potreros del usuario (liviano, para selector de calibración). */
  potrerosLista(): Promise<{ potreros: PotreroItem[] }> {
    return request('/api/potreros');
  },
  /** Detalle GeoJSON de un potrero + exclusiones. */
  potreroDetalle(id: number): Promise<PotreroDetalleResponse> {
    return request(`/api/potreros/${id}`);
  },
  /** Fotos de calibración de un potrero. */
  fotosDePotrero(potreroId: number): Promise<FotosCalibracionResponse> {
    return request(`/api/calibracion/fotos?potrero_id=${potreroId}`);
  },
  /** Sube una foto de calibración (multipart). */
  async subirFoto(potreroId: number, latitud: number, longitud: number, fecha: string, foto: File): Promise<SubidaFotoResponse> {
    const token = getToken();
    const form = new FormData();
    form.append('potrero_id', String(potreroId));
    form.append('latitud', String(latitud));
    form.append('longitud', String(longitud));
    form.append('fecha', fecha);
    form.append('foto', foto);
    const res = await fetch(`${API_URL}/api/calibracion/fotos`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    });
    if (res.status === 401) {
      forzarLogout();
      throw new Error('No autenticado (401). Iniciá sesión de nuevo.');
    }
    if (!res.ok) {
      let detail = `${res.status} ${res.statusText}`;
      try {
        const body = await res.json();
        if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
      } catch {
        /* body no JSON */
      }
      throw new Error(detail);
    }
    return (await res.json()) as SubidaFotoResponse;
  },
  /** URL absoluta de una foto subida. */
  fotoUrl(path: string): string {
    return `${API_URL}${path}`;
  },
};
