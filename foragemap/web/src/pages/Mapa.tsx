import { Suspense, lazy, useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api, type PotreroProps, type TipoDensidad } from '../lib/api';
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
import type { PotreroFeature, ExclusionOverlayFeature } from '../components/MapaMasaSeca';

// Lazy: si maplibre-gl falla, solo cae el mapa, nunca la app.
const MapaMasaSeca = lazy(() => import('../components/MapaMasaSeca'));

export default function Mapa() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [fincas, setFincas] = useState<string[]>([]);
  const [fechas, setFechas] = useState<string[]>([]);
  const [finca, setFinca] = useState('');
  const [fecha, setFecha] = useState('');
  const [lotes, setLotes] = useState<PotreroProps[]>([]);
  const [features, setFeatures] = useState<PotreroFeature[]>([]);
  const [exclusiones, setExclusiones] = useState<ExclusionOverlayFeature[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [focusSignal, setFocusSignal] = useState(0);
  const [tipo, setTipo] = useState<TipoDensidad>('total');
  const [busqueda, setBusqueda] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastSync, setLastSync] = useState<number | null>(null);
  const [colapsado, setColapsado] = useState(false);
  const [searchParams, setSearchParams] = useSearchParams();
  const [vista, setVista] = useState(() => {
    const v = searchParams.get('vista');
    return v === 'series' || v === 'histograma' || v === 'calibracion' ? v : 'mapa';
  });
  const [exportando, setExportando] = useState(false);

  // Sincronizar la vista en la URL para no perderla al navegar (ej. desde Rodeos).
  useEffect(() => {
    setSearchParams(vista === 'mapa' ? {} : { vista }, { replace: true });
  }, [vista, setSearchParams]);

  // Fincas + fechas iniciales
  useEffect(() => {
    setLoading(true);
    api.filtros()
      .then((d) => {
        setFincas(d.fincas);
        setFechas(d.fechas);
        if (d.fincas.length === 1) setFinca(d.fincas[0]);
        if (d.fechas.length === 1) setFecha(d.fechas[0]);
        setLastSync(Date.now());
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
      setLastSync(Date.now());
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
        setLastSync(Date.now());
      })
      .catch((e) => {
        setLotes([]);
        setFeatures([]);
        setSelectedId(null);
        setError(e instanceof Error ? e.message : 'Error cargando potreros');
      })
      .finally(() => setLoading(false));
  }, [finca, fecha]);

  const loteSeleccionado = useMemo(
    () => lotes.find((l) => l.id === selectedId) ?? null,
    [lotes, selectedId],
  );

  const buscar = useCallback(() => {
    const q = busqueda.trim().toLowerCase();
    if (!q) return;
    const hit = lotes.find((l) => l.nombre.toLowerCase().includes(q));
    if (hit) {
      setSelectedId(hit.id);
      setFocusSignal((n) => n + 1);
    }
  }, [busqueda, lotes]);

  const exportar = useCallback(async () => {
    if (!finca || !fecha || features.length === 0) return;
    setExportando(true);
    try {
      const fc = { type: 'FeatureCollection', features };
      const blob = new Blob([JSON.stringify(fc)], { type: 'application/geo+json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `potreros_${finca.replace(/\s+/g, '_')}_${fecha}.geojson`;
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setExportando(false);
    }
  }, [finca, fecha, features]);

  return (
    <div className="app-shell">
      <Sidebar
        colapsado={colapsado}
        onColapsar={() => setColapsado((c) => !c)}
        vista={vista}
        onVista={(v) => {
          if (v === 'rodeos') navigate('/rodeos');
          else setVista(v);
        }}
        onExportar={exportar}
        exportando={exportando}
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
              lotes={lotes}
              onVerEnMapa={(f) => { setFecha(f); setVista('mapa'); }}
            />
            {!finca && <p className="muted">Elegí una finca en el mapa para ver su serie (o volvé al <button type="button" className="link-btn" onClick={() => setVista('mapa')}>mapa</button>).</p>}
          </main>
        ) : vista === 'histograma' ? (
          <main className="content">
            <Histograma finca={finca} fecha={fecha} fechas={fechas} onFecha={setFecha} />
            {!finca && <p className="muted">Elegí una finca en el mapa para ver su histograma (o volvé al <button type="button" className="link-btn" onClick={() => setVista('mapa')}>mapa</button>).</p>}
          </main>
        ) : vista === 'calibracion' ? (
          <main className="content">
            <Calibracion />
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
                Sin fincas: todavía no hay <code>calculos_stock</code>. Cargá CSVs y corré{' '}
                <code>calcular_kilos_reales.py --guardar</code>.
              </p>
            )}

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
              <ErrorBoundary key={`${finca}|${fecha}`}>
                <Suspense fallback={<div className="card muted">Cargando librería del mapa…</div>}>
                  <MapaMasaSeca
                    features={features}
                    selectedId={selectedId}
                    onSelect={(id) => setSelectedId(id)}
                    finca={finca}
                    fecha={fecha}
                    tipo={tipo}
                    onTipo={(t) => setTipo(t)}
                    exclusiones={exclusiones}
                    focusSignal={focusSignal}
                    uid={user?.id ?? 0}
                  />
                </Suspense>
              </ErrorBoundary>
              <Leyenda tipo={tipo} conDatos={features.length > 0 && !!finca && !!fecha} />
            </div>

            <Composicion lote={loteSeleccionado} lotes={lotes} />

            <footer className="foot">
              <span className="muted small">ⓘ Los datos se actualizan automáticamente con cada nuevo procesamiento.</span>
              <span className="muted small">
                Fuente: ForageMap · <span className="ok-dot">●</span> Datos actualizados
              </span>
            </footer>
          </main>
        )}
      </div>
    </div>
  );
}
