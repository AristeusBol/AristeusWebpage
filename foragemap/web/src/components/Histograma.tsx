import { useEffect, useState } from 'react';
import { api, type HistogramaResponse, type TipoDensidad } from '../lib/api';
import { fmtFechaCorta } from '../lib/masaSeca';

interface Props {
  finca: string;
  fecha: string;
  fechas: string[];
  onFecha: (fecha: string) => void;
}

const TIPOS: { id: TipoDensidad; label: string; color: string }[] = [
  { id: 'verde', label: 'Verde', color: '#22c55e' },
  { id: 'muerta', label: 'Muerta', color: '#b26a00' },
  { id: 'total', label: 'Total', color: '#15803d' },
];

const W = 860;
const H = 300;
const PAD = { l: 56, r: 12, t: 12, b: 30 };

/** Histograma de peso por punto (kg): % de puntos por finca y fecha. */
export default function Histograma({ finca, fecha, fechas, onFecha }: Props) {
  const [tipo, setTipo] = useState<TipoDensidad>('total');
  const [bins, setBins] = useState(20);
  const [data, setData] = useState<HistogramaResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hover, setHover] = useState<number | null>(null);

  useEffect(() => {
    if (!finca || !fecha) return;
    setLoading(true);
    setError(null);
    api.histograma(finca, fecha, tipo, bins)
      .then((d) => setData(d))
      .catch((e) => setError(e instanceof Error ? e.message : 'Error cargando histograma'))
      .finally(() => setLoading(false));
  }, [finca, fecha, tipo, bins]);

  const color = TIPOS.find((t) => t.id === tipo)?.color ?? '#15803d';
  const intervalos = data?.intervalos ?? [];
  const stats = data?.stats ?? null;
  const maxPct = intervalos.reduce((m, b) => Math.max(m, b.pct), 0);
  const maxY = maxPct > 0 ? maxPct * 1.1 : 1;

  const iw = W - PAD.l - PAD.r;
  const ih = H - PAD.t - PAD.b;
  const band = intervalos.length > 0 ? iw / intervalos.length : iw;
  const bw = Math.max(2, band * 0.75);
  const X = (i: number) => PAD.l + i * band + (band - bw) / 2;
  const Y = (p: number) => PAD.t + ih - (p / maxY) * ih;

  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((f) => maxY * f);
  const xTicks = intervalos.length > 0
    ? [0, 0.25, 0.5, 0.75, 1].map((f) => {
        const idx = Math.min(intervalos.length - 1, Math.round(f * (intervalos.length - 1)));
        return { x: X(idx) + bw / 2, v: f === 1 ? intervalos[idx].lim_sup : intervalos[idx].lim_inf };
      })
    : [];

  const meanX = stats && stats.mean !== null && stats.min !== null && stats.max !== null && stats.max > stats.min
    ? PAD.l + ((stats.mean - stats.min) / (stats.max - stats.min)) * iw
    : null;

  const onMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const rect = (e.currentTarget as SVGSVGElement).getBoundingClientRect();
    const mx = (e.clientX - rect.left) * (W / rect.width);
    const i = Math.floor((mx - PAD.l) / band);
    setHover(i >= 0 && i < intervalos.length ? i : null);
  };

  const fmtN = (v: number) => v.toLocaleString('es-AR', { maximumFractionDigits: 0 });
  const fmtG = (v: number) => v.toLocaleString('es-AR', { maximumFractionDigits: 1 });
  const fmtP = (v: number) => `${v.toLocaleString('es-AR', { maximumFractionDigits: 1 })}%`;

  return (
    <div className="panel">
      <div className="serie-head">
        <h3>Histograma · {finca || '—'}</h3>
        <div className="serie-controls">
          <label>
            Fecha
            <select value={fecha} onChange={(e) => onFecha(e.target.value)} disabled={fechas.length === 0}>
              <option value="">— Elegir —</option>
              {fechas.map((f) => (
                <option key={f} value={f}>{fmtFechaCorta(f)}</option>
              ))}
            </select>
          </label>
          <div className="serie-metric" role="group" aria-label="Densidad">
            {TIPOS.map((t) => (
              <button key={t.id} type="button" className={tipo === t.id ? 'active' : ''} onClick={() => setTipo(t.id)}>
                {t.label}
              </button>
            ))}
          </div>
          <label>
            Intervalos
            <select value={bins} onChange={(e) => setBins(Number(e.target.value))}>
              {[10, 20, 30, 50].map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
          </label>
        </div>
      </div>

      {stats && stats.count > 0 && (
        <div className="comp-strip">
          <span className="comp-strip-vals">
            <span><em>n</em> {fmtN(stats.count)}</span><span className="sep">·</span>
            <span><em>mín</em> {fmtG(stats.min ?? 0)}</span><span className="sep">·</span>
            <span><em>media</em> {fmtG(stats.mean ?? 0)}</span><span className="sep">·</span>
            <span><em>máx</em> {fmtG(stats.max ?? 0)}</span>
            <small>kg/punto</small>
          </span>
        </div>
      )}

      {loading && <span className="muted">Cargando histograma…</span>}
      {error && <p className="error-text">{error}</p>}
      {!loading && !error && (!finca || !fecha) && (
        <span className="muted">Elegí finca y fecha para ver la distribución.</span>
      )}
      {!loading && !error && finca && fecha && data?.sin_datos && (
        <span className="muted">Sin puntos para esa finca y fecha.</span>
      )}
      {!loading && !error && intervalos.length > 0 && (
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="serie-svg"
          onMouseMove={onMove}
          onMouseLeave={() => setHover(null)}
          role="img"
          aria-label="Histograma de peso por punto"
        >
          {yTicks.map((t) => {
            const y = PAD.t + ih - (t / maxY) * ih;
            return (
              <g key={t}>
                <line x1={PAD.l} x2={W - PAD.r} y1={y} y2={y} stroke="#e7ede6" />
                <text x={PAD.l - 6} y={y + 4} textAnchor="end" className="tick">{fmtP(t)}</text>
              </g>
            );
          })}
          {xTicks.map((t, i) => (
            <text key={i} x={t.x} y={H - 8} textAnchor="middle" className="tick">{fmtG(t.v)}</text>
          ))}
          <text x={W - PAD.r} y={H - 8} textAnchor="end" className="tick">kg</text>
          {intervalos.map((b, i) => (
            <g key={i}>
              <title>{`${fmtG(b.lim_inf)} – ${fmtG(b.lim_sup)} kg: ${fmtN(b.count)} puntos (${fmtP(b.pct)})`}</title>
              <rect
                x={X(i)}
                y={Y(b.pct)}
                width={bw}
                height={Math.max(0, PAD.t + ih - Y(b.pct))}
                rx="3"
                fill={color}
                fillOpacity={hover === i ? 1 : 0.8}
                stroke={hover === i ? '#14532d' : 'none'}
                strokeWidth={hover === i ? 1.5 : 0}
              />
            </g>
          ))}
          {meanX !== null && (
            <g>
              <line x1={meanX} x2={meanX} y1={PAD.t} y2={PAD.t + ih} stroke="#14532d" strokeDasharray="5 3" strokeWidth="1.5" />
              <text x={Math.min(meanX + 4, W - PAD.r - 60)} y={PAD.t + 12} className="tick serie-last">
                media {fmtG(stats?.mean ?? 0)}
              </text>
            </g>
          )}
          {hover !== null && intervalos[hover] && (
            <g transform={`translate(${Math.min(X(hover) + bw + 8, W - 210)},${PAD.t + 6})`}>
              <rect width="200" height="78" rx="8" fill="rgba(20,35,20,.92)" />
              <text x="10" y="18" fill="#fff" fontSize="12" fontWeight="700">
                {fmtG(intervalos[hover].lim_inf)} – {fmtG(intervalos[hover].lim_sup)} kg
              </text>
              <text x="10" y="38" fill="#e7f6e3" fontSize="12">
                {fmtN(intervalos[hover].count)} puntos
              </text>
              <text x="10" y="58" fill="#e7f6e3" fontSize="12">
                {fmtP(intervalos[hover].pct)} del total
              </text>
            </g>
          )}
        </svg>
      )}
    </div>
  );
}
