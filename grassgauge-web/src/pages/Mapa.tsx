import { Suspense, lazy, useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api, type ParcelaDetalle, type PotreroProps, type PotreroItem, type TipoDensidad } from '../lib/api';
import { useAuth } from '../lib/auth';
import { etiquetaPotrero } from '../lib/masaSeca';
import Sidebar from '../components/Sidebar';
import Topbar from '../components/Topbar';
import Leyenda from '../components/Leyenda';
import Composicion from '../components/Composicion';
import Histograma from '../components/Histograma';
import Calibracion from '../components/Calibracion';
import SerieTemporal from '../components/SerieTemporal';
import ErrorBoundary from '../components/ErrorBoundary';
import type { ParcelaMapFeature, PotreroFeature, ExclusionOverlayFeature } from '../components/MapaMasaSeca';

// Lazy: si maplibre-gl falla, solo cae el mapa, nunca la app.
const MapaMasaSeca = lazy(() => import('../components/MapaMasaSeca'));

/** Selección persistida para restaurar finca+fecha al recargar. */
const FILTROS_KEY = 'grassgauge_filtros';

function leerFiltrosGuardados(): { finca: string; fecha: string } | null {
  try {
    const raw = localStorage.getItem(FILTROS_KEY);
    if (!raw) return null;
    const o = JSON.parse(raw) as { finca?: unknown; fecha?: unknown };
    if (typeof o.finca !== 'string' || !o.finca) return null;
    return { finca: o.finca, fecha: typeof o.fecha === 'string' ? o.fecha : '' };
  } catch {
    return null;
  }
}

