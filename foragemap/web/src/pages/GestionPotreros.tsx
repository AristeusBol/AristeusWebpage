import { Suspense, lazy, useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, type ParcelaDetalle, type PotreroProps } from '../lib/api';
import { useAuth } from '../lib/auth';
import Sidebar from '../components/Sidebar';
import Topbar from '../components/Topbar';
import ErrorBoundary from '../components/ErrorBoundary';
import type { PotreroFeature } from '../components/MapaMasaSeca';
import type { ExclusionFeature, ParcelaFeature, SeleccionGestion } from '../components/GestionMapa';

const GestionMapa = lazy(() => import('../components/GestionMapa'));

function etiqueta(nombre: string) {
  return nombre;
}

/** Área aproximada (ha) equirectangular para preview en vivo. El servidor es la fuente real. */
function areaHaPreview(ring: [number, number][]): number {
  if (ring.length < 3) return 0;
  const lat0 = ring.reduce((a, p) => a + p[1], 0) / ring.length;
  const kx = 111320 * Math.cos((lat0 * Math.PI) / 180);
  const ky = 110540;
  const pts = ring.map(([lng, lat]) => [lng * kx, lat * ky]);
  let s = 0;
  for (let i = 0; i < pts.length; i++) {
    const [x1, y1] = pts[i];
    const [x2, y2] = pts[(i + 1) % pts.length];
    s += x1 * y2 - x2 * y1;
  }
  return Math.abs(s) / 2 / 10000;
}

function puntoEnPoligono(pt: [number, number], poly: unknown): boolean {
  try {
    const g = poly as { type: string; coordinates: unknown };
    const rings = g.type === 'Polygon' ? [g.coordinates as number[][][]] : (g.coordinates as number[][][][]);
    const [x, y] = pt;
    for (const polyRings of rings) {
      const ring = polyRings[0] as [number, number][];
      let dentro = false;
      for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
        const [xi, yi] = ring[i];
        const [xj, yj] = ring[j];
        if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) dentro = !dentro;
      }
      if (dentro) return true;
    }
    return false;
  } catch {
    return true; // ante la duda, dejar que valide el servidor
  }
}

const fmt1 = (v: number | null | undefined) =>
  v === null || v === undefined ? 's/d' : v.toLocaleString('es-AR', { maximumFractionDigits: 1 });
const fmtKg = (v: number | null | undefined) =>
  v === null || v === undefined ? 's/d' : `${v.toLocaleString('es-AR', { maximumFractionDigits: 0 })} kg`;

