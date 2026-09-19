interface Props {
  colapsado: boolean;
  onColapsar: () => void;
  vista: string;
  onVista: (v: string) => void;
}

const SECCIONES: { titulo: string; items: { id: string; label: string; pronto?: boolean }[] }[] = [
  {
    titulo: 'ANÁLISIS DE PASTOS',
    items: [
      { id: 'mapa', label: 'Mapa de Masa Seca' },
      { id: 'series', label: 'Series Temporales' },
      { id: 'histograma', label: 'Histograma' },
      { id: 'calibracion', label: 'Calibración de IA' },
    ],
  },
  {
    titulo: 'GESTIÓN DE GANADOS',
    items: [
      { id: 'lotes', label: 'Lotes' },
      { id: 'rotacion', label: 'Rotación' },
      { id: 'trayectorias', label: 'Trayectorias' },
    ],
  },
  {
    titulo: 'REPORTES',
    items: [{ id: 'exportar', label: 'Exportar Datos', pronto: true }],
  },
  {
    titulo: 'SOPORTE',
    items: [{ id: 'ayuda', label: 'Ayuda y Soporte', pronto: true }],
  },
];

export default function Sidebar({ colapsado, onColapsar, vista, onVista }: Props) {
  const handle = (id: string) => {
    onVista(id);
  };

  return (
    <aside className={`sidebar ${colapsado ? 'colapsado' : ''}`}>
      <div className="brand">
        <img className="brand-logo" src={`${import.meta.env.BASE_URL}grass_gauge.png`} alt="GrassGauge" />
        {!colapsado && (
          <span className="brand-text">
            <strong>GrassGauge</strong>
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
                >
                  <span className="side-dot" />
                  {it.label}
                </button>
              ))}
            </div>
          ))}
        </nav>
      )}

      <button type="button" className="collapse-btn" onClick={onColapsar} title={colapsado ? 'Expandir menú' : 'Colapsar menú'}>
        {colapsado ? '»' : '« Colapsar menú'}
      </button>
    </aside>
  );
}
