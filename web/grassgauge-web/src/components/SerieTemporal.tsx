import { useEffect, useMemo, useState } from 'react';
import { api, type PotreroItem, type SeriePunto } from '../lib/api';
import { fmtFechaCorta, paradasDegradado } from '../lib/masaSeca';
import { ESTADOS, niceTicks } from '../lib/zonas';

interface Props {
  finca: string;
  lotes: PotreroItem[];
  /** Lote seleccionado en el mapa: la serie lo sigue (puede cambiarse manual). */
  loteIdExterno?: number | null;
  /** Parcela seleccionada en el mapa: la serie la sigue si pertenece al lote. */
  parcelaIdExterna?: number | null;
}

const SERIES = [
  { id: 'verde', label: 'Verde', color: '#10b981' },
  { id: 'muerta', label: 'Muerta', color: '#78350f' },
  { id: 'total', label: 'Total', color: '#111827' },
] as const;

type SerieId = (typeof SERIES)[number]['id'];

const W = 1020;
const H = 430;
const PAD = { l: 40, r: 38, t: 4, b: 46 };

function valor(p: SeriePunto, s: SerieId): number {
  return s === 'verde' ? p.verde_kg : s === 'muerta' ? p.muerta_kg : p.total_kg;
}

function share(p: SeriePunto, s: 'verde' | 'muerta'): number {
  const t = p.verde_kg + p.muerta_kg;
  return t > 0 ? ((s === 'verde' ? p.verde_kg : p.muerta_kg) / t) * 100 : 0;
}

