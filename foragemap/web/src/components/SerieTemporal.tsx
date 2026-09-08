import { useEffect, useMemo, useState } from 'react';
import { api, type PotreroProps, type SeriePunto } from '../lib/api';
import { fmtFechaCorta } from '../lib/masaSeca';

interface Props {
  finca: string;
  lotes: PotreroProps[];
  /** Si se provee, click en un punto salta a esa fecha en el mapa. */
  onVerEnMapa?: (fecha: string) => void;
}

const SERIES = [
  { id: 'verde', label: 'Verde', color: '#22c55e' },
  { id: 'muerta', label: 'Muerta', color: '#b26a00' },
  { id: 'total', label: 'Total', color: '#15803d' },
] as const;

type SerieId = (typeof SERIES)[number]['id'];

const W = 860;
const H = 300;
const PAD = { l: 56, r: 52, t: 12, b: 30 };

function valor(p: SeriePunto, s: SerieId): number {
  return s === 'verde' ? p.verde_kg : s === 'muerta' ? p.muerta_kg : p.total_kg;
}

function share(p: SeriePunto, s: 'verde' | 'muerta'): number {
  const t = p.verde_kg + p.muerta_kg;
  return t > 0 ? ((s === 'verde' ? p.verde_kg : p.muerta_kg) / t) * 100 : 0;
}

