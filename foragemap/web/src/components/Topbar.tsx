import { API_URL } from '../lib/api';

interface Props {
  busqueda: string;
  onBusqueda: (v: string) => void;
  onBuscar: () => void;
  fincas: string[];
  finca: string;
  onFinca: (v: string) => void;
  cargando: boolean;
  nombre: string;
  email: string;
  onSalir: () => void;
  notifCount: number;
}

function iniciales(nombre: string, email: string): string {
  const base = nombre.trim() || email.split('@')[0].replace(/[._-]+/g, ' ');
  const partes = base.split(/\s+/).filter(Boolean);
  if (partes.length >= 2) return (partes[0][0] + partes[1][0]).toUpperCase();
  return base.slice(0, 2).toUpperCase();
}

/** URL de la doc API: misma base que el backend, o localhost en dev (sin proxy /docs). */
export function docsUrl(): string {
  return API_URL ? `${API_URL}/docs` : 'http://localhost:8000/docs';
}

export default function Topbar({
  busqueda, onBusqueda, onBuscar,
  fincas, finca, onFinca, cargando,
  nombre, email, onSalir, notifCount,
}: Props) {
  return (
    <header className="topbar2">
      <form
        className="search"
        onSubmit={(e) => {
          e.preventDefault();
          onBuscar();
        }}
      >
        <span className="search-icon">⌕</span>
        <input
          value={busqueda}
          onChange={(e) => onBusqueda(e.target.value)}
          placeholder="Buscar campo, lote o actividad…"
          aria-label="Buscar lote"
        />
      </form>

      <label className="pill-select">
        <small>Finca</small>
        <select value={finca} onChange={(e) => onFinca(e.target.value)} disabled={cargando || fincas.length === 0} aria-label="Finca">
          <option value="">Elegir…</option>
          {fincas.map((f) => (
            <option key={f} value={f}>{f}</option>
          ))}
        </select>
      </label>

      <span className="icon-btn" title={`${notifCount} lotes en la finca`} aria-label={`${notifCount} lotes en la finca`}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.7 21a2 2 0 0 1-3.4 0" />
        </svg>
        {notifCount > 0 && <span className="badge">{notifCount}</span>}
      </span>
      <a className="icon-btn link" title="Documentación API" href={docsUrl()} target="_blank" rel="noreferrer">
        ?
      </a>

      <div className="user-chip" title={`${nombre} · ${email}`}>
        <span className="avatar">{iniciales(nombre, email)}</span>
        <span className="user-meta">
          <strong>{nombre || email.split('@')[0]}</strong>
          <small>Administrador</small>
        </span>
        <button type="button" className="ghost-btn" onClick={onSalir} title="Cerrar sesión">
          Salir
        </button>
      </div>
    </header>
  );
}