/** Gráfico de líneas minimalista: evolución del stock en el tiempo. */
export default function SerieTemporal({ finca, lotes, loteIdExterno, parcelaIdExterna }: Props) {
  const [loteId, setLoteId] = useState<string>('');
  const [parcelaId, setParcelaId] = useState<string>('');
  const [parcelas, setParcelas] = useState<{ id: number; nombre: string }[]>([]);
  const [activas, setActivas] = useState<Record<SerieId, boolean>>({ verde: true, muerta: true, total: true });
  const [puntos, setPuntos] = useState<SeriePunto[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hover, setHover] = useState<{ i: number; id: SerieId } | null>(null);

  useEffect(() => {
    if (loteIdExterno === undefined) return;
    setLoteId(loteIdExterno ? String(loteIdExterno) : '');
  }, [loteIdExterno]);

  // Parcelas del lote elegido (submenú perezoso): al cambiar de lote se
  // resetea la parcela; la externa solo aplica si pertenece al lote.
  useEffect(() => {
    setParcelaId('');
    if (!loteId) { setParcelas([]); return; }
    let vivo = true;
    api.parcelasDePotrero(Number(loteId))
      .then((d) => {
        if (!vivo) return;
        const pars = d.features.map((f) => ({ id: f.properties.id, nombre: f.properties.nombre }));
        setParcelas(pars);
        if (parcelaIdExterna != null && pars.some((p) => p.id === parcelaIdExterna)) {
          setParcelaId(String(parcelaIdExterna));
        }
      })
      .catch(() => { if (vivo) setParcelas([]); });
    return () => { vivo = false; };
  }, [loteId, parcelaIdExterna]);

  useEffect(() => {
    if (!finca) return;
    setLoading(true);
    setError(null);
    // Parcela y potrero son excluyentes en la API: con parcela se manda
    // solo parcela_id (el backend resuelve el potrero padre como contexto).
    const parc = parcelaId ? Number(parcelaId) : null;
    api.serie(finca, parc ? null : (loteId ? Number(loteId) : null), parc)
      .then((d) => setPuntos(d.puntos))
      .catch((e) => setError(e instanceof Error ? e.message : 'Error cargando serie'))
      .finally(() => setLoading(false));
  }, [finca, loteId, parcelaId]);

  const unidad = 't/ha';
  /** Valor en t/ha (kg / área / 1000). Sin área cae a kg para no romper. */
  const val = (p: SeriePunto, s: SerieId): number => {
    const kg = valor(p, s);
    return p.area_ha > 0 ? kg / p.area_ha / 1000 : kg;
  };
  const fmtV = (v: number) => v.toLocaleString('es-AR', { maximumFractionDigits: 2 });

  const { maxV, ticks, paths, coords, grad } = useMemo(() => {
    const ids = SERIES.filter((s) => activas[s.id]).map((s) => s.id);
    let dataMax = 0;
    for (const p of puntos) for (const id of ids) dataMax = Math.max(dataMax, val(p, id));
    // Rango completo fijo 0–5 (todas las franjas visibles): no reescala al
    // cambiar de lote. Solo crece si un dato supera el tope.
    const top = Math.max(5, niceTicks(dataMax).top);
    const { ticks } = niceTicks(top);
    const max = top;
    const iw = W - PAD.l - PAD.r;
    const ih = H - PAD.t - PAD.b;
    const X = (i: number) => (puntos.length === 1 ? PAD.l + iw / 2 : PAD.l + (i / (puntos.length - 1)) * iw);
    const Y = (v: number) => PAD.t + ih - (v / max) * ih;
    const paths = ids.map((id) => ({
      id,
      d: puntos.map((p, i) => `${i === 0 ? 'M' : 'L'}${X(i).toFixed(1)},${Y(val(p, id)).toFixed(1)}`).join(' '),
    }));
    const coords = puntos.map((p, i) => ({
      x: X(i),
      dots: ids.map((id) => ({ id, y: Y(val(p, id)), v: val(p, id) })),
    }));
    // Fondo con las mismas paradas del mapa de masa seca: tramos sólidos por
    // zona y fundido corto en cada corte. La última banda se estira hasta el
    // tope (igual que en el mapa los valores altos quedan en morado).
    // La leyenda de abajo sigue mostrando solo las 5 zonas (ESTADOS).
    let grad: { stops: { o: number; c: string }[] } | null = null;
    if (puntos.length > 0) {
      const off = (v: number) => Math.max(0, Math.min(1, 1 - v / max));
      const paradas = paradasDegradado();
      const ultimo = paradas[paradas.length - 1].color;
      const cand: { v: number; o: number; c: string }[] = [{ v: max, o: off(max), c: ultimo }];
      for (const p of paradas) {
        const t = p.v / 100;
        if (t <= 0 || t >= max) continue;
        cand.push({ v: t, o: off(t), c: p.color });
      }
      cand.push({ v: 0, o: off(0), c: paradas[0].color });
      cand.sort((a, b2) => b2.v - a.v); // offsets ascendentes = valores descendentes
      grad = { stops: cand.map(({ o, c }) => ({ o, c })) };
    }
    return { maxV: max, ticks, paths, coords, grad };
  }, [puntos, activas]);

  const toggle = (id: SerieId) => setActivas((a) => ({ ...a, [id]: !a[id] }));

  /** Estado del último valor según las franjas (siempre en t MS/ha). */
  const estado = useMemo(() => {
    if (puntos.length === 0) return null;
    const last = puntos[puntos.length - 1];
    if (!(last.area_ha > 0)) return null;
    const tha = last.total_kg / last.area_ha / 1000;
    const e = ESTADOS.find((r) => tha >= r.min && tha <= r.max) ?? ESTADOS[ESTADOS.length - 1];
    return { txt: e.nombre, color: e.texto, banda: e.color, tha };
  }, [puntos]);
  const deltas = useMemo(() => {
    if (puntos.length < 2) return [];
    const a = puntos[puntos.length - 2];
    const b = puntos[puntos.length - 1];
    return SERIES.filter((s) => activas[s.id]).map((s) => {
      const va = val(a, s.id);
      const vb = val(b, s.id);
      const d = va !== 0 ? ((vb - va) / Math.abs(va)) * 100 : vb > 0 ? 100 : 0;
      return { id: s.id, label: s.label, d };
    });
  }, [puntos, activas]);

  return (
    <div className="panel">
      <div className="serie-head">
        <div className="serie-left">
          <label>
            Potrero
            <select value={loteId} onChange={(e) => setLoteId(e.target.value)}>
              <option value="">Toda la estancia</option>
              {lotes.map((l) => (
                <option key={l.id} value={l.id}>{l.nombre}</option>
              ))}
            </select>
          </label>
          {parcelas.length > 0 && (
            <label>
              Parcela
              <select value={parcelaId} onChange={(e) => setParcelaId(e.target.value)} aria-label="Parcela del potrero">
                <option value="">Todo el potrero</option>
                {parcelas.map((p) => (
                  <option key={p.id} value={p.id}>{p.nombre}</option>
                ))}
              </select>
            </label>
          )}
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
        {deltas.length > 0 && (
          <div className="delta-row delta-right" style={{ gap: 14 }} title={`Variación vs ${fmtFechaCorta(puntos[puntos.length - 2].fecha)}`}>
            {estado && (
              <span
                style={{ fontSize: '0.78rem', fontWeight: 700, color: estado.banda }}
                title={`Total última fecha: ${estado.tha.toFixed(2)} t MS/ha`}
              >
                {estado.txt}
              </span>
            )}
            {deltas.map((d) => {
              const sube = d.d >= 0;
              return (
                <span key={d.id} style={{ fontSize: '0.78rem', fontWeight: 600, color: '#111827' }}>
                  {d.label}:
                  <b style={{ color: sube ? '#15803d' : '#b91c1c' }}>
                    {' '}{sube ? '▲' : '▼'} {Math.abs(d.d).toFixed(1)}%
                  </b>
                </span>
              );
            })}
          </div>
        )}
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
          role="img"
          aria-label="Serie temporal de masa seca"
        >
          {grad && (
            <g>
              <defs>
                <linearGradient id="zonas-cycle" x1="0" y1="0" x2="0" y2="1">
                  {grad.stops.map((s, k) => (
                    <stop key={k} offset={s.o} stopColor={s.c} />
                  ))}
                </linearGradient>
              </defs>
              <rect x={PAD.l} y={PAD.t} width={W - PAD.l - PAD.r} height={H - PAD.t - PAD.b} fill="url(#zonas-cycle)" />
            </g>
          )}
          {(() => {
            const pw = W - PAD.l - PAD.r;
            const ph = H - PAD.t - PAD.b;
            const yy = (t: number) => PAD.t + ph - (t / maxV) * ph;
            return (
              <g>
                <rect x={PAD.l} y={PAD.t} width={pw} height={ph} fill="none" stroke="#000" strokeWidth={0.75} />
                {ticks.map((t) => (
                  <g key={t}>
                    <line x1={PAD.l - 4} x2={PAD.l} y1={yy(t)} y2={yy(t)} stroke="#000" strokeWidth={0.75} />
                    <text x={PAD.l - 8} y={yy(t) + 4} textAnchor="end" className="tick">{fmtV(t)}</text>
                  </g>
                ))}
                <text
                  x={15} y={PAD.t + ph / 2} textAnchor="middle" className="axis-title"
                  transform={`rotate(-90 15 ${PAD.t + ph / 2})`}
                >
                  Biomasa (t MS ha⁻¹)
                </text>
              </g>
            );
          })()}
          {puntos.map((p, i) => {
            const x = coords[i]?.x ?? 0;
            return (
              <g key={p.fecha}>
                <line x1={x} x2={x} y1={H - PAD.b} y2={H - PAD.b + 4} stroke="#000" strokeWidth={0.75} />
                <text x={x} y={H - PAD.b + 18} textAnchor="middle" className="tick">
                  {fmtFechaCorta(p.fecha).slice(0, 5)}
                </text>
              </g>
            );
          })}
          <text x={(PAD.l + W - PAD.r) / 2} y={H - 4} textAnchor="middle" className="axis-title">
            Fecha
          </text>
          {paths.map((s) => {
            const color = SERIES.find((x) => x.id === s.id)?.color;
            const base = s.id === 'total' ? 3 : 2.5;
            return (
              <path
                key={s.id}
                d={s.d}
                fill="none"
                stroke={color}
                strokeWidth={base}
                strokeLinecap="round"
                opacity={s.id === 'total' ? 1 : 0.95}
              />
            );
          })}
          {coords.map((c, i) =>
            c.dots.map((d) => {
              const isHover = hover !== null && hover.i === i && hover.id === d.id;
              // Toda la fecha resaltada: la caja muestra las 3 series.
              // Las demás fechas se atenúan para que el grupo activo resalte.
              const isDateHover = hover !== null && hover.i === i;
              const dimmed = hover !== null && hover.i !== i;
              return (
                <g key={`${i}-${d.id}`}>
                  {/* Área de impacto invisible: facilita embocar el punto. */}
                  <circle
                    cx={c.x}
                    cy={d.y}
                    r={11}
                    fill="transparent"
                    onMouseEnter={() => setHover({ i, id: d.id })}
                    onMouseLeave={() => setHover(null)}
                  />
                  <circle
                    cx={c.x}
                    cy={d.y}
                    r={isHover ? 7 : isDateHover ? 5.5 : d.id === 'total' ? 4 : 3.5}
                    fill={SERIES.find((x) => x.id === d.id)?.color}
                    opacity={dimmed ? 0.3 : 1}
                    pointerEvents="none"
                  />
                </g>
              );
            }),
          )}
          {coords.length > 0 &&
            (() => {
              const last = coords[coords.length - 1].dots
                .map((d) => ({
                  id: d.id,
                  y: d.y,
                  v: d.v,
                  color: SERIES.find((x) => x.id === d.id)?.color ?? '#000',
                }))
                .sort((a, b) => a.y - b.y);
              // Separación mínima para que no se solapen.
              const GAP = 13;
              for (let k = 1; k < last.length; k++) {
                if (last[k].y < last[k - 1].y + GAP) last[k] = { ...last[k], y: last[k - 1].y + GAP };
              }
              return last.map((d) => (
                <text
                  key={`last-${d.id}`}
                  x={W - PAD.r + 6}
                  y={d.y + 4}
                  className="tick serie-last"
                  style={{ fill: d.color }}
                >
                  {fmtV(d.v)}
                </text>
              ));
            })()}
          {hover !== null && coords[hover.i] && (
            /* pointerEvents none: la caja no debe robar el hover del punto. */
            <g pointerEvents="none">
              <g transform={`translate(${Math.min(coords[hover.i].x + 10, W - 158)},${PAD.t + 6})`}>
                <rect width="148" height={20 + coords[hover.i].dots.length * 15} rx="7" fill="rgba(20,35,20,.92)" />
                <text x="8" y="15" fill="#fff" fontSize="11" fontWeight="700">
                  {fmtFechaCorta(puntos[hover.i].fecha)} · {unidad}
                </text>
                {coords[hover.i].dots.map((d, j) => (
                  <text key={d.id} x="8" y={30 + j * 15} fill="#e7f6e3" fontSize="11">
                    {SERIES.find((x) => x.id === d.id)?.label}: {fmtV(d.v)}
                    {d.id !== 'total' && ` (${share(puntos[hover.i], d.id).toFixed(0)}%)`}
                  </text>
                ))}
              </g>
            </g>
          )}
        </svg>
      )}
      {puntos.length >= 2 && (
        <div className="zonas-legend" aria-label="Franjas del ciclo (t MS/ha)">
          {ESTADOS.map((e) => (
            <span key={e.nombre} className="zona-item" title={`${e.min.toFixed(1)}–${e.max === Number.POSITIVE_INFINITY ? '+' : e.max.toFixed(1)} t MS/ha`}>
              <span className="swatch" style={{ background: e.color }} />
              {e.nombre} <small>{e.min.toFixed(1)}–{e.max === Number.POSITIVE_INFINITY ? '+' : e.max.toFixed(1)}</small>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