export default function Mapa() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [fincas, setFincas] = useState<string[]>([]);
  const [fechas, setFechas] = useState<string[]>([]);
  const [finca, setFinca] = useState('');
  const [fecha, setFecha] = useState('');
  const [lotes, setLotes] = useState<PotreroProps[]>([]);
  const [lotesLista, setLotesLista] = useState<PotreroItem[]>([]);
  const [features, setFeatures] = useState<PotreroFeature[]>([]);
  const [exclusiones, setExclusiones] = useState<ExclusionOverlayFeature[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [tipo, setTipo] = useState<TipoDensidad>('total');
  const [mostrarParcelas, setMostrarParcelas] = useState(false);
  const [parcelas, setParcelas] = useState<ParcelaMapFeature[]>([]);
  const [parcelaSelId, setParcelaSelId] = useState<number | null>(null);
  const [parcelaDet, setParcelaDet] = useState<ParcelaDetalle | null>(null);
  const [dibujando, setDibujando] = useState(false);
  const [vertices, setVertices] = useState<[number, number][]>([]);
  const [nombreSug, setNombreSug] = useState('');
  const [guardandoParc, setGuardandoParc] = useState(false);
  const [errorParc, setErrorParc] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [colapsado, setColapsado] = useState(false);
  const [searchParams, setSearchParams] = useSearchParams();
  const [vista, setVista] = useState(() => {
    const v = searchParams.get('vista');
    return v === 'series' || v === 'histograma' || v === 'calibracion' || v === 'ayuda' || v === 'exportar' ? v : 'mapa';
  });

  // Sincronizar la vista en la URL para no perderla al navegar (ej. desde Rodeos).
  useEffect(() => {
    setSearchParams(vista === 'mapa' ? {} : { vista }, { replace: true });
  }, [vista, setSearchParams]);

  // Mapa de masa seca e histograma siempre con fecha: si está vacía, elegir la
  // más reciente (el backend ordena fechas DESC, así que fechas[0] es la última).
  useEffect(() => {
    if ((vista !== 'mapa' && vista !== 'histograma') || !finca || !fechas.length) return;
    if (!fecha) setFecha(fechas[0]);
  }, [vista, finca, fecha, fechas]);

  // Persistir finca+fecha para restaurarlas al recargar.
  useEffect(() => {
    try {
      if (finca) localStorage.setItem(FILTROS_KEY, JSON.stringify({ finca, fecha }));
      else localStorage.removeItem(FILTROS_KEY);
    } catch {
      /* almacenamiento no disponible */
    }
  }, [finca, fecha]);

  // Fincas + fechas iniciales (restaura la selección guardada si sigue válida)
  useEffect(() => {
    setLoading(true);
    api.potrerosLista()
      .then((d) => setLotesLista(d.potreros))
      .catch(() => setLotesLista([]));
    api.filtros()
      .then(async (d) => {
        setFincas(d.fincas);
        setFechas(d.fechas);
        const saved = leerFiltrosGuardados();
        if (saved && d.fincas.includes(saved.finca)) {
          setFinca(saved.finca);
          try {
            const df = await api.filtros(saved.finca);
            setFechas(df.fechas);
            if (saved.fecha && df.fechas.includes(saved.fecha)) setFecha(saved.fecha);
            else if (df.fechas.length === 1) setFecha(df.fechas[0]);
          } catch {
            /* quedan las fechas globales */
          }
        } else {
          if (d.fincas.length === 1) setFinca(d.fincas[0]);
          if (d.fechas.length === 1) setFecha(d.fechas[0]);
        }
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Error cargando filtros'))
      .finally(() => setLoading(false));
  }, []);

  // Cascada finca -> fechas, y potreros al tener finca+fecha
  const cargarFiltros = useCallback(async (nuevaFinca: string) => {
    setFinca(nuevaFinca);
    setFecha('');
    setLotes([]);
    setFeatures([]);
    setSelectedId(null);
    if (!nuevaFinca) return;
    setLoading(true);
    try {
      const d = await api.filtros(nuevaFinca);
      setFechas(d.fechas);
      if (d.fechas.length === 1) setFecha(d.fechas[0]);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error cargando fechas');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!finca) {
      setExclusiones([]);
      return;
    }
    // No-fatal: si falla, el mapa igual muestra densidad recortada del backend.
    api.exclusiones(finca)
      .then((d) => setExclusiones(
        d.features.map((f) => ({
          type: 'Feature' as const,
          geometry: f.geometry as ExclusionOverlayFeature['geometry'],
          properties: {
            id: f.properties.id,
            nombre: f.properties.nombre,
            etiqueta: f.properties.nombre,
          },
        })),
      ))
      .catch(() => setExclusiones([]));
  }, [finca]);

  useEffect(() => {
    if (!finca || !fecha) return;
    setLoading(true);
    setError(null);
    api.potreros(finca, fecha)
      .then((d) => {
        const props = d.features.map((f) => f.properties);
        setLotes(props);
        setFeatures(
          d.features.map((f) => ({
            type: 'Feature' as const,
            geometry: f.geometry as PotreroFeature['geometry'],
            properties: { ...f.properties, etiqueta: etiquetaPotrero(f.properties) },
          })),
        );
        // Auto-seleccionar el lote con mayor t/ha (como A5 en la referencia).
        const conDato = props.filter((p) => p.t_ha_total !== null && p.t_ha_total !== undefined);
        const top = conDato.length
          ? conDato.reduce((a, b) => ((b.t_ha_total ?? -1) > (a.t_ha_total ?? -1) ? b : a))
          : null;
        setSelectedId(top ? top.id : null);
      })
      .catch((e) => {
        setLotes([]);
        setFeatures([]);
        setSelectedId(null);
        setError(e instanceof Error ? e.message : 'Error cargando potreros');
      })
      .finally(() => setLoading(false));
  }, [finca, fecha]);

  /** Primer hueco libre '<base>_1, _2...' entre los nombres en uso (formato nuevo). */
  const siguienteNombreLocal = useCallback((base: string, usados: Set<string>) => {
    const b = (base || 'Parcela').trim() || 'Parcela';
    let i = 1;
    while (usados.has(`${b}_${i}`)) i += 1;
    return `${b}_${i}`;
  }, []);

  // Parcelas hijas: una llamada por finca (con fecha para promedio zonal).
  const recargarParcelas = useCallback(async () => {
    if (!mostrarParcelas || !finca) { setParcelas([]); return; }
    try {
      const d = await api.parcelasFinca(finca, fecha || undefined);
      setParcelas(d.features.map((f) => ({
        type: 'Feature' as const,
        geometry: f.geometry as ParcelaMapFeature['geometry'],
        properties: {
          id: f.properties.id,
          nombre: f.properties.nombre,
          etiqueta: f.properties.nombre,
          potrero_id: f.properties.potrero_id,
          estado: f.properties.estado,
          area_ha: f.properties.area_ha,
          t_ha_total: f.properties.t_ha_total,
        },
      })));
    } catch {
      setParcelas([]);
    }
  }, [mostrarParcelas, finca, fecha]);

  useEffect(() => { void recargarParcelas(); }, [recargarParcelas]);

  // Limpiar selección de parcela al cambiar de finca/fecha o apagar el toggle.
  useEffect(() => { setParcelaSelId(null); setParcelaDet(null); }, [finca, fecha, mostrarParcelas]);

  // Detalle zonal de la parcela clickeada (promedio real de su zona).
  // Además selecciona el potrero padre: parcela y potrero siempre van juntos.
  useEffect(() => {
    if (parcelaSelId == null) { setParcelaDet(null); return; }
    let vivo = true;
    api.detalleParcela(parcelaSelId, fecha || undefined)
      .then((d) => {
        if (!vivo) return;
        setParcelaDet(d);
        if (typeof d.potrero_id === 'number') setSelectedId(d.potrero_id);
      })
      .catch(() => { if (vivo) setParcelaDet(null); });
    return () => { vivo = false; };
  }, [parcelaSelId, fecha]);

  // Esc cancela el dibujo en curso.
  useEffect(() => {
    if (!dibujando) return;
    const fn = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { setDibujando(false); setVertices([]); setErrorParc(null); }
    };
    window.addEventListener('keydown', fn);
    return () => window.removeEventListener('keydown', fn);
  }, [dibujando]);

  const iniciarDibujo = useCallback(async () => {
    setErrorParc(null);
    if (!finca) { setErrorParc('Elegí una estancia primero.'); return; }
    if (selectedId == null) { setErrorParc('Elegí un potrero padre primero (clic en el mapa).'); return; }
    setParcelaSelId(null);
    setDibujando(true);
    setVertices([]);
    const base = lotes.find((l) => l.id === selectedId)?.nombre ?? 'Parcela';
    const usados = new Set(
      parcelas.filter((p) => (p.properties.potrero_id as number) === selectedId).map((p) => p.properties.nombre),
    );
    // Nombre local inmediato (no depende del backend); se confirma contra el
    // servidor abajo y se recalcula al guardar.
    setNombreSug(siguienteNombreLocal(base, usados));
    try {
      const s = await api.sugerirNombreParcela(selectedId);
      if (/_\d+$/.test(s.nombre_sugerido)) setNombreSug(s.nombre_sugerido);
    } catch {
      /* queda la sugerencia local */
    }
  }, [finca, selectedId, lotes, parcelas, siguienteNombreLocal]);

  const cerrarYGuardar = useCallback(async () => {
    setErrorParc(null);
    if (selectedId == null) {
      setErrorParc('Elegí un potrero padre primero (clic en el mapa).');
      return;
    }
    // Colapsar vértices consecutivos casi idénticos (el doble-clic mete 2 clics
    // en el mismo punto pegado y si no se colapsan el polígono queda inválido).
    const limpios = vertices.filter((v, i) => {
      if (i === 0) return true;
      const a = vertices[i - 1];
      return Math.hypot(v[0] - a[0], v[1] - a[1]) > 1e-7;
    });
    if (limpios.length >= 2) {
      const a = limpios[0];
      const b = limpios[limpios.length - 1];
      if (Math.hypot(a[0] - b[0], a[1] - b[1]) <= 1e-7) limpios.pop();
    }
    if (limpios.length < 3) { setErrorParc('Marcá al menos 3 vértices para cerrar la parcela.'); return; }
    const ring = [...limpios, limpios[0]];
    const base = lotes.find((l) => l.id === selectedId)?.nombre ?? 'Parcela';
    const usados = new Set(
      parcelas.filter((p) => (p.properties.potrero_id as number) === selectedId).map((p) => p.properties.nombre),
    );
    const nombre = siguienteNombreLocal(base, usados);
    setGuardandoParc(true);
    try {
      const r = await api.crearParcela(selectedId, { type: 'Polygon', coordinates: [ring] }, 'optimo', nombre);
      setDibujando(false);
      setVertices([]);
      await recargarParcelas();
      setParcelaSelId(r.id);
    } catch (e) {
      setErrorParc(e instanceof Error ? e.message : 'No se pudo guardar la parcela');
    } finally {
      setGuardandoParc(false);
    }
  }, [selectedId, vertices, recargarParcelas, siguienteNombreLocal, lotes, parcelas]);

  const cambiarEstadoParcela = useCallback(async (estado: string) => {
    if (parcelaSelId == null) return;
    setErrorParc(null);
    try {
      await api.actualizarParcela(parcelaSelId, { estado });
      await recargarParcelas();
      const d = await api.detalleParcela(parcelaSelId, fecha || undefined);
      setParcelaDet(d);
    } catch (e) {
      setErrorParc(e instanceof Error ? e.message : 'No se pudo actualizar');
    }
  }, [parcelaSelId, fecha, recargarParcelas]);

  const eliminarParcela = useCallback(async () => {
    if (parcelaSelId == null) return;
    if (!window.confirm('¿Eliminar esta parcela?')) return;
    setErrorParc(null);
    try {
      await api.eliminarParcela(parcelaSelId);
      setParcelaSelId(null);
      setParcelaDet(null);
      await recargarParcelas();
    } catch (e) {
      setErrorParc(e instanceof Error ? e.message : 'No se pudo eliminar');
    }
  }, [parcelaSelId, recargarParcelas]);

  const loteSeleccionado = useMemo(
    () => lotes.find((l) => l.id === selectedId) ?? null,
    [lotes, selectedId],
  );

  return (
    <div className="app-shell">
      <Sidebar
        colapsado={colapsado}
        onColapsar={() => setColapsado((c) => !c)}
        vista={vista}
        onVista={(v) => {
          if (v === 'rodeos' || v === 'lotes') navigate('/rodeos');
          else if (v === 'rotacion') navigate('/rodeos/rotacion');
          else if (v === 'trayectorias') navigate('/rodeos/trayectorias');
          else setVista(v);
        }}
      />

      <div className="main-col">
        <Topbar
          fincas={fincas}
          finca={finca}
          onFinca={(v) => cargarFiltros(v)}
          cargando={loading}
          nombre={user?.nombre ?? ''}
          email={user?.email ?? ''}
          onSalir={logout}
          notifCount={lotes.length}
        />

        {vista === 'series' ? (
          <main className="content">
            <SerieTemporal
              finca={finca}
              lotes={lotesLista.filter((l) => !finca || l.finca === finca)}
              loteIdExterno={selectedId}
              parcelaIdExterna={parcelaSelId}
            />
            {!finca && <p className="muted">Elegí una estancia en el mapa para ver su serie (o volvé al <button type="button" className="link-btn" onClick={() => setVista('mapa')}>mapa</button>).</p>}
          </main>
        ) : vista === 'histograma' ? (
          <main className="content">
            <Histograma finca={finca} fecha={fecha} fechas={fechas} onFecha={setFecha} lotes={lotesLista.filter((l) => !finca || l.finca === finca)} loteIdExterno={selectedId} parcelaIdExterna={parcelaSelId} />
            {!finca && <p className="muted">Elegí una estancia en el mapa para ver su histograma (o volvé al <button type="button" className="link-btn" onClick={() => setVista('mapa')}>mapa</button>).</p>}
          </main>
        ) : vista === 'calibracion' ? (
          <main className="content">
            <Calibracion />
          </main>
        ) : vista === 'ayuda' ? (
          <main className="content">
            <div className="card" style={{ textAlign: 'center', padding: '48px 24px' }}>
              <div style={{ fontSize: '2.5rem' }} aria-hidden>🚧</div>
              <h3>Ayuda y Soporte</h3>
              <p className="muted">Zona en construcción. Estamos preparando guías y contacto.</p>
              <button type="button" onClick={() => setVista('mapa')}>Volver al mapa</button>
            </div>
          </main>
        ) : vista === 'exportar' ? (
          <main className="content">
            <div className="card" style={{ textAlign: 'center', padding: '48px 24px' }}>
              <div style={{ fontSize: '2.5rem' }} aria-hidden>🚧</div>
              <h3>Exportar Datos</h3>
              <p className="muted">Zona en construcción. Estamos preparando las descargas.</p>
              <button type="button" onClick={() => setVista('mapa')}>Volver al mapa</button>
            </div>
          </main>
        ) : vista !== 'mapa' ? (
          <main className="content">
            <div className="card">
              <h3>Próximamente</h3>
              <p className="muted">Este módulo aún no está implementado. El Mapa de Masa Seca ya es funcional.</p>
              <button type="button" onClick={() => setVista('mapa')}>Volver al mapa</button>
            </div>
          </main>
        ) : (
          <main className="content map-layout">
            {loading && <span className="muted">Cargando…</span>}
            {error && <p className="error-text">{error}</p>}
            {fincas.length === 0 && !loading && (
              <p className="muted">
                Sin estancias: todavía no hay potreros cargados. Subí potreros y mapa
                desde el loader (el stock se calcula solo al subir el mapa).
              </p>
            )}

            <section className="panel mapa-panel">
            <div className="map-wrap">
              <label className="map-fecha-float">
                Fecha
                <select value={fecha} onChange={(e) => setFecha(e.target.value)} disabled={fechas.length === 0} aria-label="Fecha">
                  <option value="">— Elegir —</option>
                  {fechas.map((f) => (
                    <option key={f} value={f}>{f}</option>
                  ))}
                </select>
              </label>
              <div className="map-submenu" role="group" aria-label="Tipo de densidad">
                {(['verde', 'muerta', 'total'] as TipoDensidad[]).map((t) => (
                  <button
                    key={t}
                    type="button"
                    className={tipo === t ? 'active' : ''}
                    onClick={() => setTipo(t)}
                  >
                    {t[0].toUpperCase() + t.slice(1)}
                  </button>
                ))}
              </div>
              <div className="map-submenu-parcelas" role="group" aria-label="Parcelas">
                <button
                  type="button"
                  className={mostrarParcelas ? 'active' : ''}
                  onClick={() => setMostrarParcelas((v) => !v)}
                  title="Mostrar / ocultar parcelas hijas"
                >
                  Parcelas
                </button>
                {mostrarParcelas && !dibujando && parcelaDet && (
                  <label
                    className="parc-estado"
                    title={`Clic para cambiar el estado de ${parcelaDet.nombre}`}
                  >
                    <select
                      value={parcelaDet.estado}
                      onChange={(e) => void cambiarEstadoParcela(e.target.value)}
                      aria-label={`Estado de ${parcelaDet.nombre} (clic para cambiar)`}
                    >
                      <option value="critico">critico</option>
                      <option value="desarrollo">desarrollo</option>
                      <option value="optimo">optimo</option>
                      <option value="maduro">maduro</option>
                      <option value="pasado">pasado</option>
                    </select>
                    <svg className="parc-estado-caret" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <polyline points="6 9 12 15 18 9" />
                    </svg>
                  </label>
                )}
                <button
                  type="button"
                  className={dibujando ? 'active' : ''}
                  onClick={() => { if (dibujando) { setDibujando(false); setVertices([]); } else void iniciarDibujo(); }}
                  title={selectedId == null ? 'Elegí un potrero padre primero' : 'Nueva parcela dentro del potrero elegido'}
                  aria-label="Nueva parcela"
                  style={{ padding: '3px 7px', display: 'inline-flex', alignItems: 'center' }}
                >
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true">
                    <line x1="12" y1="5" x2="12" y2="19" />
                    <line x1="5" y1="12" x2="19" y2="12" />
                  </svg>
                </button>
                {mostrarParcelas && !dibujando && parcelaDet && (
                  <>
                    <button
                      type="button"
                      className="parc-del"
                      onClick={() => void eliminarParcela()}
                      title={`Eliminar ${parcelaDet.nombre}`}
                      aria-label={`Eliminar ${parcelaDet.nombre}`}
                    >
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                        <path d="M3 6h18" />
                        <path d="M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2" />
                        <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
                        <line x1="10" y1="11" x2="10" y2="17" />
                        <line x1="14" y1="11" x2="14" y2="17" />
                      </svg>
                    </button>
                  </>
                )}
              </div>
              {dibujando && (
                <>
                <div className="map-dibujo-hint" aria-live="polite">
                  {guardandoParc ? 'Guardando parcela…' : `Clic: vértice (${vertices.length}) · se pega a bordes y esquinas · doble-clic o ✓: cerrar · Esc: cancelar`}
                </div>
                <div className="map-dibujo-bar" role="group" aria-label="Dibujo de parcela">
                  <span className="dibujo-nombre" title={nombreSug ? `Potrero padre: ${loteSeleccionado?.nombre ?? '—'} · se guardará como ${nombreSug}` : 'Dibujando parcela'}>
                    {loteSeleccionado?.nombre ? `en ${loteSeleccionado.nombre} · ` : ''}{nombreSug || '…'}
                  </span>
                  <button type="button" onClick={() => setVertices((v) => v.slice(0, -1))} disabled={vertices.length === 0} title="Deshacer último vértice" aria-label="Deshacer último vértice">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <path d="M9 14L4 9l5-5" />
                      <path d="M4 9h10a6 6 0 0 1 0 12h-3" />
                    </svg>
                  </button>
                  <button type="button" className="dibujo-cerrar" onClick={() => void cerrarYGuardar()} disabled={vertices.length < 3 || guardandoParc} title={vertices.length < 3 ? 'Marcá al menos 3 vértices' : 'Cerrar y guardar parcela'} aria-label="Cerrar y guardar parcela">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                    <span>({vertices.length})</span>
                  </button>
                  <button type="button" onClick={() => { setDibujando(false); setVertices([]); setErrorParc(null); }} title="Cancelar dibujo (Esc)" aria-label="Cancelar dibujo">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true">
                      <line x1="18" y1="6" x2="6" y2="18" />
                      <line x1="6" y1="6" x2="18" y2="18" />
                    </svg>
                  </button>
                </div>
                </>
              )}
              {dibujando && errorParc && <div className="map-overlay error">{errorParc}</div>}
              <ErrorBoundary key={`${finca}|${fecha}`}>
                <Suspense fallback={<div className="card muted">Cargando librería del mapa…</div>}>
                  <MapaMasaSeca
                    features={features}
                    selectedId={selectedId}
                    onSelect={(id) => {
                      setSelectedId(id);
                      // Si la parcela elegida no es de este potrero, se oculta su tira.
                      setParcelaSelId((prev) => {
                        if (prev == null) return prev;
                        const pid = parcelas.find((p) => p.properties.id === prev)?.properties.potrero_id;
                        return pid !== undefined && pid === id ? prev : null;
                      });
                    }}
                    finca={finca}
                    fecha={fecha}
                    tipo={tipo}
                    exclusiones={exclusiones}
                    uid={user?.id ?? 0}
                    parcelas={parcelas}
                    mostrarParcelas={mostrarParcelas}
                    parcelaSelectedId={parcelaSelId}
                    onSelectParcela={(id) => {
                      setParcelaSelId(id);
                      if (id != null) {
                        const padre = parcelas.find((p) => p.properties.id === id)?.properties.potrero_id;
                        if (typeof padre === 'number') setSelectedId(padre);
                      }
                    }}
                    dibujando={dibujando}
                    vertices={vertices}
                    onDibujoClick={(ll) => setVertices((v) => [...v, ll])}
                    onDibujoDobleClick={() => void cerrarYGuardar()}
                  />
                </Suspense>
              </ErrorBoundary>
              <Leyenda />
            </div>

            <Composicion lote={loteSeleccionado} lotes={lotes} />
            {mostrarParcelas && !dibujando && parcelaDet && (
              <>
                {errorParc && <p className="error-text">{errorParc}</p>}
                <div className="comp-strip">
                  <strong className="comp-strip-title">{parcelaDet.nombre} <span className="comp-arrow">→</span></strong>
                    {(() => {
                      const tot = parcelaDet.masa_total_kg ?? 0;
                      if (!parcelaDet.tiene_calculo || parcelaDet.t_ha_total == null || tot <= 0) {
                        return <span className="muted">Sin datos en esta zona/fecha.</span>;
                      }
                      const fmt1 = (v: number) => Number(v).toLocaleString('es-AR', { maximumFractionDigits: 1 });
                      const fmt0 = (v: number) => Number(v).toLocaleString('es-AR', { maximumFractionDigits: 0 });
                      const pctV = ((parcelaDet.masa_verde_kg ?? 0) / tot) * 100;
                      const pctM = ((parcelaDet.masa_muerta_kg ?? 0) / tot) * 100;
                      return (
                        <div className="comp-strip-vals">
                          <span><em>Área:</em> {parcelaDet.area_ha != null ? `${Number(parcelaDet.area_ha).toLocaleString('es-AR', { maximumFractionDigits: 2 })} ha` : '—'}</span>
                          <span className="sep">·</span>
                          <span><em>Verde:</em> <span style={{ color: 'var(--densidad-verde)' }}>{fmt1(parcelaDet.t_ha_verde ?? 0)} t/ha</span> <small>({fmt0(pctV)}%)</small></span>
                          <span className="sep">·</span>
                          <span><em>Muerta:</em> <span style={{ color: 'var(--densidad-muerta)' }}>{fmt1(parcelaDet.t_ha_muerta ?? 0)} t/ha</span> <small>({fmt0(pctM)}%)</small></span>
                          <span className="sep">·</span>
                          <span><em>Total:</em> <span style={{ color: 'var(--densidad-total)' }}>{fmt1(parcelaDet.t_ha_total)} t/ha</span></span>
                          <span className="sep">·</span>
                          <small className="muted">{parcelaDet.n_puntos != null ? `${parcelaDet.n_puntos} pts` : ''}</small>
                        </div>
                      );
                    })()}
                  </div>
              </>
            )}
            </section>
          </main>
        )}
      </div>
    </div>
  );
}
