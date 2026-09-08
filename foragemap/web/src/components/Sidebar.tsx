import { docsUrl } from './Topbar';

interface Props {
  colapsado: boolean;
  onColapsar: () => void;
  vista: string;
  onVista: (v: string) => void;
  onExportar: () => void;
  exportando: boolean;
  ultimaSync: number | null;
  sincronizando: boolean;
}

const SECCIONES: { titulo: string; items: { id: string; label: string; pronto?: boolean }[] }[] = [
  {
    titulo: 'ANÁLISIS',
    items: [
      { id: 'mapa', label: 'Mapa de Masa Seca' },
      { id: 'series', label: 'Series Temporales' },
      { id: 'histograma', label: 'Histograma' },
    ],
  },
  {
    titulo: 'GESTIÓN',
    items: [
      { id: 'rodeos', label: 'Gestión de Rodeos' },
      { id: 'calibracion', label: 'Calibración de IA' },
    ],
  },
  {
    titulo: 'REPORTES',
    items: [{ id: 'exportar', label: 'Exportar Datos' }],
  },
  {
    titulo: 'SOPORTE',
    items: [{ id: 'ayuda', label: 'Ayuda y Soporte' }],
  },
];

export default function Sidebar({ colapsado, onColapsar, vista, onVista, onExportar, exportando, ultimaSync, sincronizando }: Props) {
  const handle = (id: string) => {
    if (id === 'exportar') {
      onExportar();
      return;
    }
    if (id === 'ayuda') {
      window.open(docsUrl(), '_blank', 'noopener');
      return;
    }
    onVista(id);
  };

  return (
    <aside className={`sidebar ${colapsado ? 'colapsado' : ''}`}>
      <div className="brand">
        <span className="brand-logo">◈</span>
        {!colapsado && (
          <span className="brand-text">
            <strong>ForageMap</strong>
            <small>Masa Seca</small>
          </span>
        )}
      </div>

      {!colapsado && (
        <nav className="side-nav">
          {SECCIONES.map((sec) => (
            <div key={sec.titulo} className="side-sec">
              <span className="side-sec-titulo">{sec.titulo}</span>
              {sec.items.map((it) => (
                <button
                  key={it.id}
                  type="button"
                  className={`side-item ${vista === it.id ? 'activo' : ''} ${it.pronto ? 'pronto' : ''}`}
                  title={it.pronto ? 'Próximamente' : it.label}
                  onClick={() => handle(it.id)}
                  disabled={it.id === 'exportar' && exportando}
                >
                  <span className="side-dot" />
                  {it.label}
                  {it.id === 'exportar' && exportando ? '…' : ''}
                </button>
              ))}
            </div>
          ))}
        </nav>
      )}

      {!colapsado && (
        <div className="sync-card">
          <span className={`sync-dot ${sincronizando ? 'syncing' : ''}`} />
          <div>
            <strong>{sincronizando ? 'Sincronizando…' : 'Datos guardados'}</strong>
            <small>
              Última sincronización
              <br />
              {ultimaSync ? new Date(ultimaSync).toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' }) : '—'}
            </small>
          </div>
        </div>
      )}

      <button type="button" className="collapse-btn" onClick={onColapsar} title={colapsado ? 'Expandir menú' : 'Colapsar menú'}>
        {colapsado ? '»' : '« Colapsar menú'}
      </button>
    </aside>
  );
}