/** Gráfico de líneas minimalista: evolución del stock (kg) en el tiempo. */
export default function SerieTemporal({ finca, lotes, onVerEnMapa }: Props) {
  const [loteId, setLoteId] = useState<string>('');
  const [activas, setActivas] = useState<Record<SerieId, boolean>>({ verde: true, muerta: true, total: true });
  const [puntos, setPuntos] = useState<SeriePunto[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hover, setHover] = useState<number | null>(null);

  useEffect(() => {
    if (!finca) return;
    setLoading(true);
    setError(null);
    api.serie(finca, loteId ? Number(loteId) : null)
      .then((d) => setPuntos(d.puntos))
      .catch((e) => setError(e instanceof Error ? e.message : 'Error cargando serie'))
      .finally(() => setLoading(false));
  }, [finca, loteId]);

  const unidad = 'kg';
  const fmtV = (v: number) => v.toLocaleString('es-AR', { maximumFractionDigits: 0 });

  const { maxV, paths, coords, areaTotal } = useMemo(() => {
    const ids = SERIES.filter((s) => activas[s.id]).map((s) => s.id);
    let max = 0;
    for (const p of puntos) for (const id of ids) max = Math.max(max, valor(p, id));
    max = max > 0 ? max * 1.15 : 1;
    const iw = W - PAD.l - PAD.r;
    const ih = H - PAD.t - PAD.b;
    const X = (i: number) => (puntos.length === 1 ? PAD.l + iw / 2 : PAD.l + (i / (puntos.length - 1)) * iw);
    const Y = (v: number) => PAD.t + ih - (v / max) * ih;
    const paths = ids.map((id) => ({
      id,
      d: puntos.map((p, i) => `${i === 0 ? 'M' : 'L'}${X(i).toFixed(1)},${Y(valor(p, id)).toFixed(1)}`).join(' '),
    }));
    const coords = puntos.map((p, i) => ({
      x: X(i),
      dots: ids.map((id) => ({ id, y: Y(valor(p, id)), v: valor(p, id) })),
    }));
    const base = PAD.t + ih;
    const areaTotal = activas.total && puntos.length > 0
      ? `${puntos.map((p, i) => `${i === 0 ? 'M' : 'L'}${X(i).toFixed(1)},${Y(valor(p, 'total')).toFixed(1)}`).join(' ')} L${X(puntos.length - 1).toFixed(1)},${base} L${X(0).toFixed(1)},${base} Z`
      : null;
    return { maxV: max, paths, coords, areaTotal };
  }, [puntos, activas]);

  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => maxV * f);
  const toggle = (id: SerieId) => setActivas((a) => ({ ...a, [id]: !a[id] }));

  const onMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const rect = (e.currentTarget as SVGSVGElement).getBoundingClientRect();
    const sx = W / rect.width;
    const mx = (e.clientX - rect.left) * sx;
    let best = 0;
    let bestD = Infinity;
    coords.forEach((c, i) => {
      const d = Math.abs(c.x - mx);
      if (d < bestD) { bestD = d; best = i; }
    });
    setHover(best);
  };

  return (
    <div className="panel">
      <div className="serie-head">
        <h3>Serie temporal · {finca || '—'}</h3>
        <div className="serie-controls">
          <label>
            Lote
            <select value={loteId} onChange={(e) => setLoteId(e.target.value)}>
              <option value="">Toda la finca</option>
              {lotes.map((l) => (
                <option key={l.id} value={l.id}>{l.nombre}</option>
              ))}
            </select>
          </label>
          <div className="serie-legend">
            {SERIES.map((s) => (
              <button
                key={s.id}
                type="button"
                className={activas[s.id] ? 'on' : 'off'}
                onClick={() => toggle(s.id)}
                title="Mostrar/ocultar serie"
              >
                <span className="swatch" style={{ background: activas[s.id] ? s.color : '#d4dcd3' }} />
                {s.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {loading && <span className="muted">Cargando serie…</span>}
      {error && <p className="error-text">{error}</p>}
      {!loading && !error && puntos.length < 2 && (
        <span className="muted">Se necesitan al menos 2 fechas con cálculo para graficar.</span>
      )}
      {puntos.length >= 2 && (
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="serie-svg"
          onMouseMove={onMove}
          onMouseLeave={() => setHover(null)}
          role="img"
          aria-label="Serie temporal de masa seca"
        >
          <defs>
            <linearGradient id="serie-area" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#15803d" stopOpacity="0.18" />
              <stop offset="100%" stopColor="#15803d" stopOpacity="0.02" />
            </linearGradient>
          </defs>
          {ticks.map((t) => {
            const y = PAD.t + (H - PAD.t - PAD.b) - (t / maxV) * (H - PAD.t - PAD.b);
            return (
              <g key={t}>
                <line x1={PAD.l} x2={W - PAD.r} y1={y} y2={y} stroke="#e7ede6" />
                <text x={PAD.l - 6} y={y + 4} textAnchor="end" className="tick">{fmtV(t)}</text>
              </g>
            );
          })}
          {puntos.map((p, i) => {
            const x = coords[i]?.x ?? 0;
            return (
              <text key={p.fecha} x={x} y={H - 8} textAnchor="middle" className="tick">
                {fmtFechaCorta(p.fecha).slice(0, 5)}
              </text>
            );
          })}
          {areaTotal && <path d={areaTotal} fill="url(#serie-area)" />}
          {paths.map((s) => (
            <path
              key={s.id}
              d={s.d}
              fill="none"
              stroke={SERIES.find((x) => x.id === s.id)?.color}
              strokeWidth={s.id === 'total' ? 2.5 : 1.5}
              strokeLinecap="round"
              opacity={s.id === 'total' ? 1 : 0.75}
            />
          ))}
          {coords.map((c, i) =>
            c.dots.map((d) => (
              <circle
                key={`${i}-${d.id}`}
                cx={c.x}
                cy={d.y}
                r={hover === i ? 4.5 : d.id === 'total' ? 3 : 2.5}
                fill={SERIES.find((x) => x.id === d.id)?.color}
                stroke="#fff"
                strokeWidth="1.5"
                className={onVerEnMapa ? 'serie-dot' : undefined}
                onClick={() => onVerEnMapa?.(puntos[i].fecha)}
              >
                <title>{`${fmtFechaCorta(puntos[i].fecha)} — ${fmtV(d.v)} ${unidad}${onVerEnMapa ? ' (ver en mapa)' : ''}`}</title>
              </circle>
            )),
          )}
          {coords.length > 0 && (
            <text
              x={W - PAD.r + 6}
              y={coords[coords.length - 1].dots.find((d) => d.id === 'total')?.y ?? 0}
              className="tick serie-last"
            >
              {fmtV(valor(puntos[puntos.length - 1], 'total'))}
            </text>
          )}
          {hover !== null && coords[hover] && (
            <g>
              <line
                x1={coords[hover].x} x2={coords[hover].x}
                y1={PAD.t} y2={H - PAD.b}
                stroke="#9db89a" strokeDasharray="4 3"
              />
              <g transform={`translate(${Math.min(coords[hover].x + 10, W - 190)},${PAD.t + 6})`}>
                <rect width="180" height={24 + coords[hover].dots.length * 18} rx="8" fill="rgba(20,35,20,.92)" />
                <text x="10" y="18" fill="#fff" fontSize="12" fontWeight="700">
                  {fmtFechaCorta(puntos[hover].fecha)} · {unidad}
                </text>
                {coords[hover].dots.map((d, j) => (
                  <text key={d.id} x="10" y={36 + j * 18} fill="#e7f6e3" fontSize="12">
                    {SERIES.find((x) => x.id === d.id)?.label}: {fmtV(d.v)}
                    {d.id !== 'total' && ` (${share(puntos[hover], d.id).toFixed(0)}%)`}
                  </text>
                ))}
              </g>
            </g>
          )}
        </svg>
      )}
    </div>
  );
}
