import { Suspense, lazy, useCallback, useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { api, CATEGORIAS_RODEO, type Asignacion, type BalanceResponse, type EtapaTrayectoria, type ParcelaBalance, type Rodeo, type Trayectoria, type TrayectoriaLote } from '../lib/api';
import { useAuth } from '../lib/auth';
import Sidebar from '../components/Sidebar';
import Topbar from '../components/Topbar';
import ErrorBoundary from '../components/ErrorBoundary';
import {
  PALETA_ROTACION, colorDeRodeoRegistrado, fmtFecha, isoHoy,
} from '../lib/rotacion';
import type { MapaRotacionParcelaFeature, SecuenciaPin } from '../components/MapaRotacion';
import type { PotreroFeature } from '../components/MapaMasaSeca';

// Lazy: maplibre solo se carga al ver el mapa de trayectorias.
const MapaRotacion = lazy(() => import('../components/MapaRotacion'));

type Tab = 'lotes' | 'rotacion' | 'trayectorias';

/** Título de la sección visible (según la ruta, no hay pestañas). */
const TITULOS: Record<Tab, string> = {
  lotes: 'Gestión de lotes',
  rotacion: 'Rotación',
  trayectorias: 'Trayectorias',
};

const fmtInt = (v: number) => v.toLocaleString('es-AR', { maximumFractionDigits: 0 });
const fmt1 = (v: number) => v.toLocaleString('es-AR', { maximumFractionDigits: 1 });

const ESTADO_ETAPA_COLOR = {
  vigente: '#15803d',
  programada: '#b45309',
  cerrada: '#6b7280',
} as const;

/** Leyenda de colores del mapa: estados de parcela + base del potrero. */
const LEYENDA_COLORES_MAPA = [
  { id: 'critico', label: 'Crítico', color: '#ef4444' },
  { id: 'desarrollo', label: 'Desarrollo', color: '#facc15' },
  { id: 'optimo', label: 'Óptimo', color: '#22c55e' },
  { id: 'maduro', label: 'Maduro', color: '#8b5cf6' },
  { id: 'pasado', label: 'Pasado', color: '#86198f' },
  { id: 'potrero-vacio', label: 'Potrero vacío', color: '#233D39' },
] as const;

/** Cara de vaca: identifica a un lote en las listas, coloreada con su color. */
const IconoLote = ({ size = 24 }: { size?: number }) => (
  <svg
    width={size}
    height={size}
viewBox="2 3 20 13.5"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <path d="M8 6.5 6 3.5" />
    <path d="M16 6.5 18 3.5" />
    <path d="M4.8 10a6.8 6.8 0 0 1 14.4 0v3.6a2.6 2.6 0 0 1-2.6 2.6H7.4a2.6 2.6 0 0 1-2.6-2.6V10Z" />
    <path d="m10.2 13.2 1.8 1.8 1.8-1.8" />
    <circle cx="9" cy="10.2" r="0.85" fill="currentColor" stroke="none" />
    <circle cx="15" cy="10.2" r="0.85" fill="currentColor" stroke="none" />
  </svg>
);

/** Suma n días a una fecha ISO (yyyy-mm-dd) sin tocar la zona horaria local. */
const addDias = (iso: string, n: number) => {
  const d = new Date(`${iso}T12:00:00`);
  d.setDate(d.getDate() + n);
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${m}-${dd}`;
};

/** Días (ISO) de la semana que arranca en la fecha dada. */
const semana = (iso: string): string[] => Array.from({ length: 7 }, (_, i) => addDias(iso, i));

/** Semana vacía: 7 días, cada uno con su lista de parcelas. */
const semanaVacia = (): string[][] => Array.from({ length: 7 }, () => []);

/** Etiqueta de un día del plan: Hoy/Mañana si arranca hoy; si no, Día 1..7. */
const diaLabel = (i: number, inicio: string): string => {
  if (inicio === isoHoy()) return i === 0 ? 'Hoy' : i === 1 ? 'Mañana' : `+${i} días`;
  return `Día ${i + 1}`;
};

/** Gestión de rodeos: quién come (base de rotación y balance). */
export default function GestionRodeos() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [colapsado, setColapsado] = useState(false);
  /** Sección visible según la ruta: /rodeos, /rodeos/rotacion, /rodeos/trayectorias. */
  const { pathname } = useLocation();
  const tab: Tab = pathname.endsWith('/rotacion')
    ? 'rotacion'
    : pathname.endsWith('/trayectorias') ? 'trayectorias' : 'lotes';
  const [rodeos, setRodeos] = useState<Rodeo[]>([]);
  const [totalCab, setTotalCab] = useState(0);
  const [totalCons, setTotalCons] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [formAbierto, setFormAbierto] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [nombre, setNombre] = useState('');
  const [categoria, setCategoria] = useState(CATEGORIAS_RODEO[0].id);
  const [cabezas, setCabezas] = useState('50');
  const [peso, setPeso] = useState(String(CATEGORIAS_RODEO[0].peso));
  const [consumo, setConsumo] = useState(String(CATEGORIAS_RODEO[0].consumo));
  const [notas, setNotas] = useState('');
  const [colorSel, setColorSel] = useState('');
  const [guardando, setGuardando] = useState(false);

  // Lista de rodeos: edición rápida de cabezas.
  const [editCabId, setEditCabId] = useState<number | null>(null);
  const [editCabVal, setEditCabVal] = useState('');

  // ---- Rotación ----
  const [rotFincas, setRotFincas] = useState<string[]>([]);
  const [rotFinca, setRotFinca] = useState('');
  const [rotParcelas, setRotParcelas] = useState<MapaRotacionParcelaFeature[]>([]);
  const [rotPotreros, setRotPotreros] = useState<PotreroFeature[]>([]);
  const [estadoActual, setEstadoActual] = useState<Asignacion[]>([]);
  const [asignaciones, setAsignaciones] = useState<Asignacion[]>([]);
  const [rotLoading, setRotLoading] = useState(false);
  const [rotError, setRotError] = useState<string | null>(null);
  const [rotMsg, setRotMsg] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<{ mensaje: string; onOk: () => void; onNo?: () => void } | null>(null);
  const [parcelaSel, setParcelaSel] = useState<number | null>(null);
  const [loteSel, setLoteSel] = useState<number | null>(null);

  // ---- Trayectoria de la semana por lote ----
  const [trayectoria, setTrayectoria] = useState<TrayectoriaLote[]>([]);
  const [trayLoading, setTrayLoading] = useState(false);
  const [trayError, setTrayError] = useState<string | null>(null);

  // ---- Plan semanal: trayecto de 7 días (varias parcelas por día + residuo) ----
  const [planAbierto, setPlanAbierto] = useState(false);
  const [planRodeoId, setPlanRodeoId] = useState('');
  const [planInicio, setPlanInicio] = useState(isoHoy());
  const [planDias, setPlanDias] = useState<string[][]>(() => semanaVacia());
  /** Inicio de la trayectoria que se está editando (null = trayectoria nueva). */
  const [planReemplaza, setPlanReemplaza] = useState<string | null>(null);
  const [utilizacion, setUtilizacion] = useState<40 | 50 | 60>(50);
  const [planGuardando, setPlanGuardando] = useState(false);

  // ---- Cerrar pastoreo ----
  const [cerrarId, setCerrarId] = useState<number | null>(null);
  const [cerrarFecha, setCerrarFecha] = useState('');

  // ---- Balance por parcela (días de forraje que aguanta) ----
  const [oferta, setOferta] = useState<BalanceResponse | null>(null);

  const recargar = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const d = await api.rodeosLista();
      setRodeos(d.rodeos);
      setTotalCab(d.total_cabezas);
      setTotalCons(d.total_consumo_diario_ms_kg);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error cargando lotes');
      setRodeos([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void recargar(); }, [recargar]);

  // ---- Rotación: carga ----
  const cargarRotacion = useCallback(async () => {
    setRotError(null);
    setRotLoading(true);
    try {
      const d = await api.rotacionLista();
      setAsignaciones(d.asignaciones);
      setEstadoActual(d.estado_actual);
    } catch (e) {
      setRotError(e instanceof Error ? e.message : 'Error cargando rotación');
      setAsignaciones([]);
      setEstadoActual([]);
    } finally {
      setRotLoading(false);
    }
  }, []);

  /** Trayectoria semanal por lote (etapas cerradas → vigente → programadas). */
  const cargarTrayectoria = useCallback(async () => {
    setTrayError(null);
    setTrayLoading(true);
    try {
      const d = await api.trayectoriaRotacion();
      setTrayectoria(d.trayectoria);
    } catch (e) {
      setTrayError(e instanceof Error ? e.message : 'Error cargando trayectoria');
      setTrayectoria([]);
    } finally {
      setTrayLoading(false);
    }
  }, []);

  /** Días de forraje por parcela (balance) para el semáforo "aguanta N d". */
  const cargarBalance = useCallback(async () => {
    if (!rotFinca) {
      setOferta(null);
      return;
    }
    try {
      setOferta(await api.balance(rotFinca));
    } catch {
      setOferta(null);
    }
  }, [rotFinca]);

  const cargarGeosRot = useCallback(async (finca: string) => {
    if (!finca) {
      setRotParcelas([]);
      setRotPotreros([]);
      return;
    }
    try {
      const [pd, pt] = await Promise.all([
        api.parcelasFinca(finca),
        api.potreros(finca),
      ]);
      setRotParcelas(pd.features.map((f) => ({
        type: 'Feature',
        geometry: f.geometry as MapaRotacionParcelaFeature['geometry'],
        properties: {
          id: f.properties.id,
          nombre: f.properties.nombre,
          finca: f.properties.finca,
          potrero_id: f.properties.potrero_id,
          estado: f.properties.estado,
          area_ha: f.properties.area_ha,
        },
      })));
      setRotPotreros(pt.features.map((f) => ({
        type: 'Feature',
        geometry: f.geometry as PotreroFeature['geometry'],
        properties: f.properties,
      })));
    } catch (e) {
      setRotError(e instanceof Error ? e.message : 'Error cargando parcelas');
      setRotParcelas([]);
    }
  }, []);

  useEffect(() => {
    api.fincasConPotreros()
      .then((d) => {
        setRotFincas(d.fincas);
        if (d.fincas.length === 1) setRotFinca(d.fincas[0]);
      })
      .catch(() => setRotFincas([]));
  }, []);

  useEffect(() => {
    if (tab !== 'rotacion' && tab !== 'trayectorias') return;
    void cargarRotacion();
  }, [tab, cargarRotacion]);

  useEffect(() => {
    if (tab !== 'rotacion' && tab !== 'trayectorias') return;
    void cargarGeosRot(rotFinca);
  }, [tab, rotFinca, cargarGeosRot]);

  useEffect(() => {
    if (tab !== 'rotacion' && tab !== 'trayectorias') return;
    void cargarTrayectoria();
  }, [tab, cargarTrayectoria]);

  useEffect(() => {
    if (tab !== 'rotacion' || !rotFinca) return;
    void cargarBalance();
  }, [tab, rotFinca, cargarBalance]);

  // ---- Rotación: acciones ----
  const ubicacionRodeo = useMemo(() => {
    const m = new Map<number, Asignacion>();
    for (const a of estadoActual) if (!m.has(a.rodeo_id)) m.set(a.rodeo_id, a);
    return m;
  }, [estadoActual]);

  const coloresUsados = useMemo(
    () => new Set(rodeos.filter((r) => r.id !== editId && r.color).map((r) => r.color as string)),
    [rodeos, editId],
  );

  const guardarCabezas = async (r: Rodeo) => {
    const n = Math.floor(Number(editCabVal));
    if (!(n >= 1)) { setEditCabId(null); return; }
    try {
      await api.actualizarRodeo(r.id, { cabezas: n });
      setEditCabId(null);
      await recargar();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo actualizar cabezas');
      setEditCabId(null);
    }
  };

  /** Secuencia de pastoreo por parcela para los pins del mapa. */
  const secuencias = useMemo(() => {
    const mapa = new Map<number, SecuenciaPin>();
    for (const lote of trayectoria) {
      const color = colorDeRodeoRegistrado(rodeos, estadoActual, lote.rodeo_id);
      const etapas = lote.trayectorias
        .flatMap((t) => t.etapas)
        .sort((a, b) => a.fecha_entrada.localeCompare(b.fecha_entrada));
      let num = 1;
      for (const e of etapas) {
        if (!mapa.has(e.parcela_id)) {
          mapa.set(e.parcela_id, {
            numero: num,
            color,
            estado: e.estado_etapa,
            cabezas: lote.cabezas,
          });
          num++;
        }
      }
    }
    return mapa;
  }, [trayectoria, rodeos, estadoActual]);

  /** Masa/t/ha por parcela desde el balance (para el semáforo del plan). */
  const balById = useMemo(() => {
    const m = new Map<number, ParcelaBalance>();
    if (oferta) for (const p of oferta.parcelas) m.set(p.parcela_id, p);
    return m;
  }, [oferta]);

  /** Fechas de la semana que arranca en el día elegido como inicio. */
  const fechasPlan = useMemo(() => semana(planInicio), [planInicio]);

  /** Días (ISO) ya cubiertos por otras trayectorias del lote en el editor:
   * se bloquean para no repetir fechas entre trayectorias independientes.
   * Al editar una trayectoria se excluyen sus propios días. */
  const planBloqueados = useMemo(() => {
    const s = new Set<string>();
    const rid = Number(planRodeoId);
    const lt = rid ? trayectoria.find((t) => t.rodeo_id === rid) : undefined;
    if (!lt) return s;
    for (const tr of (lt.trayectorias ?? [])) {
      if (planReemplaza && tr.inicio === planReemplaza) continue;
      for (const e of tr.etapas) {
        const fin = e.fecha_salida ?? e.fecha_entrada;
        let d = e.fecha_entrada;
        let i = 0;
        while (d <= fin && i < 3660) {
          s.add(d);
          d = addDias(d, 1);
          i += 1;
        }
      }
    }
    return s;
  }, [trayectoria, planRodeoId, planReemplaza]);

  /** Rodeo elegido en el editor del plan y su consumo diario. */
  const rodeoPlan = useMemo(
    () => rodeos.find((r) => r.id === Number(planRodeoId)) ?? null,
    [rodeos, planRodeoId],
  );
  const consumoPlan = rodeoPlan?.consumo_diario_ms_kg ?? null;

  /** Parcela elegida ese día por OTROS rodeos (bloquea el selector). */
  const ocupadosEnDia = useMemo(() => {
    const sets = fechasPlan.map(() => new Set<number>());
    const excluir = Number(planRodeoId);
    for (const a of asignaciones) {
      if (a.rodeo_id === excluir) continue;
      for (let i = 0; i < 7; i += 1) {
        const f = fechasPlan[i];
        if (f >= a.fecha_entrada && (a.fecha_salida == null || f <= a.fecha_salida)) sets[i].add(a.parcela_id);
      }
    }
    return sets;
  }, [asignaciones, planRodeoId, fechasPlan]);

  /** Balance diario con residuo: cada día suma el sobrante del anterior.
   * disponible = residuo anterior + Σ (masa × utilización%) de sus parcelas. */
  const ledger = useMemo(() => {
    const R = consumoPlan;
    const dias: {
      residuo: number; aporta: number; disponible: number;
      sobra: number; falta: number | null; cubierto: boolean;
    }[] = [];
    let res = 0;
    for (let i = 0; i < 7; i += 1) {
      let aporta = 0;
      for (const pidStr of planDias[i]) {
        const b = balById.get(Number(pidStr));
        const m = b?.masa_total_kg;
        if (m != null && m > 0) aporta += m * utilizacion / 100;
      }
      const disponible = res + aporta;
      let sobra = 0;
      let falta: number | null = null;
      let cubierto = false;
      if (R != null) {
        sobra = Math.max(0, disponible - R);
        falta = Math.max(0, R - disponible);
        cubierto = disponible >= R;
      }
      dias.push({ residuo: res, aporta, disponible, sobra, falta, cubierto });
      res = R != null ? sobra : 0;
    }
    return dias;
  }, [planDias, balById, consumoPlan, utilizacion]);


  /** Camino actual de un rodeo mapeado a una semana (lista de parcelas por día). */
  const caminoDe = useCallback((rid: number, fechas: string[] = fechasPlan): string[][] => {
    const arr: string[][] = fechas.map(() => []);
    const propias = asignaciones
      .filter((a) => a.rodeo_id === rid)
      .sort((x, y) => (x.fecha_entrada === y.fecha_entrada
        ? x.id - y.id
        : x.fecha_entrada < y.fecha_entrada ? -1 : 1));
    for (const a of propias) {
      for (let i = 0; i < fechas.length; i += 1) {
        const f = fechas[i];
        if (f >= a.fecha_entrada && (a.fecha_salida == null || f <= a.fecha_salida)) {
          const s = String(a.parcela_id);
          if (arr[i][arr[i].length - 1] !== s) arr[i].push(s);
        }
      }
    }
    return arr;
  }, [asignaciones, fechasPlan]);

  /** Parcelas usadas por CUALQUIER rodeo en toda esta semana (bloquean al resto: cada
   * parcela entra una sola vez por semana entre todos los rodeos). */
  const elegidasSemana = useMemo(() => {
    const s = new Set<number>();
    for (const r of rodeos) {
      for (const dia of caminoDe(r.id, fechasPlan)) {
        for (const v of dia) {
          const n = Number(v);
          if (Number.isFinite(n) && n > 0) s.add(n);
        }
      }
    }
    for (const dia of planDias) {
      for (const v of dia) {
        const n = Number(v);
        if (v !== '' && Number.isFinite(n) && n > 0) s.add(n);
      }
    }
    return s;
  }, [rodeos, fechasPlan, caminoDe, planDias]);

  const abrirPlan = (rid?: number, reemplaza?: string | null) => {
    setRotError(null);
    setRotMsg(null);
    setPlanGuardando(false);
    setPlanAbierto(true);
    setPlanReemplaza(reemplaza ?? null);
    if (rid != null) {
      setPlanRodeoId(String(rid));
      if (reemplaza) {
        // Edición de una trayectoria existente: su ventana desde su inicio.
        setPlanInicio(reemplaza);
        setPlanDias(caminoDe(rid, semana(reemplaza)));
      } else {
        // Trayectoria nueva: arranca hoy o el siguiente día libre del lote.
        const s = new Set<string>();
        const lt = trayectoria.find((t) => t.rodeo_id === rid);
        if (lt) for (const tr of (lt.trayectorias ?? [])) for (const e of tr.etapas) {
          const fin = e.fecha_salida ?? e.fecha_entrada;
          let d = e.fecha_entrada;
          let i = 0;
          while (d <= fin && i < 3660) {
            s.add(d);
            d = addDias(d, 1);
            i += 1;
          }
        }
        let ini = isoHoy();
        while (s.has(ini)) ini = addDias(ini, 1);
        setPlanInicio(ini);
        setPlanDias(caminoDe(rid, semana(ini)));
      }
    } else {
      setPlanRodeoId('');
      setPlanInicio(isoHoy());
      setPlanDias(semanaVacia());
    }
  };

  /** Al cambiar el día de inicio se re-mapea el camino a la nueva semana. */
  const onPlanInicio = (v: string) => {
    setPlanInicio(v);
    const nf = semana(v);
    const rid = planRodeoId ? Number(planRodeoId) : null;
    setPlanDias(rid ? caminoDe(rid, nf) : semanaVacia());
  };

  /** Al elegir una parcela un día se pone elegida solo ese día. Su cobertura
   * (cuántos días alcanza su masa) se ve en el mensaje del balance. */
  const setDiaPlan = (i: number, idx: number, v: string) => {
    setPlanDias((prev) =>
      prev.map((d, di) => (di === i ? d.map((x, xi) => (xi === idx ? v : x)) : d)),
    );
  };

  const agregarParcela = (i: number) => {
    setPlanDias((prev) => prev.map((dia, di) => (di === i ? [...dia, ''] : dia)));
  };

  const quitarParcela = (i: number, idx: number) => {
    setPlanDias((prev) => prev.map((dia, di) => (di === i ? dia.filter((_, xi) => xi !== idx) : dia)));
  };

  const guardarPlan = async () => {
    const rid = Number(planRodeoId);
    if (!rid) { setRotError('Elegí un lote para planificar su camino.'); return; }
    const diasCrudos: number[][] = planDias.map((lista) =>
      lista.map((v) => Number(v)).filter((x) => Number.isFinite(x) && x > 0),
    );
    const dias: number[][] = diasCrudos.map((d) => [...d]);
    if (consumoPlan != null && consumoPlan > 0) {
      for (let i = 0; i < 7; i += 1) {
        for (const pid of diasCrudos[i]) {
          const b = balById.get(pid);
          const ap = b?.masa_total_kg != null && b.masa_total_kg > 0
            ? b.masa_total_kg * utilizacion / 100
            : 0;
          if (ap <= 0) continue;
          const extra = Math.max(0, Math.ceil(ap / consumoPlan) - 1);
          for (let j = i + 1; j < 7 && j - i <= extra; j += 1) {
            if (planBloqueados.has(fechasPlan[j])) continue;  // no llenar días ocupados
            if (dias[j].length === 0) dias[j] = [pid];
          }
        }
      }
    }
    if (!dias.some((d) => d.length > 0)) { setRotError('Planificá al menos un día del camino.'); return; }
    setRotError(null);
    setRotMsg(null);
    setPlanGuardando(true);
    try {
      await api.semana(rid, planInicio, dias, planReemplaza);
      setPlanAbierto(false);
      await cargarRotacion();
      await cargarTrayectoria();
      await cargarBalance();
    } catch (e) {
      setRotError(e instanceof Error ? e.message : 'No se pudo guardar el camino');
    } finally {
      setPlanGuardando(false);
    }
  };

  const abrirCierreEtapa = (e: EtapaTrayectoria) => {
    setCerrarId(e.id);
    setCerrarFecha(isoHoy());
    setRotError(null);
    setRotMsg(null);
  };

  const cerrarPastoreo = async (asigId: number) => {
    if (!cerrarFecha) { setRotError('Fijá la fecha de salida.'); return; }
    setRotError(null);
    setRotMsg(null);
    try {
      const a = await api.actualizarAsignacion(asigId, { fecha_salida: cerrarFecha });
      setCerrarId(null);
      setRotMsg(`Pastoreo de ${a.rodeo} en ${a.parcela} cerrado el ${fmtFecha(cerrarFecha)}.`);
      await cargarRotacion();
      await cargarTrayectoria();
      await cargarBalance();
    } catch (e) {
      setRotError(e instanceof Error ? e.message : 'No se pudo cerrar el pastoreo');
    }
  };

  const pedirBorrarTrayectoria = (rid: number, inicio: string) => {
    setConfirm({
      mensaje: `¿Borrar esta trayectoria completa (desde el ${fmtFecha(inicio)})?`,
      onOk: () => { setConfirm(null); void borrarTrayectoria(rid, inicio); },
    });
  };

  const borrarTrayectoria = async (rid: number, inicio: string) => {
    setRotError(null);
    setRotMsg(null);
    try {
      const r = await api.eliminarTrayectoria(rid, inicio);
      setRotMsg(`Trayectoria del ${fmtFecha(inicio)} borrada (${r.asignaciones} etapa${r.asignaciones === 1 ? '' : 's'}).`);
      await cargarTrayectoria();
      await cargarRotacion();
      await cargarBalance();
    } catch (e) {
      setRotError(e instanceof Error ? e.message : 'No se pudo borrar la trayectoria');
    }
  };

  /** Primer paso: ¿finalizar?; si Sí, segunda pregunta: ¿parcelas a crítico? */
  const pedirFinalizar = (rid: number, inicio: string) => {
    setConfirm({
      mensaje: `¿Finalizar la trayectoria del ${fmtFecha(inicio)}? Pasará al historial de rotaciones finalizadas.`,
      onOk: () => setConfirm({
        mensaje: '¿Marcar también todas las parcelas de ese camino como crítico?',
        onOk: () => { setConfirm(null); void finalizarTrayectoria(rid, inicio, true); },
        onNo: () => { setConfirm(null); void finalizarTrayectoria(rid, inicio, false); },
      }),
    });
  };

  const finalizarTrayectoria = async (rid: number, inicio: string, aCritico: boolean) => {
    setRotError(null);
    setRotMsg(null);
    try {
      const r = await api.finalizarTrayectoria(rid, inicio, aCritico);
      setRotMsg(
        r.parcelas_a_critico > 0
          ? `Trayectoria del ${fmtFecha(inicio)} finalizada y ${r.parcelas_a_critico} parcela${r.parcelas_a_critico === 1 ? '' : 's'} marcada${r.parcelas_a_critico === 1 ? '' : 's'} como crítico.`
          : `Trayectoria del ${fmtFecha(inicio)} finalizada y movida al historial.`
      );
      await cargarTrayectoria();
      await cargarRotacion();
      await cargarBalance();
      if (rotFinca) void cargarGeosRot(rotFinca);
    } catch (e) {
      setRotError(e instanceof Error ? e.message : 'No se pudo finalizar la trayectoria');
    }
  };

  /** Rango Desde → Hasta del conjunto de etapas de una trayectoria. */
  const rangoDe = (tr: Trayectoria): string => {
    if (tr.etapas.length === 0) return tr.inicio ? `desde ${fmtFecha(tr.inicio)}` : 'histórica';
    let min = tr.etapas[0].fecha_entrada;
    let max = tr.etapas[0].fecha_salida ?? tr.etapas[0].fecha_entrada;
    for (const e of tr.etapas) {
      if (e.fecha_entrada < min) min = e.fecha_entrada;
      const f = e.fecha_salida ?? e.fecha_entrada;
      if (f > max) max = f;
    }
    return `${fmtFecha(min)} → ${fmtFecha(max)}`;
  };

  const potrerosById = useMemo(
    () => new Map(rotPotreros.map((f) => [f.properties.id, f.properties.nombre])),
    [rotPotreros],
  );

  const nombresParcelaById = useMemo(
    () => new Map(rotParcelas.map((f) => [f.properties.id, f.properties.nombre])),
    [rotParcelas],
  );

  /** Parcelas agrupadas por potrero para el selector (mismas unidades que el mapa). */
  const parcelasPorPotrero = useMemo(() => {
    const m = new Map<number, MapaRotacionParcelaFeature[]>();
    for (const p of rotParcelas) {
      const pid = p.properties.potrero_id;
      if (!m.has(pid)) m.set(pid, []);
      m.get(pid)!.push(p);
    }
    return Array.from(m.entries()).sort((a, b) => a[0] - b[0]);
  }, [rotParcelas]);

  const abrirNuevo = () => {
    const c = CATEGORIAS_RODEO[0];
    setEditId(null);
    setNombre('');
    setCategoria(c.id);
    setCabezas('50');
    setPeso(String(c.peso));
    setConsumo(String(c.consumo));
    setNotas('');
    setColorSel('');
    setFormAbierto(true);
    setError(null);
    setMsg(null);
  };

  const abrirEditar = (r: Rodeo) => {
    setEditId(r.id);
    setNombre(r.nombre);
    setCategoria(r.categoria);
    setCabezas(String(r.cabezas));
    setPeso(String(r.peso_prom_kg));
    setConsumo(String(r.consumo_pct));
    setNotas(r.notas ?? '');
    setColorSel(r.color ?? '');
    setFormAbierto(true);
    setError(null);
    setMsg(null);
  };

  /** Al cambiar de categoría se precargan peso y consumo sugeridos. */
  const onCategoria = (id: string) => {
    setCategoria(id);
    const c = CATEGORIAS_RODEO.find((x) => x.id === id);
    if (c && editId == null) {
      setPeso(String(c.peso));
      setConsumo(String(c.consumo));
    }
  };

  /** Consumo estimado en vivo antes de guardar. */
  const estimado = useMemo(() => {
    const cab = Number(cabezas);
    const p = Number(peso);
    const c = Number(consumo);
    if (!(cab > 0) || !(p > 0) || !(c > 0)) return null;
    return (cab * p * c) / 100;
  }, [cabezas, peso, consumo]);

  const guardar = async () => {
    setError(null);
    setMsg(null);
    const cab = Number(cabezas);
    const p = Number(peso);
    const c = Number(consumo);
    if (!nombre.trim()) { setError('El nombre es requerido.'); return; }
    if (!(cab >= 1)) { setError('Cabezas: mínimo 1.'); return; }
    if (!(p > 0)) { setError('Peso prom: debe ser positivo.'); return; }
    if (!(c >= 0.5 && c <= 6)) { setError('Consumo: entre 0.5 y 6.0 %.'); return; }
    setGuardando(true);
    try {
      const datos = {
        nombre: nombre.trim(), categoria,
        cabezas: cab, peso_prom_kg: p, consumo_pct: c,
        notas: notas.trim() ? notas.trim() : null,
        color: colorSel || null,
      };
      if (editId == null) {
        await api.crearRodeo(datos);
      } else {
        const r = await api.actualizarRodeo(editId, datos);
        setMsg(`Lote ${r.nombre} actualizado.`);
      }
      setFormAbierto(false);
      await recargar();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo guardar');
    } finally {
      setGuardando(false);
    }
  };

  const eliminar = async (r: Rodeo) => {
    setConfirm({
      mensaje: `¿Eliminar el lote "${r.nombre}" (${r.cabezas} cabezas)? Se borra también su historial de pastoreo.`,
      onOk: () => { setConfirm(null); void _eliminar(r); },
    });
  };

  const _eliminar = async (r: Rodeo) => {
    setError(null);
    try {
      await api.eliminarRodeo(r.id);
      setMsg(`Lote ${r.nombre} eliminado.`);
      await recargar();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo eliminar');
    }
  };

  /** Lote elegido en las pestañas de Rotación (por defecto el primero). */
  const loteActual = trayectoria.length > 0
    ? trayectoria.find((l) => l.rodeo_id === loteSel) ?? trayectoria[0]
    : null;

  return (
    <div className="app-shell">
      <Sidebar
        colapsado={colapsado}
        onColapsar={() => setColapsado((c) => !c)}
        vista={tab}
        onVista={(v) => {
          if (v === 'lotes') navigate('/rodeos');
          else if (v === 'rotacion') navigate('/rodeos/rotacion');
          else if (v === 'trayectorias') navigate('/rodeos/trayectorias');
          else if (v === 'mapa') navigate('/mapa');
          else navigate(`/mapa?vista=${v}`);
        }}
      />

      <div className="main-col">
        <Topbar
          fincas={rotFincas}
          finca={rotFinca}
          onFinca={(v) => { setRotFinca(v); setParcelaSel(null); }}
          cargando={loading || rotLoading}
          nombre={user?.nombre ?? ''}
          email={user?.email ?? ''}
          onSalir={logout}
          notifCount={rodeos.length}
        />

        <main className="content">
          <div className="panel">
            <div className="serie-head">
              <h3>{TITULOS[tab]}</h3>
            </div>

            {tab === 'lotes' && (
              <>
                {error && <p className="error-text">{error}</p>}
                {msg && <p className="muted">{msg}</p>}
                {loading && <span className="muted">Cargando…</span>}

                {!formAbierto ? (
                  <div style={{ margin: '14px 0 18px' }}>
                    <button type="button" onClick={abrirNuevo}>+ Nuevo lote</button>
                  </div>
                ) : (
                  <div className="calib-block">
                    <h4 className="calib-title">{editId == null ? 'Nuevo lote' : 'Editar lote'}</h4>
                    <label>
                      Nombre
                      <input value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Nelores Blancos Nuevos" maxLength={50} />
                    </label>
                    <label>
                      Categoría
                      <select value={categoria} onChange={(e) => onCategoria(e.target.value)}>
                        {CATEGORIAS_RODEO.map((c) => (
                          <option key={c.id} value={c.id}>{c.label}</option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Cabezas
                      <input type="number" min={1} step={1} value={cabezas} onChange={(e) => setCabezas(e.target.value)} />
                    </label>
                    <label>
                      Peso prom (kg)
                      <input type="number" min={1} step={1} value={peso} onChange={(e) => setPeso(e.target.value)} />
                    </label>
                    <label>
                      Consumo (% PV en MS/día)
                      <input type="number" min={0.5} max={6} step={0.1} value={consumo} onChange={(e) => setConsumo(e.target.value)} />
                    </label>
                    <label>
                      Notas (opcional)
                      <input value={notas} onChange={(e) => setNotas(e.target.value)} placeholder="Ej. lote parejo, destete marzo" maxLength={280} />
                    </label>
                    <label>
                      Color de lote
                      <span style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                        <button
                          type="button"
                          onClick={() => setColorSel('')}
                          title="Color automático (recomendado): lo elige la app"
                          aria-label="Color automático"
                          style={{
                            width: 26, height: 26, borderRadius: 8, border: '1px solid #d1d5db',
                            background: 'repeating-linear-gradient(45deg, #e5e7eb 0 4px, #ffffff 4px 8px)',
                            outline: colorSel === '' ? '2px solid #111827' : 'none', outlineOffset: 2,
                            cursor: 'pointer',
                          }}
                        >
                          <span className="muted" style={{ fontSize: '0.6rem', fontWeight: 700 }}>A</span>
                        </button>
                        {PALETA_ROTACION.map((c) => {
                          const enUso = coloresUsados.has(c) && colorSel !== c;
                          return (
                            <button
                              key={c}
                              type="button"
                              onClick={() => setColorSel(colorSel === c ? '' : c)}
                              disabled={enUso}
                              title={enUso ? `Color ${c} ya usado por otro lote` : colorSel === c ? 'Clic para volver a automático' : `Fijar color ${c}`}
                              style={{
                                width: 26, height: 26, borderRadius: '50%', background: c, border: '1px solid #d1d5db',
                                outline: colorSel === c ? '2px solid #111827' : 'none', outlineOffset: 2,
                                opacity: enUso ? 0.25 : 1, cursor: enUso ? 'not-allowed' : 'pointer',
                              }}
                            />
                          );
                        })}
                        <span className="muted" style={{ fontSize: '0.75rem' }}>{colorSel === '' ? 'automático' : `color fijo ${colorSel}`}</span>
                      </span>
                    </label>
                    {estimado != null && (
                      <span className="muted">Consumo estimado: <strong>{fmt1(estimado)} kg MS/día</strong></span>
                    )}
                    <div className="calib-actions">
                      <button type="button" onClick={() => void guardar()} disabled={guardando}>
                        {guardando ? 'Guardando…' : 'Guardar'}
                      </button>
                      <button type="button" className="ghost-btn" onClick={() => setFormAbierto(false)}>Cancelar</button>
                    </div>
                  </div>
                )}

                {rodeos.length > 0 && (
                  <div className="comp-strip">
                    <div className="comp-strip-vals">
                      <span><em>Cabezas:</em> {fmtInt(totalCab)}</span>
                      <span className="sep">·</span>
                      <span><em>Consumo total:</em> {fmt1(totalCons)} kg MS/día</span>
                      <span className="sep">·</span>
                      <span><em>Lotes:</em> {rodeos.length}</span>
                    </div>
                  </div>
                )}

                {rodeos.length > 0 && (
                  <div className="tbl-scroll tbl-marco">
                    <table className="tbl-rod tbl-lotes">
                      <thead>
                        <tr>
                          <th>Lote</th>
                          <th className="num">Cabezas</th>
                          <th className="num">Peso<small>kg</small></th>
                          <th className="num">Consumo por Lote<small>% PV</small></th>
                          <th className="num">Consumo por Lote<small>kg MS/día</small></th>
                          <th>Hoy en</th>
                          <th />
                        </tr>
                      </thead>
                      <tbody>
                        {rodeos.map((r) => {
                          const ubi = ubicacionRodeo.get(r.id);
                          const color = colorDeRodeoRegistrado(rodeos, estadoActual, r.id);
                          return (
                            <tr key={r.id} onClick={() => abrirEditar(r)} title="Clic para editar">
                              <td>
                                <span className="lote-ico" style={{ color: r.color ?? color }}><IconoLote /></span>
                                <span style={{ marginLeft: 8, verticalAlign: 'middle' }}>
                                  <strong>{r.nombre}</strong>{' '}
                                  {r.categoria_label && <small className="muted">{r.categoria_label}</small>}
                                </span>
                              </td>
                              <td
                                className="num"
                                onClick={(e) => e.stopPropagation()}
                                style={{ cursor: 'default' }}
                              >
                                {editCabId === r.id ? (
                                  <input
                                    type="number"
                                    min={1}
                                    step={1}
                                    autoFocus
                                    value={editCabVal}
                                    onChange={(e) => setEditCabVal(e.target.value)}
                                    onBlur={() => void guardarCabezas(r)}
                                    onKeyDown={(e) => {
                                      if (e.key === 'Enter') void guardarCabezas(r);
                                      if (e.key === 'Escape') setEditCabId(null);
                                    }}
                                    style={{ maxWidth: 90 }}
                                  />
                                ) : (
                                  <span
                                    role="button"
                                    tabIndex={0}
                                    aria-label={`Editar cabezas de ${r.nombre}`}
                                    title="Editar cabezas"
                                    style={{ textDecoration: 'underline dotted', cursor: 'pointer' }}
                                    onClick={() => { setEditCabId(r.id); setEditCabVal(String(r.cabezas)); }}
                                    onKeyDown={(e) => { if (e.key === 'Enter') { setEditCabId(r.id); setEditCabVal(String(r.cabezas)); } }}
                                  >
                                    {fmtInt(r.cabezas)}
                                  </span>
                                )}
                              </td>
                              <td className="num">{fmt1(r.peso_prom_kg)}</td>
                              <td className="num">{fmt1(r.consumo_pct)}</td>
                              <td className="num">{fmt1(r.consumo_diario_ms_kg ?? 0)}</td>
                              <td title={ubi ? `${ubi.potrero} · desde ${fmtFecha(ubi.fecha_entrada)}` : undefined}>
                                {ubi ? <span style={{ color }}>{ubi.parcela}</span> : '—'}
                              </td>
                              <td className="num">
                                <span
                                  className="tbl-del"
                                  role="button"
                                  tabIndex={0}
                                  aria-label={`Eliminar ${r.nombre}`}
                                  title={`Eliminar ${r.nombre} (borra su historial de pastoreo)`}
                                  onClick={(e) => { e.stopPropagation(); void eliminar(r); }}
                                  onKeyDown={(e) => { if (e.key === 'Enter') { e.stopPropagation(); void eliminar(r); } }}
                                >
                                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                                    <path d="M3 6h18" />
                                    <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                                    <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
                                    <path d="M10 11v6" />
                                    <path d="M14 11v6" />
                                  </svg>
                                </span>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            )}

            {tab === 'rotacion' && (
              <>
                {rotError && <p className="error-text">{rotError}</p>}
                {rotMsg && <p className="muted">{rotMsg}</p>}
                {trayError && <p className="error-text">{trayError}</p>}
                {rotLoading && <span className="muted">Cargando…</span>}
                {trayLoading && <span className="muted">Cargando trayectoria…</span>}

                {!rotFinca ? (
                  <p className="muted">
                    Elegí una estancia para ver/cargar rotaciones. {rotFincas.length === 0 && 'Todavía no hay potreros cargados.'}
                  </p>
                ) : (
                  <>
                    {cerrarId != null && (
                      <div className="calib-block" style={{ margin: '12px 0' }}>
                        <h4 className="calib-title">Cerrar pastoreo</h4>
                        <label>
                          Fecha de salida
                          <input type="date" value={cerrarFecha} onChange={(e) => setCerrarFecha(e.target.value)} />
                        </label>
                        <div className="calib-actions">
                          <button type="button" onClick={() => void cerrarPastoreo(cerrarId)}>Cerrar</button>
                          <button type="button" className="ghost-btn" onClick={() => setCerrarId(null)}>Cancelar</button>
                        </div>
                      </div>
                    )}

                    {planAbierto && (
                      <div className="calib-block plan-block">
                        <h4 className="calib-title">
                          {planReemplaza
                            ? `Editar trayectoria · ${rodeoPlan?.nombre ?? ''} (desde ${fmtFecha(planReemplaza)})`
                            : `Nuevo camino ${rodeoPlan ? `· ${rodeoPlan.nombre}` : '· elegí el grupo'}`}
                        </h4>
                        <p className="muted" style={{ margin: '2px 0 8px' }}>
                          Ventana de 7 días sin repetir fechas entre trayectorias: los días ya usados por otro trayecto del lote quedan bloqueados.
                        </p>

                        <div className="plan-controls">
                          <label>
                            Inicio de la semana
                            <input type="date" value={planInicio} onChange={(e) => onPlanInicio(e.target.value)} />
                          </label>
                          <label>
                            Utilización (% aprovechable)
                            <span className="serie-legend tabs-rod" role="group" aria-label="Utilización del forraje">
                              {([40, 50, 60] as const).map((u) => (
                                <button
                                  key={u}
                                  type="button"
                                  className={utilizacion === u ? 'on' : 'off'}
                                  onClick={() => setUtilizacion(u)}
                                >
                                  {u}%
                                </button>
                              ))}
                            </span>
                          </label>
                        </div>

                        <div className="tbl-scroll">
                          <table className="tbl-rod">
                            <thead>
                              <tr>
                                <th>Día</th>
                                <th>Parcela(s)</th>
                                <th>Consumo por Lote{consumoPlan != null ? ` [${fmt1(consumoPlan)} kg MS/día]` : ''}</th>
                              </tr>
                            </thead>
                            <tbody>
                              {fechasPlan.map((f, i) => {
                                const line = ledger[i];
                                const diaOcupados = ocupadosEnDia[i];
                                const bloqueado = planBloqueados.has(f);
                                return (
                                  <tr key={f} style={{ verticalAlign: 'top' }}>
                                    <td>
                                        <span className="plan-fecha">{fmtFecha(f)}</span>
                                        {bloqueado && <span className="plan-bloq">ocupado</span>}
                                      </td>
                                    <td>
                                      {bloqueado ? (
                                        <span className="muted plan-bloq-note">Día ya cubierto por otra trayectoria del lote.</span>
                                      ) : (
                                      <div className="plan-col">
                                        {planDias[i].map((pidStr, idx) => {
                                          return (
                                            <div key={idx} className="plan-parcela">
                                              <select
                                                value={pidStr}
                                                onChange={(e) => setDiaPlan(i, idx, e.target.value)}
                                                aria-label={`Parcela ${idx + 1} del día ${diaLabel(i, planInicio)} (${fmtFecha(f)})`}
                                              >
                                                <option value="">— Elegir parcela —</option>
                                                {parcelasPorPotrero.map(([ppid, lista]) => (
                                                  <optgroup key={ppid} label={potrerosById.get(ppid) ?? `Potrero ${ppid}`}>
                                                    {lista
                                                      .map((p) => {
                                                        const o = balById.get(p.properties.id);
                                                        const ap = o?.masa_total_kg != null && o.masa_total_kg > 0
                                                          ? o.masa_total_kg * utilizacion / 100
                                                          : 0;
                                                        const extras: string[] = [];
                                                        if (ap > 0) extras.push(`${fmt1(ap)} kg`);
                                                        if (ap > 0 && consumoPlan != null && consumoPlan > 0) extras.push(`dura ${fmt1(ap / consumoPlan)}d`);
                                                        const critica = p.properties.estado === 'critico'
                                                          && p.properties.id !== Number(pidStr);
                                                        const blocked = diaOcupados.has(p.properties.id)
                                                          || (elegidasSemana.has(p.properties.id) && p.properties.id !== Number(pidStr));
                                                        if (critica) return null;
                                                        return (
                                                          <option
                                                            key={p.properties.id}
                                                            value={p.properties.id}
                                                            disabled={blocked}
                                                          >
                                                            {p.properties.nombre}{extras.length ? ` · ${extras.join(' · ')}` : ''} · {p.properties.estado}
                                                          </option>
                                                        );
                                                      })}
                                                  </optgroup>
                                                ))}
                                              </select>
                                              <span
                                                  className="tbl-del"
                                                  role="button"
                                                  tabIndex={0}
                                                  aria-label={`Quitar la parcela ${idx + 1} del día ${diaLabel(i, planInicio)}`}
                                                  title={`Quitar ${nombresParcelaById.get(Number(pidStr)) ?? `parcela ${pidStr}`}`}
                                                  onClick={() => quitarParcela(i, idx)}
                                                  onKeyDown={(ev) => { if (ev.key === 'Enter') quitarParcela(i, idx); }}
                                                >
                                                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                                                    <path d="M3 6h18" />
                                                    <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                                                    <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
                                                    <path d="M10 11v6" />
                                                    <path d="M14 11v6" />
                                                  </svg>
                                              </span>
                                            </div>
                                          );
                                        })}
                                        <button
                                            type="button"
                                            className="plan-agregar"
                                            aria-label={`Agregar parcela al día ${diaLabel(i, planInicio)}`}
                                            title={`Agregar una parcela al día ${diaLabel(i, planInicio)}`}
                                            onClick={() => agregarParcela(i)}
                                          >
                                            <span aria-hidden="true" className="plan-agregar-icono">+</span>
                                          </button>
                                      </div>
                                      )}
                                    </td>
                                    <td>
                                      {consumoPlan == null ? (
                                        <span className="comp-legend-chip" style={{ background: '#f3f4f6', color: '#6b7280' }}>
                                          elegí lote para calcular
                                        </span>
                                      ) : (
                                        <div
                                          className="cov"
                                          title={`Residuo de ayer: ${fmt1(line.residuo)} kg · aporte de hoy: ${fmt1(line.aporta)} kg`}
                                          style={{
                                            ['--res' as string]: `${consumoPlan > 0 && line.residuo > 0 ? Math.min(100, (line.residuo / consumoPlan) * 100) : 0}%`,
                                            ['--pct' as string]: `${consumoPlan > 0 ? Math.min(100, (line.disponible / consumoPlan) * 100) : 0}%`,
                                          }}
                                        >
                                          <div className={['cov-track', line.cubierto ? 'cov-ok' : planDias[i].length === 0 ? 'cov-libre' : 'cov-falta'].join(' ')}>
                                            {line.residuo > 0 && <span className="cov-res" />}
                                            <span className="cov-fill" />
                                          </div>
                                          <small className={['cov-agg', line.cubierto ? 'cov-ok' : planDias[i].length === 0 ? 'cov-libre' : 'cov-falta'].join(' ')}>
                                            {fmt1(Math.min(line.disponible, consumoPlan))} kg
                                          </small>
                                        </div>
                                      )}
                                    </td>
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        </div>

                        <div className="calib-actions">
                          <button type="button" onClick={() => void guardarPlan()} disabled={planGuardando}>
                            {planGuardando ? 'Guardando…' : 'Guardar camino'}
                          </button>
                          <button type="button" className="ghost-btn" onClick={() => setPlanAbierto(false)}>Cancelar</button>
                        </div>
                      </div>
                    )}

                    {!trayLoading && trayectoria.length === 0 ? (
                      <p className="muted" style={{ marginTop: 10 }}>
                        Aún no hay asignaciones en esta estancia. Asigná un lote a una parcela para armar su trayectoria semanal.
                      </p>
                    ) : (
                    <>
                    {trayectoria.length > 1 && (
                      <div className="serie-legend tabs-rod tray-tabs" role="tablist" aria-label="Lotes">
                        {trayectoria.map((lt) => (
                          <button
                            key={lt.rodeo_id}
                            role="tab"
                            aria-selected={lt.rodeo_id === loteActual?.rodeo_id}
                            type="button"
                            className={lt.rodeo_id === loteActual?.rodeo_id ? 'on' : 'off'}
                            onClick={() => setLoteSel(lt.rodeo_id)}
                          >
                            <span className="lote-tab">
                              <span className="lote-ico" style={{ color: colorDeRodeoRegistrado(rodeos, estadoActual, lt.rodeo_id) }}>
                                <IconoLote size={14} />
                              </span>
                              {lt.rodeo}
                            </span>
                          </button>
                        ))}
                      </div>
                    )}
                    {loteActual && (() => {
      const l = loteActual;
      const r = rodeos.find((x) => x.id === l.rodeo_id);
      const col = colorDeRodeoRegistrado(rodeos, estadoActual, l.rodeo_id);
      const trayectorias = l.trayectorias ?? [];
      const activas = trayectorias.filter((t) => !t.finalizada);
      const historial = trayectorias.filter((t) => t.finalizada);

      /** Tabla de una trayectoria en curso (con acciones editar/completar/borrar). */
      const traTabla = (tr: Trayectoria) => {
        const tInicio = tr.inicio;
        const accionable = tInicio != null;
        return (
          <div key={tInicio ?? 'legado'} className="tray-tra">
            <div className="tray-tra-header">
              <span className="tray-tra-rango">{rangoDe(tr)}</span>
              {accionable ? (
                <span className="tray-tra-actions">
                  <span
                    className="tray-icono"
                    role="button"
                    tabIndex={0}
                    aria-label={`Editar trayectoria del ${fmtFecha(tInicio)}`}
                    title="Editar esta trayectoria"
                    onClick={() => abrirPlan(l.rodeo_id, tInicio)}
                    onKeyDown={(ev) => { if (ev.key === 'Enter') abrirPlan(l.rodeo_id, tInicio); }}
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" />
                    </svg>
                  </span>
                  <span
                    className="tray-icono tray-icono-final"
                    role="button"
                    tabIndex={0}
                    aria-label={`Finalizar trayectoria del ${fmtFecha(tInicio)}`}
                    title="Finalizar y pasar al historial"
                    onClick={() => pedirFinalizar(l.rodeo_id, tInicio)}
                    onKeyDown={(ev) => { if (ev.key === 'Enter') pedirFinalizar(l.rodeo_id, tInicio); }}
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <path d="M20 6 9 17l-5-5" />
                    </svg>
                  </span>
                  <span
                    className="tray-icono tray-icono-peligro"
                    role="button"
                    tabIndex={0}
                    aria-label={`Borrar trayectoria del ${fmtFecha(tInicio)}`}
                    title="Borrar esta trayectoria"
                    onClick={() => pedirBorrarTrayectoria(l.rodeo_id, tInicio)}
                    onKeyDown={(ev) => { if (ev.key === 'Enter') pedirBorrarTrayectoria(l.rodeo_id, tInicio); }}
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <path d="M3 6h18" />
                      <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                      <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
                      <path d="M10 11v6" />
                      <path d="M14 11v6" />
                    </svg>
                  </span>
                </span>
              ) : (
                <span className="muted" style={{ fontStyle: 'italic', fontSize: '0.72rem' }}>histórica</span>
              )}
            </div>
            {tr.etapas.length === 0 ? (
              <p className="muted tray-sin-datos">Sin etapas en esta trayectoria.</p>
            ) : (
              <div className="tbl-scroll">
                <table className="tbl-rod">
                  <thead>
                    <tr>
                      <th>Parcela</th>
                      <th>Desde<small>→ Hasta</small></th>
                      <th>Estado</th>
                      <th className="num">Plan<small>días</small></th>
                      <th className="num">Va<small>días</small></th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {tr.etapas.map((e) => {
                      const plan = e.dias_planificados;
                      const esVigente = e.estado_etapa === 'vigente';
                      return (
                        <tr key={e.id} className={esVigente ? 'tbl-vigente' : undefined}>
                          <td>
                            <span
                              className="tray-parcela"
                              role="button"
                              tabIndex={0}
                              aria-label={`Ver ${e.parcela} en el mapa de trayectorias`}
                              onClick={() => { setParcelaSel(e.parcela_id); navigate('/rodeos/trayectorias'); }}
                              onKeyDown={(ev) => { if (ev.key === 'Enter') { setParcelaSel(e.parcela_id); navigate('/rodeos/trayectorias'); } }}
                            >
                              <strong>{e.parcela}</strong>
                            </span>
                          </td>
                          <td>
                            <span className="tray-rango">
                              {fmtFecha(e.fecha_entrada)}
                              <span className="tray-rango-arrow">→</span>
                              {e.fecha_salida ? fmtFecha(e.fecha_salida) : <span className="tray-rango-hoy">hoy</span>}
                            </span>
                          </td>
                          <td>
                            <span className="comp-legend-chip" style={{ color: ESTADO_ETAPA_COLOR[e.estado_etapa] }}>{e.estado_etapa}</span>
                          </td>
                          <td className="num">{plan != null ? `${fmt1(plan)}d` : '—'}</td>
                          <td
                            className="num"
                            style={esVigente && plan != null && (e.dias_transcurridos ?? 0) > plan ? { color: '#b91c1c', fontWeight: 700 } : undefined}
                          >{e.dias_transcurridos != null ? `${fmt1(e.dias_transcurridos)}d` : '—'}</td>
                          <td className="num">
                            {esVigente && (
                              <span style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
                                {e.fecha_salida == null && (
                                  <span
                                    className="tray-cerrar"
                                    role="button"
                                    tabIndex={0}
                                    aria-label={`Cerrar pastoreo en ${e.parcela}`}
                                    onClick={() => abrirCierreEtapa(e)}
                                    onKeyDown={(ev) => { if (ev.key === 'Enter') abrirCierreEtapa(e); }}
                                  >
                                    cerrar
                                  </span>
                                )}
                              </span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        );
      };
      return (
        <div className="tray-lotes">
        <div key={l.rodeo_id} className="tray-lote">
          <div className="lote-resumen">
            <span className="lote-ico" style={{ color: col }}><IconoLote /></span>
            <span className="lote-titulo">
              <strong>{l.rodeo}</strong>
              <span className="lote-meta">
                {r && (<>
                  <span>{r.categoria_label}</span>
                  <span aria-hidden="true">·</span>
                </>)}
                <span><b>{fmtInt(l.cabezas)}</b> cab</span>
                <span aria-hidden="true">·</span>
                <span><b>{fmt1(l.consumo_diario_ms_kg)}</b> kg MS/día</span>
              </span>
            </span>
            <span
              className="lote-editar"
              role="button"
              tabIndex={0}
              aria-label={`Nuevo camino para ${l.rodeo}`}
              title="Nuevo camino (próximo día libre)"
              onClick={() => abrirPlan(l.rodeo_id)}
              onKeyDown={(ev) => { if (ev.key === 'Enter') abrirPlan(l.rodeo_id); }}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" />
              </svg>
            </span>
          </div>
          {activas.length === 0 ? (
            <p className="muted tray-sin-datos">Sin trayectorias en curso.</p>
          ) : (
            <>
              <div className="tray-historial-titulo">Rotaciones en curso</div>
              {activas.map((tr) => traTabla(tr))}
            </>
          )}
          {historial.length > 0 && (
            <div className="tray-historial">
              <div className="tray-historial-titulo">Rotaciones finalizadas</div>
              <div className="tbl-scroll">
                <table className="tbl-rod">
                  <thead>
                    <tr>
                      <th>Fecha</th>
                      <th>Recorrido</th>
                      <th>Estado</th>
                      <th className="num">Plan<small>días</small></th>
                      <th className="num">Va<small>días</small></th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {historial.map((tr) => {
                      const desd = tr.etapas.length ? tr.etapas.map((e) => e.fecha_entrada).sort()[0] : null;
                      const hast = desd ? (tr.etapas.map((e) => e.fecha_salida ?? e.fecha_entrada).sort().at(-1) ?? desd) : null;
                      const planDias = desd && hast
                        ? Math.round((new Date(`${hast}T00:00:00`).getTime() - new Date(`${desd}T00:00:00`).getTime()) / 86400000) + 1
                        : 0;
                      return (
                        <tr key={tr.inicio ?? 'legado'}>
                          <td>
                            <span className="tray-rango">
                              {desd && hast ? (<>
                                {fmtFecha(desd)}
                                <span className="tray-rango-arrow">→</span>
                                {fmtFecha(hast)}
                              </>) : '—'}
                            </span>
                          </td>
                          <td>
                            <span className="tray-tra-cadena">
                              {tr.etapas.map((e, i) => (
                                <span key={e.id} className="tray-tra-eslabon">
                                  <span className="tray-tra-flecha" aria-hidden="true">{i > 0 ? '→' : ''}</span>
                                  <b>{e.parcela}</b>
                                </span>
                              ))}
                            </span>
                          </td>
                          <td><span className="comp-legend-chip" style={{ color: '#9ca3af' }}>finalizada</span></td>
                          <td className="num">{planDias ? `${fmt1(planDias)}d` : '—'}</td>
                          <td className="num">—</td>
                          <td />
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
        </div>
      );
      })()}
      </>
                    )}
                  </>
                )}
              </>
            )}

            {tab === 'trayectorias' && (
              <>
                {!rotFinca ? (
                  <p className="muted">
                    Elegí una estancia para ver las trayectorias. {rotFincas.length === 0 && 'Todavía no hay potreros cargados.'}
                  </p>
                ) : estadoActual.length === 0 ? (
                  <p className="muted">Hoy no hay rodeos pastoreando en esta estancia. Asignalos desde Rotación.</p>
                ) : (
                  <>
                    <div className="map-wrap" style={{ position: 'relative' }}>
                      <ErrorBoundary key={rotFinca}>
                        <Suspense fallback={<div className="card muted">Cargando mapa…</div>}>
                          <MapaRotacion
                            potreros={rotPotreros}
                            parcelas={rotParcelas}
                            parcelaSeleccionada={parcelaSel}
                            onSeleccionarParcela={(id) => setParcelaSel(id)}
                            secuencias={secuencias}
                          />
                        </Suspense>
                      </ErrorBoundary>
                      {parcelaSel != null && (
                        <div className="map-overlay" style={{ top: '8px', right: '8px', left: 'auto', pointerEvents: 'none' }}>
                          {(() => {
                            const parc = rotParcelas.find((p) => p.properties.id === parcelaSel);
                            const asig = estadoActual.find((a) => a.parcela_id === parcelaSel);
                            const nombre = parc ? parc.properties.nombre : `#${parcelaSel}`;
                            return asig
                              ? `Parcela ${nombre} · ${asig.rodeo} · desde ${fmtFecha(asig.fecha_entrada)}`
                              : `Parcela ${nombre} · libre hoy`;
                          })()}
                        </div>
                      )}
                    </div>

                    <div className="zonas-legend" aria-label="Colores del mapa">
                      {LEYENDA_COLORES_MAPA.map((e) => (
                        <span key={e.id} className="zona-item" title={`Parcelas en estado ${e.label}`}>
                          <span className="swatch" style={{ background: e.color }} />
                          {e.label}
                        </span>
                      ))}
                    </div>
                  </>
                )}
              </>
            )}
          </div>
        </main>
      </div>
      {confirm != null && (
        <div className="conf-overlay" role="dialog" aria-modal="true" aria-label="Confirmación">
          <div className="conf-caja">
            <p className="conf-mensaje">{confirm.mensaje}</p>
            <div className="conf-acciones">
              <button type="button" className="ghost-btn conf-btn" onClick={() => (confirm.onNo ? confirm.onNo() : setConfirm(null))}>No</button>
              <button type="button" className="conf-btn conf-si" onClick={() => confirm.onOk()}>Sí</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}