export default function GestionPotreros() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [fincas, setFincas] = useState<string[]>([]);
  const [fechas, setFechas] = useState<string[]>([]);
  const [finca, setFinca] = useState('');
  const [fecha, setFecha] = useState('');
  const [mostrarDensidad, setMostrarDensidad] = useState(false); // default OFF
  const [potreros, setPotreros] = useState<PotreroFeature[]>([]);
  const [parcelas, setParcelas] = useState<ParcelaFeature[]>([]);
  const [exclusiones, setExclusiones] = useState<ExclusionFeature[]>([]);
  const [sel, setSel] = useState<SeleccionGestion | null>(null);
  const [focusSignal, setFocusSignal] = useState(0);
  const [detalle, setDetalle] = useState<ParcelaDetalle | null>(null);
  const [detallePotrero, setDetallePotrero] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastSync, setLastSync] = useState<number | null>(null);
  const [colapsado, setColapsado] = useState(false);
  const [busqueda, setBusqueda] = useState('');

  // Dibujo (solo parcelas: los potreros ya existen y son de solo lectura)
  const [modo, setModo] = useState<null | 'parcela'>(null);
  const [vertices, setVertices] = useState<[number, number][]>([]);
  const [cerrado, setCerrado] = useState(false);
  const [nombreForm, setNombreForm] = useState('');
  const [estadoForm, setEstadoForm] = useState('activa');
  const [guardando, setGuardando] = useState(false);
  const [editando, setEditando] = useState(false);

  const fincaEfectiva = useMemo(() => finca.trim(), [finca]);

  const recargar = useCallback(async (f: string, fe: string | null) => {
    if (!f) return;
    setLoading(true);
    setError(null);
    try {
      // Exclusiones no-fatal: si el endpoint no existe (backend viejo) el mapa igual muestra todo lo demás.
      const [p, q, x] = await Promise.all([
        api.potreros(f, fe || undefined),
        api.parcelasFinca(f, fe || undefined),
        api.exclusiones(f).catch(() => ({ type: 'FeatureCollection', features: [], metadata: { finca: f, count: 0 } })),
      ]);
      setPotreros(
        p.features.map((x) => ({
          type: 'Feature' as const,
          geometry: x.geometry as PotreroFeature['geometry'],
          properties: { ...(x.properties as PotreroProps), etiqueta: etiqueta((x.properties as PotreroProps).nombre) },
        })),
      );
      setParcelas(
        q.features.map((x) => ({
          type: 'Feature' as const,
          geometry: x.geometry as ParcelaFeature['geometry'],
          properties: {
            ...(x.properties as unknown as ParcelaFeature['properties']),
            etiqueta: etiqueta((x.properties as { nombre: string }).nombre),
          },
        })),
      );
      setExclusiones(
        x.features.map((e) => ({
          type: 'Feature' as const,
          geometry: e.geometry as ExclusionFeature['geometry'],
          properties: {
            ...(e.properties as unknown as ExclusionFeature['properties']),
            etiqueta: etiqueta((e.properties as { nombre: string }).nombre),
          },
        })),
      );
      setLastSync(Date.now());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error cargando gestión');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Fincas = las que ya tienen potreros (no dependen de cálculos).
    // Fechas = para el prorrateo forrajero (opcional, de calculos_stock).
    Promise.all([
      api.fincasConPotreros().catch(() => ({ fincas: [] as string[] })),
      api.filtros().catch(() => ({ fincas: [] as string[], fechas: [] as string[] })),
    ])
      .then(([pf, fl]) => {
        const flFull = fl as { fincas: string[]; fechas: string[] };
        setFincas(pf.fincas.length > 0 ? pf.fincas : flFull.fincas);
        setFechas(flFull.fechas);
        const f = pf.fincas.length > 0 ? pf.fincas : flFull.fincas;
        if (f.length === 1) setFinca(f[0]);
        if (flFull.fechas.length === 1) setFecha(flFull.fechas[0]);
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Error cargando filtros'));
  }, []);

  useEffect(() => {
    if (fincaEfectiva) recargar(fincaEfectiva, fecha || null);
    else {
      setPotreros([]);
      setParcelas([]);
      setExclusiones([]);
    }
  }, [fincaEfectiva, fecha, recargar]);

  // Detalle al seleccionar (igual que mapa de color: clic muestra datos)
  useEffect(() => {
    if (!sel) {
      setDetalle(null);
      setDetallePotrero(null);
      return;
    }
    if (sel.tipo === 'parcela') {
      api.detalleParcela(sel.id, fecha || undefined)
        .then(setDetalle)
        .catch((e) => setError(e instanceof Error ? e.message : 'Error cargando parcela'));
    } else {
      api.detalleGestion(sel.id, fecha || undefined)
        .then((d) => {
          const pot = d.features.find((f) => (f.properties as { tipo?: string }).tipo === 'potrero_base');
          setDetallePotrero((pot?.properties as Record<string, unknown>) ?? null);
          setDetalle(null);
        })
        .catch((e) => setError(e instanceof Error ? e.message : 'Error cargando potrero'));
    }
  }, [sel, fecha]);

  const onMapClick = useCallback((lngLat: [number, number]) => {
    setVertices((v) => {
      if (v.length >= 200) return v;
      return [...v, lngLat];
    });
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setModo(null);
        setVertices([]);
        setCerrado(false);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const iniciarDibujoParcela = async () => {
    setError(null);
    if (!sel || sel.tipo !== 'potrero') {
      setError('Seleccioná primero un potrero (clic en el mapa o en la lista) para dibujar una parcela dentro.');
      return;
    }
    setModo('parcela');
    setVertices([]);
    setCerrado(false);
    setEditando(false);
    try {
      const s = await api.sugerirNombreParcela(sel.id);
      setNombreForm(s.nombre_sugerido);
    } catch {
      setNombreForm('');
    }
    setEstadoForm('activa');
  };

  const cerrarPoligono = () => {
    if (vertices.length < 3) {
      setError('Marcá al menos 3 puntos para cerrar el polígono.');
      return;
    }
    if (sel?.tipo === 'potrero') {
      const pot = potreros.find((p) => p.properties.id === sel.id);
      if (!pot) {
        setError('El potrero seleccionado ya no está cargado. Elegilo de nuevo.');
        return;
      }
      const fuera = vertices.filter((v) => !puntoEnPoligono(v, pot.geometry));
      if (fuera.length > 0) {
        setError(`Hay ${fuera.length} punto(s) fuera del potrero (borde blanco). Las parcelas se dibujan solo dentro del potrero.`);
        return;
      }
      const excDelPotrero = exclusiones.filter((e) => e.properties.potrero_id === sel.id);
      const enExclusion = vertices.filter((v) =>
        excDelPotrero.some((e) => puntoEnPoligono(v, e.geometry)),
      );
      if (enExclusion.length > 0) {
        setError(`Hay ${enExclusion.length} punto(s) dentro de una zona de exclusión (rojo). Dibujá solo en área útil.`);
        return;
      }
    }
    setCerrado(true);
  };

  const guardarDibujo = async () => {
    if (!cerrado || vertices.length < 3) return;
    const nombre = nombreForm.trim();
    if (!nombre) {
      setError('Poné un nombre antes de guardar.');
      return;
    }
    const ring = [...vertices, vertices[0]];
    const geom = { type: 'Polygon', coordinates: [ring] };
    if (!sel || sel.tipo !== 'potrero') {
      setError('Seleccioná primero el potrero padre.');
      return;
    }
    setGuardando(true);
    setError(null);
    try {
      const r = await api.crearParcela(sel.id, nombre, geom, estadoForm);
      setModo(null);
      setVertices([]);
      setCerrado(false);
      setNombreForm('');
      await recargar(fincaEfectiva, fecha || null);
      setSel({ tipo: 'parcela', id: r.id });
      setFocusSignal((n) => n + 1);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error guardando');
    } finally {
      setGuardando(false);
    }
  };

  const eliminarParcelaSel = async () => {
    if (!sel || sel.tipo !== 'parcela') return;
    const nombre = parcelas.find((p) => p.properties.id === sel.id)?.properties.nombre;
    if (!window.confirm(`¿Eliminar parcela "${nombre}"? Esta acción no se puede deshacer.`)) return;
    setLoading(true);
    try {
      await api.eliminarParcela(sel.id);
      setSel(null);
      await recargar(fincaEfectiva, fecha || null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error eliminando');
    } finally {
      setLoading(false);
    }
  };

  const renombrarParcelaSel = async () => {
    if (!sel || sel.tipo !== 'parcela' || !editando) return;
    const nombre = nombreForm.trim();
    if (!nombre) {
      setError('El nombre no puede estar vacío.');
      return;
    }
    try {
      await api.actualizarParcela(sel.id, { nombre });
      setEditando(false);
      await recargar(fincaEfectiva, fecha || null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error renombrando');
    }
  };

  const exportar = useCallback(() => {
    const fc = {
      type: 'FeatureCollection',
      features: [...potreros, ...parcelas, ...exclusiones],
    };
    const blob = new Blob([JSON.stringify(fc)], { type: 'application/geo+json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `gestion_${fincaEfectiva.replace(/\s+/g, '_') || 'finca'}.geojson`;
    a.click();
    URL.revokeObjectURL(url);
  }, [potreros, parcelas, exclusiones, fincaEfectiva]);

  const buscar = useCallback(() => {
    const q = busqueda.trim().toLowerCase();
    if (!q) return;
    const hitP = parcelas.find((p) => String(p.properties.nombre).toLowerCase().includes(q));
    if (hitP) {
      setSel({ tipo: 'parcela', id: hitP.properties.id });
      setFocusSignal((n) => n + 1);
      return;
    }
    const hit = potreros.find((p) => p.properties.nombre.toLowerCase().includes(q));
    if (hit) {
      setSel({ tipo: 'potrero', id: hit.properties.id });
      setFocusSignal((n) => n + 1);
    }
  }, [busqueda, parcelas, potreros]);

  const areaPreview = useMemo(() => areaHaPreview(vertices), [vertices]);
  const selParcelaProps = sel?.tipo === 'parcela'
    ? parcelas.find((p) => p.properties.id === sel.id)?.properties ?? null
    : null;
  const selPotreroProps = sel?.tipo === 'potrero'
    ? potreros.find((p) => p.properties.id === sel.id)?.properties ?? null
    : null;
  const parcelasDelPotrero = useMemo(() => {
    if (sel?.tipo !== 'potrero') return [];
    return parcelas.filter((p) => p.properties.potrero_id === sel.id);
  }, [parcelas, sel]);

  return (
    <div className="app-shell">
      <Sidebar
        colapsado={colapsado}
        onColapsar={() => setColapsado((c) => !c)}
        vista="rodeos"
        onVista={(v) => {
          if (v === 'mapa') navigate('/mapa');
          else if (v === 'calibracion' || v === 'series' || v === 'histograma') navigate(`/mapa?vista=${v}`);
        }}
        onExportar={exportar}
        exportando={false}
        ultimaSync={lastSync}
        sincronizando={loading}
      />

      <div className="main-col">
        <Topbar
          busqueda={busqueda}
          onBusqueda={setBusqueda}
          onBuscar={buscar}
          fincas={fincas}
          finca={finca}
          onFinca={(v) => setFinca(v)}
          cargando={loading}
          nombre={user?.nombre ?? ''}
          email={user?.email ?? ''}
          onSalir={logout}
          notifCount={potreros.length + parcelas.length + exclusiones.length}
        />

        <main className="content map-layout">
          {error && <p className="error-text">{error}</p>}

          <div className="card">
            <div className="serie-head">
              <h3>Gestión de Rodeos · potreros y parcelas (solo masa total)</h3>
              <div className="serie-controls">
                <label>
                  Fecha
                  <select value={fecha} onChange={(e) => setFecha(e.target.value)} aria-label="Fecha para prorrateo">
                    <option value="">— Sin fecha (solo áreas) —</option>
                    {fechas.map((f) => <option key={f} value={f}>{f}</option>)}
                  </select>
                </label>
                <label title="Muestra la capa forrajera total (MVT) debajo de los bordes">
                  <input type="checkbox" checked={mostrarDensidad} onChange={(e) => setMostrarDensidad(e.target.checked)} />
                  Ver forraje
                </label>
              </div>
            </div>
            <p className="muted small" style={{ margin: '4px 0 0' }}>
              Los potreros ya existen (borde blanco) y no se dibujan. Seleccioná uno y dibujá parcelas dentro (amarillo), fuera de exclusiones (rojo).
            </p>
            <div className="calib-actions" style={{ marginTop: 8 }}>
              {!modo ? (
                <button
                  type="button"
                  className="ghost-btn"
                  onClick={iniciarDibujoParcela}
                  title={sel?.tipo === 'potrero' ? 'Dibujar parcela dentro del potrero seleccionado' : 'Seleccioná primero un potrero'}
                >
                  + Parcela en potrero{sel?.tipo === 'potrero' ? ` “${selPotreroProps?.nombre}”` : ''}
                </button>
              ) : (
                <>
                  <button type="button" className="ghost-btn" onClick={() => setVertices((v) => v.slice(0, -1))} disabled={vertices.length === 0 || cerrado}>
                    Deshacer punto
                  </button>
                  {!cerrado ? (
                    <>
                      <button type="button" className="ghost-btn" onClick={cerrarPoligono} disabled={vertices.length < 3}>
                        Cerrar parcela ({vertices.length} pts{areaPreview > 0 ? ` · ~${areaPreview.toFixed(1)} ha` : ''})
                      </button>
                      <button type="button" className="ghost-btn" onClick={() => { setModo(null); setVertices([]); }}>
                        Cancelar (Esc)
                      </button>
                    </>
                  ) : (
                    <>
                      <label style={{ display: 'flex', gap: 6, alignItems: 'center', fontSize: '.85rem' }}>
                        Nombre parcela
                        <input
                          value={nombreForm}
                          onChange={(e) => setNombreForm(e.target.value)}
                          placeholder="Ej. P5-A"
                          style={{ padding: 6, borderRadius: 6, border: '1px solid #cbd5c0', minWidth: 160 }}
                        />
                      </label>
                      <label style={{ display: 'flex', gap: 6, alignItems: 'center', fontSize: '.85rem' }}>
                        Estado
                        <select value={estadoForm} onChange={(e) => setEstadoForm(e.target.value)}>
                          <option value="activa">activa</option>
                          <option value="descanso">descanso</option>
                          <option value="excluida">excluida</option>
                        </select>
                      </label>
                      <span className="muted small">~{areaPreview.toFixed(2)} ha (preview; el servidor calcula el área real)</span>
                      <button type="button" className="ghost-btn" onClick={guardarDibujo} disabled={guardando}>
                        {guardando ? 'Guardando…' : 'Guardar parcela'}
                      </button>
                      <button type="button" className="ghost-btn" onClick={() => setCerrado(false)}>
                        Seguir dibujando
                      </button>
                    </>
                  )}
                </>
              )}
            </div>
            {!fincaEfectiva && <p className="muted" style={{ marginTop: 8 }}>Elegí una finca arriba para ver sus potreros. Las fincas listadas son las que ya tienen potreros cargados.</p>}
            {fincaEfectiva && potreros.length === 0 && !loading && (
              <p className="muted" style={{ marginTop: 8 }}>Esta finca no tiene potreros cargados. Los potreros se cargan por CSV; acá solo se dibujan parcelas dentro de potreros existentes.</p>
            )}
          </div>

          <div className="map-wrap">
            <ErrorBoundary key={fincaEfectiva}>
              <Suspense fallback={<div className="card muted">Cargando mapa…</div>}>
                <GestionMapa
                  potreros={potreros}
                  parcelas={parcelas}
                  exclusiones={exclusiones}
                  seleccion={sel}
                  onSelect={(s) => { setSel(s); setEditando(false); }}
                  finca={fincaEfectiva}
                  fecha={fecha}
                  mostrarDensidad={mostrarDensidad}
                  uid={user?.id ?? 0}
                  dibujando={modo !== null && !cerrado}
                  vertices={vertices}
                  onMapClick={onMapClick}
                  focusSignal={focusSignal}
                />
              </Suspense>
            </ErrorBoundary>
          </div>

          {/* Panel de datos al hacer clic — igual que mapa de color, panel completo */}
          <div className="panel comp-strip">
            <strong className="comp-strip-title">
              {sel?.tipo === 'parcela'
                ? `Parcela · ${selParcelaProps?.nombre ?? detalle?.nombre ?? ''}`
                : sel?.tipo === 'potrero'
                  ? `Potrero · ${selPotreroProps?.nombre ?? ''}`
                  : 'Seleccioná un potrero o parcela en el mapa'}
            </strong>
            {sel?.tipo === 'parcela' && (selParcelaProps || detalle) && (
              <div className="comp-strip-vals">
                <span><em>Área</em> <strong>{fmt1((detalle?.area_ha ?? selParcelaProps?.area_ha) as number)} ha</strong></span>
                <span className="sep">·</span>
                <span><em>Verde</em> <strong>{fmt1((detalle?.t_ha_verde ?? selParcelaProps?.t_ha_verde) as number)} t/ha</strong> <small>({fmtKg((detalle?.masa_verde_kg ?? selParcelaProps?.masa_verde_kg) as number)})</small></span>
                <span className="sep">·</span>
                <span><em>Muerta</em> <strong>{fmt1((detalle?.t_ha_muerta ?? selParcelaProps?.t_ha_muerta) as number)} t/ha</strong> <small>({fmtKg((detalle?.masa_muerta_kg ?? selParcelaProps?.masa_muerta_kg) as number)})</small></span>
                <span className="sep">·</span>
                <span><em>Total</em> <strong>{fmt1((detalle?.t_ha_total ?? selParcelaProps?.t_ha_total) as number)} t/ha</strong> <small>({fmtKg((detalle?.masa_total_kg ?? selParcelaProps?.masa_total_kg) as number)})</small></span>
                {((detalle?.estimado_por_prorrateo) || (selParcelaProps as unknown as { estimado_por_prorrateo?: boolean })?.estimado_por_prorrateo) && (
                  <small className="muted">* estimado por prorrateo del potrero</small>
                )}
                {!fecha && <small className="muted">Elegí fecha para ver forraje (prorrateo).</small>}
              </div>
            )}
            {sel?.tipo === 'potrero' && detallePotrero && (
              <div className="comp-strip-vals">
                <span><em>Área bruta</em> <strong>{fmt1(detallePotrero.area_bruta_ha as number)} ha</strong></span>
                <span className="sep">·</span>
                <span><em>Verde</em> <strong>{fmt1(detallePotrero.t_ha_verde as number)} t/ha</strong> <small>({fmtKg(detallePotrero.masa_verde_kg as number)})</small></span>
                <span className="sep">·</span>
                <span><em>Muerta</em> <strong>{fmt1(detallePotrero.t_ha_muerta as number)} t/ha</strong> <small>({fmtKg(detallePotrero.masa_muerta_kg as number)})</small></span>
                <span className="sep">·</span>
                <span><em>Total</em> <strong>{fmt1(detallePotrero.t_ha_total as number)} t/ha</strong> <small>({fmtKg(detallePotrero.masa_total_kg as number)})</small></span>
              </div>
            )}
            {sel?.tipo === 'parcela' && (
              <div className="calib-actions">
                {!editando ? (
                  <button type="button" className="ghost-btn" onClick={() => { setEditando(true); setNombreForm(String((selParcelaProps?.nombre ?? detalle?.nombre ?? '') as string)); }}>
                    Renombrar parcela
                  </button>
                ) : (
                  <>
                    <input value={nombreForm} onChange={(e) => setNombreForm(e.target.value)} style={{ padding: 6, borderRadius: 6, border: '1px solid #cbd5c0' }} />
                    <button type="button" className="ghost-btn" onClick={renombrarParcelaSel}>Guardar nombre</button>
                    <button type="button" className="ghost-btn" onClick={() => setEditando(false)}>Cancelar</button>
                  </>
                )}
                <button type="button" className="ghost-btn" onClick={eliminarParcelaSel}>Eliminar parcela</button>
              </div>
            )}
          </div>

          {/* Lista lateral: potreros + parcelas del seleccionado */}
          <div className="card">
            <h3>Potreros ({potreros.length}) · Parcelas ({parcelas.length}) · Exclusiones ({exclusiones.length})</h3>
            <p className="muted small" style={{ margin: '4px 0 0' }}>
              En el mapa: <strong style={{ color: '#fff', background: '#555', padding: '0 6px', borderRadius: 4 }}>blanco = potrero</strong>{' '}
              <strong style={{ color: '#422', background: '#fecaca', padding: '0 6px', borderRadius: 4 }}>rojo = exclusión (no dibujable)</strong>{' '}
              <strong style={{ color: '#422', background: '#facc15', padding: '0 6px', borderRadius: 4 }}>amarillo = parcela</strong>.
              Las parcelas se dibujan solo dentro del potrero y fuera de exclusiones.
            </p>
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
              <div style={{ flex: '1 1 280px' }}>
                <strong className="small muted">POTREROS</strong>
                {potreros.map((p) => (
                  <button
                    key={p.properties.id}
                    type="button"
                    className={`side-item ${sel?.tipo === 'potrero' && sel.id === p.properties.id ? 'activo' : ''}`}
                    style={{ width: '100%' }}
                    onClick={() => { setSel({ tipo: 'potrero', id: p.properties.id }); setFocusSignal((n) => n + 1); }}
                  >
                    <span className="side-dot" />
                    {p.properties.nombre} · {fmt1(p.properties.area_bruta_ha)} ha
                    {p.properties.t_ha_total != null ? ` · ${fmt1(p.properties.t_ha_total)} t/ha` : ''}
                  </button>
                ))}
                {potreros.length === 0 && <p className="muted small">Sin potreros en esta finca.</p>}
              </div>
              <div style={{ flex: '1 1 280px' }}>
                <strong className="small muted">
                  {sel?.tipo === 'potrero' ? `PARCELAS DE “${selPotreroProps?.nombre}” (${parcelasDelPotrero.length})` : 'PARCELAS (seleccioná un potrero)'}
                </strong>
                {parcelasDelPotrero.map((p) => (
                  <button
                    key={p.properties.id}
                    type="button"
                    className={`side-item ${sel?.tipo === 'parcela' && sel.id === p.properties.id ? 'activo' : ''}`}
                    style={{ width: '100%' }}
                    onClick={() => { setSel({ tipo: 'parcela', id: p.properties.id }); setFocusSignal((n) => n + 1); }}
                  >
                    <span className="side-dot" />
                    {p.properties.nombre} · {fmt1(p.properties.area_ha)} ha · {p.properties.estado}
                    {(p.properties as { t_ha_total?: number | null }).t_ha_total != null
                      ? ` · ${fmt1((p.properties as { t_ha_total?: number | null }).t_ha_total)} t/ha*` : ''}
                  </button>
                ))}
                {sel?.tipo === 'potrero' && parcelasDelPotrero.length === 0 && (
                  <p className="muted small">Sin parcelas. Usá “+ Parcela en potrero”.</p>
                )}
              </div>
            </div>
          </div>

          <footer className="foot">
            <span className="muted small">* masas de parcela estimadas por prorrateo del potrero (t/ha potrero × área parcela).</span>
            <span className="muted small">Fuente: ForageMap · <span className="ok-dot">●</span> Gestión predial</span>
          </footer>
        </main>
      </div>
    </div>
  );
}
