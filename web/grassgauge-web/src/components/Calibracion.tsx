import { useEffect, useMemo, useState } from 'react';
import { api, type FotoCalibracion, type PotreroDetalleResponse, type PotreroItem, type SubidaFotoResponse } from '../lib/api';
import { fmtFechaCorta } from '../lib/masaSeca';
import { validarPuntoCalibracion, type FeatureSimple } from '../lib/geo';
import MapaPunto from './MapaPunto';

type Paso = 1 | 2 | 3;

/** Calibración de IA: potrero → punto exacto en mapa → foto georreferenciada. */
export default function Calibracion() {
  const [paso, setPaso] = useState<Paso>(1);
  const [potreros, setPotreros] = useState<PotreroItem[]>([]);
  const [potreroId, setPotreroId] = useState<string>('');
  const [puntoError, setPuntoError] = useState<string | null>(null);
  const [detalle, setDetalle] = useState<PotreroDetalleResponse | null>(null);
  const [punto, setPunto] = useState<{ lat: number; lon: number } | null>(null);
  const [fechas, setFechas] = useState<string[]>([]);
  const [fecha, setFecha] = useState('');
  const [archivo, setArchivo] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [galeria, setGaleria] = useState<FotoCalibracion[]>([]);
  const [subidasSesion, setSubidasSesion] = useState(0);
  const [exito, setExito] = useState<SubidaFotoResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [subiendo, setSubiendo] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    api.potrerosLista()
      .then((d) => setPotreros(d.potreros))
      .catch((e) => setError(e instanceof Error ? e.message : 'Error cargando potreros'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    return () => { if (preview) URL.revokeObjectURL(preview); };
  }, [preview]);

  const potrero = useMemo(() => potreros.find((p) => String(p.id) === potreroId) ?? null, [potreros, potreroId]);
  const fincas = useMemo(() => [...new Set(potreros.map((p) => p.finca))].sort(), [potreros]);

  const elegirPotrero = async (idStr?: string) => {
    const sel = idStr ?? potreroId;
    const pot = potreros.find((p) => String(p.id) === sel);
    if (!sel || !pot) return;
    setPotreroId(sel);
    setLoading(true);
    setError(null);
    try {
      const [det, flt, gal] = await Promise.all([
        api.potreroDetalle(Number(sel)),
        api.filtros(pot.finca),
        api.fotosDePotrero(Number(sel)),
      ]);
      setDetalle(det);
      setFechas(flt.fechas);
      if (flt.fechas.length > 0) setFecha(flt.fechas[flt.fechas.length - 1]);
      setGaleria(gal.fotos);
      setPunto(null);
      setPuntoError(null);
      setExito(null);
      setPaso(2);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error cargando potrero');
    } finally {
      setLoading(false);
    }
  };

  const onArchivo = (f: File | null) => {
    if (preview) URL.revokeObjectURL(preview);
    if (f) {
      // Validación previa: evita subir 25MB por red lenta para que falle igual.
      const esImagen = f.type.startsWith('image/') || /\.(jpe?g|png|webp|heic|heif|tif|tiff)$/i.test(f.name);
      if (!esImagen) {
        setError('El archivo no es una imagen válida (JPG, PNG, WebP, HEIC o TIFF).');
        setArchivo(null);
        setPreview(null);
        return;
      }
      if (f.size > 25 * 1024 * 1024) {
        setError(`La foto pesa ${(f.size / 1048576).toFixed(1)}MB y el máximo es 25MB.`);
        setArchivo(null);
        setPreview(null);
        return;
      }
      setError(null);
    }
    setArchivo(f);
    setPreview(f ? URL.createObjectURL(f) : null);
  };

  /** Marca el punto con validación inmediata (dentro del lote, fuera de exclusiones). */
  const marcarPunto = (lat: number, lon: number) => {
    const v = validarPuntoCalibracion(lat, lon, (detalle?.features ?? []) as unknown as FeatureSimple[]);
    if (!v.ok) {
      setPunto(null);
      setPuntoError(v.motivo);
      return;
    }
    setPuntoError(null);
    setPunto({ lat, lon });
  };

  const subir = async () => {
    if (!potrero || !punto || !archivo || !fecha) return;
    setSubiendo(true);
    setError(null);
    try {
      const r = await api.subirFoto(potrero.id, punto.lat, punto.lon, fecha, archivo);
      setExito(r);
      setSubidasSesion((n) => n + 1);
      const gal = await api.fotosDePotrero(potrero.id);
      setGaleria(gal.fotos);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error subiendo foto');
    } finally {
      setSubiendo(false);
    }
  };

  const otraFoto = () => {
    onArchivo(null);
    setPunto(null);
    setPuntoError(null);
    setExito(null);
    setError(null);
    setPaso(2);
  };

  /** Otra foto en el mismo punto (sin re-marcar). */
  const otraFotoMismoPunto = () => {
    onArchivo(null);
    setExito(null);
    setError(null);
  };

  return (
    <div className="panel">
      <div className="serie-head">
        <h3>Calibración de IA{subidasSesion > 0 && ` · ${subidasSesion} subida${subidasSesion === 1 ? '' : 's'} esta sesión`}</h3>
        <div className="calib-steps" aria-label="Progreso">
          {(['Potrero', 'Punto', 'Foto'] as const).map((label, i) => {
            const done = paso > i + 1;
            return (
              <span key={label} className={`calib-step ${paso === i + 1 ? 'active' : ''} ${done ? 'done' : ''}`}>
                <span className="calib-num">{done ? '✓' : i + 1}</span> {label}
              </span>
            );
          })}
        </div>
      </div>

      {error && <p className="error-text">{error}</p>}

      {paso === 1 && (
        <div className="calib-block">
          <h4 className="calib-title">1 · Elegí el potrero</h4>
          <p className="muted">Elegí el potrero del cual vas a subir la foto.</p>
          <label>
            Potrero
            <select value={potreroId} onChange={(e) => setPotreroId(e.target.value)} disabled={loading || potreros.length === 0}>
              <option value="">— Elegir —</option>
              {fincas.map((f) => (
                <optgroup key={f} label={f}>
                  {potreros.filter((p) => p.finca === f).map((p) => (
                    <option key={p.id} value={p.id}>{p.nombre}</option>
                  ))}
                </optgroup>
              ))}
            </select>
          </label>
          {loading && <span className="muted">Cargando…</span>}
          {!loading && potreros.length === 0 && !error && <span className="muted">No tenés potreros cargados.</span>}
          <div>
            <button type="button" onClick={() => void elegirPotrero()} disabled={!potreroId || loading}>Continuar →</button>
          </div>
        </div>
      )}

      {paso === 2 && potrero && (
        <div className="calib-block">
          <h4 className="calib-title">2 · Marcá el punto exacto</h4>
          <p className="muted">
            <strong>{potrero.nombre}</strong> · {potrero.finca}
            {galeria.length > 0 && ` · ${galeria.length} foto${galeria.length === 1 ? '' : 's'} ya`} — hacé click en el mapa para marcar el punto exacto de la foto.
          </p>
          <div className="map-wrap">
            <MapaPunto features={detalle?.features ?? []} punto={punto} onPunto={marcarPunto} />
          </div>
          {punto && (
            <span className="muted small" style={{ color: 'var(--delta-up)', fontWeight: 600 }}>
              ✓ Punto válido: {punto.lat.toFixed(6)}, {punto.lon.toFixed(6)}
            </span>
          )}
          {puntoError && <p className="error-text">{puntoError}</p>}
          <div className="calib-actions">
            <button type="button" className="ghost-btn" onClick={() => setPaso(1)}>← Cambiar potrero</button>
            <button type="button" onClick={() => setPaso(3)} disabled={!punto}>Continuar →</button>
          </div>
        </div>
      )}

      {paso === 3 && potrero && punto && (
        <div className="calib-block">
          {!exito ? (
            <>
              <h4 className="calib-title">3 · Subí la foto</h4>
              <p className="muted">
                <strong>{potrero.nombre}</strong> · {punto.lat.toFixed(6)}, {punto.lon.toFixed(6)} — elegí la fecha que calibra y la foto.
              </p>
              <label>
                Fecha de la lectura
                <select value={fecha} onChange={(e) => setFecha(e.target.value)} disabled={fechas.length === 0}>
                  <option value="">— Elegir —</option>
                  {fechas.map((f) => (
                    <option key={f} value={f}>{fmtFechaCorta(f)}</option>
                  ))}
                </select>
              </label>
              <label
                className="dropzone"
                onDragOver={(e) => { e.preventDefault(); e.currentTarget.classList.add('over'); }}
                onDragLeave={(e) => e.currentTarget.classList.remove('over')}
                onDrop={(e) => { e.preventDefault(); e.currentTarget.classList.remove('over'); onArchivo(e.dataTransfer.files?.[0] ?? null); }}
              >
                <span className="dropzone-icon" aria-hidden>📷</span>
                <span className="dropzone-title">{archivo ? 'Foto lista' : 'Arrastrá la foto o tocá para elegirla'}</span>
                <span className="dropzone-hint">JPG, PNG, WebP, HEIC o TIFF · máx 25MB</span>
                {archivo && <span className="dropzone-file">{archivo.name} · {(archivo.size / 1048576).toFixed(1)} MB</span>}
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp,image/heic,image/heif,image/tiff,.jpg,.jpeg,.png,.webp,.heic,.heif,.tif,.tiff"
                  onChange={(e) => onArchivo(e.target.files?.[0] ?? null)}
                />
              </label>
              {preview && <img src={preview} alt="Vista previa" className="calib-preview" />}
              {subiendo && <span className="muted">Subiendo…</span>}
              <div className="calib-actions">
                <button type="button" className="ghost-btn" onClick={() => setPaso(2)}>← Mover punto</button>
                <button type="button" onClick={subir} disabled={!archivo || !fecha || subiendo}>
                  {subiendo ? 'Subiendo…' : 'Subir foto'}
                </button>
              </div>
            </>
          ) : (
            <div className="calib-ok">
              <h4>✓ Foto subida</h4>
              <p className="muted">
                {exito.potrero} · {fmtFechaCorta(exito.fecha)} · {exito.latitud.toFixed(5)}, {exito.longitud.toFixed(5)} — ya podés seguir agregando más.
              </p>
              <div className="calib-actions">
                <button type="button" onClick={otraFotoMismoPunto}>+ Otra foto aquí</button>
                <button type="button" className="ghost-btn" onClick={otraFoto}>Otro punto</button>
                <button type="button" className="ghost-btn" onClick={() => { setPotreroId(''); setDetalle(null); setPaso(1); setExito(null); }}>
                  Cambiar de potrero
                </button>
              </div>
            </div>
          )}

          {galeria.length > 0 && (
            <div className="calib-galeria">
              <h4>Fotos de {potrero.nombre} ({galeria.length})</h4>
              <div className="calib-grid">
                {galeria.map((f) => (
                  <a key={f.id} href={api.fotoUrl(f.url)} target="_blank" rel="noreferrer" title={`${fmtFechaCorta(f.fecha)} · ${f.latitud.toFixed(5)}, ${f.longitud.toFixed(5)}`}>
                    <img src={api.fotoUrl(f.url)} alt={`Foto ${f.id}`} loading="lazy" />
                    <small>{fmtFechaCorta(f.fecha)}</small>
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
