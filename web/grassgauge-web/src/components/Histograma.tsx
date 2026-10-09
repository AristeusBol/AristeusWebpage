import { useEffect, useMemo, useState } from 'react';
import { api, type HistogramaResponse, type PotreroItem } from '../lib/api';
import { fmtFechaCorta } from '../lib/masaSeca';
import { niceTicks } from '../lib/zonas';
import { useDataPalette } from '../hooks/useDataPalette';
import { useUiPalette } from '../hooks/useUiPalette';

interface Props {
  finca: string;
  fecha: string;
  fechas: string[];
  onFecha: (fecha: string) => void;
  lotes: PotreroItem[];
  /** Lote seleccionado en el mapa: el histograma lo sigue (puede cambiarse manual). */
  loteIdExterno?: number | null;
  /** Parcela seleccionada en el mapa: el histograma la sigue si pertenece al lote. */
  parcelaIdExterna?: number | null;
}

// Paleta propia del histograma (análisis distinto a Series: sin verdes/rojos de franjas).
// Pirámide vertical: Verde arriba, Muerta abajo.
const LADOS = [
  { id: 'verde', label: 'Verde', dir: -1 },
  { id: 'muerta', label: 'Muerta', dir: 1 },
] as const;

type SerieId = (typeof LADOS)[number]['id'];

const W = 860;
const H = 365;
const PAD = { l: 52, r: 14, t: 12, b: 46 };

/** Histograma comparado + comparativa por fecha (barras agrupadas t/ha). */
export default function Histograma({ finca, fecha, fechas, onFecha, lotes, loteIdExterno, parcelaIdExterna }: Props) {
  const pal = useDataPalette();
  const ui = useUiPalette();
  const colorDe = (id: SerieId): string =>
    id === 'verde' ? pal.verde : pal.muerta;
  const BINS = 50; // fijo: comparable entre fechas y lotes
  const [loteId, setLoteId] = useState<string>('');
  const [parcelaId, setParcelaId] = useState<string>('');
  const [parcelas, setParcelas] = useState<{ id: number; nombre: string }[]>([]);
  const [activas, setActivas] = useState<Record<SerieId, boolean>>({ verde: true, muerta: true });
  const [data, setData] = useState<HistogramaResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hover, setHover] = useState<number | null>(null);

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
    if (!finca || !fecha) return;
    setLoading(true);
    setError(null);
    // Parcela y potrero son excluyentes en la API: con parcela se manda
    // solo parcela_id (el backend resuelve el potrero padre como contexto).
    const parc = parcelaId ? Number(parcelaId) : null;
    api.histograma(finca, fecha, BINS, parc ? null : (loteId ? Number(loteId) : null), parc)
      .then((d) => setData(d))
      .catch((e) => setError(e instanceof Error ? e.message : 'Error cargando histograma'))
      .finally(() => setLoading(false));
  }, [finca, fecha, loteId, parcelaId]);

  const unit = 't/ha';

  const conv = useMemo(() => {
    const n = data?.stats.count ?? 0;
    const areaHa = data?.filtros.area_ha ?? 0;
    // Cada punto representa area_ha/count ha: valores del backend → t/ha.
    const k = areaHa > 0 && n > 0 ? n / areaHa / 1000 : 1;
    const edges = (data?.edges ?? []).map((e) => e * k);
    const ids = LADOS.filter((s) => activas[s.id]).map((s) => s.id);
    const series = ids.map((id) => {
      const s = data?.series[id];
      return {
        id,
        color: colorDe(id),
        dir: LADOS.find((x) => x.id === id)?.dir ?? 1,
        mean: s?.mean != null ? s.mean * k : null,
        counts: s?.counts ?? [],
        pcts: s?.pcts ?? [],
      };
    });
    const nbins = Math.max(0, edges.length - 1);
    return { n, edges, series, nbins };
  }, [data, activas]);

  const { edges, series, nbins } = conv;
  // Viewport adaptado al rango con datos (alineado a bin): los bines siguen
  // siendo fijos globales (comparables), pero el eje X muestra desde el
  // primer bin con datos hasta el último (±1 de aire).
  let i0 = 0;
  let i1 = Math.max(0, nbins - 1);
  if (nbins > 0) {
    const has = (i: number) => series.some((s) => (s.counts[i] ?? 0) > 0);
    while (i0 < nbins - 1 && !has(i0)) i0 += 1;
    while (i1 > i0 && !has(i1)) i1 -= 1;
    i0 = Math.max(0, i0 - 1);
    i1 = Math.min(nbins - 1, i1 + 1);
  }
  const vn = nbins > 0 ? i1 - i0 + 1 : 0; // bines visibles
  const maxPct = series.reduce((m, s) => s.pcts.reduce((a, p) => Math.max(a, p), m), 0);
  const { ticks: yTicks, top: maxY } = niceTicks(maxPct);

  const iw = W - PAD.l - PAD.r;
  const ih = H - PAD.t - PAD.b;
  const midY = PAD.t + ih / 2; // eje central: Verde arriba, Muerta abajo
  const hh = ih / 2;
  const gw = vn > 0 ? iw / vn : iw; // ancho por bin visible
  const bw = Math.max(2, gw * 0.6);
  const X = (k: number) => PAD.l + k * gw + (gw - bw) / 2; // k = índice visible
  const Yv = (p: number) => midY - (p / maxY) * hh; // mitad superior (Verde)
  const Ym = (p: number) => midY + (p / maxY) * hh; // mitad inferior (Muerta)

  const xMin = edges.length > 0 ? edges[i0] : 0;
  const xMax = edges.length > 0 ? edges[i1 + 1] : 1;
  const xTicks = vn > 0
    ? [0, 0.25, 0.5, 0.75, 1].map((f) => ({ x: PAD.l + f * iw, v: xMin + f * (xMax - xMin) }))
    : [];

  const toggle = (id: SerieId) => setActivas((a) => ({ ...a, [id]: !a[id] }));

  const onMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const rect = (e.currentTarget as SVGSVGElement).getBoundingClientRect();
    const mx = (e.clientX - rect.left) * (W / rect.width);
    const k = Math.floor((mx - PAD.l) / gw);
    setHover(k >= 0 && k < vn ? k : null);
  };

  const fmtG = (v: number) => v.toLocaleString('es-AR', { maximumFractionDigits: 1 });
  const fmtP = (v: number) => `${v.toLocaleString('es-AR', { maximumFractionDigits: 1 })}%`;

  return (
    <div className="panel">
      <div className="serie-head">
        <div className="serie-left">
          <label>
            Fecha
            <select value={fecha} onChange={(e) => onFecha(e.target.value)} disabled={fechas.length === 0}>
              <option value="">— Elegir —</option>
              {fechas.map((f) => (
                <option key={f} value={f}>{fmtFechaCorta(f)}</option>
              ))}
            </select>
          </label>
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
            {LADOS.map((s) => (
              <button
                key={s.id}
                type="button"
                className={activas[s.id] ? 'on' : 'off'}
                onClick={() => toggle(s.id)}
                title="Mostrar/ocultar lado"
              >
                <span className="swatch" style={{ background: activas[s.id] ? colorDe(s.id) : pal.swatchOff }} />
                {s.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {loading && <span className="muted">Cargando histograma…</span>}
      {error && <p className="error-text">{error}</p>}
      {!loading && !error && (!finca || !fecha) && (
        <span className="muted">Elegí finca y fecha para ver la distribución.</span>
      )}
      {!loading && !error && finca && fecha && data?.sin_datos && (
        <span className="muted">Sin puntos para esa finca y fecha.</span>
      )}
      {!loading && !error && nbins > 0 && (
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="serie-svg"
          onMouseMove={onMove}
          onMouseLeave={() => setHover(null)}
          role="img"
          aria-label="Histograma comparado por intervalo"
        >
          <rect x={PAD.l} y={PAD.t} width={iw} height={ih} fill="none" stroke={ui.axisPrimary} strokeWidth={0.75} />
          <line x1={PAD.l} x2={W - PAD.r} y1={midY} y2={midY} stroke={ui.axisPrimary} strokeWidth={0.75} />
          {yTicks.map((t) => (
            <g key={t}>
              <line x1={PAD.l - 4} x2={PAD.l} y1={Yv(t)} y2={Yv(t)} stroke={ui.axisPrimary} strokeWidth={0.75} />
              <text x={PAD.l - 8} y={Yv(t) + 4} textAnchor="end" className="tick">{fmtP(t)}</text>
              {t > 0 && (
                <g>
                  <line x1={PAD.l - 4} x2={PAD.l} y1={Ym(t)} y2={Ym(t)} stroke={ui.axisPrimary} strokeWidth={0.75} />
                  <text x={PAD.l - 8} y={Ym(t) + 4} textAnchor="end" className="tick">{fmtP(t)}</text>
                </g>
              )}
            </g>
          ))}
          <text
            x={15} y={PAD.t + ih / 2} textAnchor="middle" className="axis-title"
            transform={`rotate(-90 15 ${PAD.t + ih / 2})`}
          >
            % de puntos
          </text>
          {xTicks.map((t, i) => (
            <g key={i}>
              <line x1={t.x} x2={t.x} y1={H - PAD.b} y2={H - PAD.b + 4} stroke={ui.axisPrimary} strokeWidth={0.75} />
              <text x={t.x} y={H - PAD.b + 18} textAnchor="middle" className="tick">{fmtG(t.v)}</text>
            </g>
          ))}
          <text x={(PAD.l + W - PAD.r) / 2} y={H - 4} textAnchor="middle" className="axis-title">
            Biomasa (t MS ha⁻¹)
          </text>
          {Array.from({ length: vn }, (_, k) => {
            const gi = i0 + k; // índice global del bin (bines fijos)
            return (
              <g key={gi}>
                {series.map((s) => {
                  const pct = s.pcts[gi] ?? 0;
                  const h = (pct / maxY) * hh;
                  const y = s.dir < 0 ? midY - h : midY;
                  return (
                  <g key={s.id}>
                    <rect
                        x={X(k)}
                        y={y}
                        width={bw}
                        height={Math.max(0, h)}
                        rx="2"
                        fill={s.color}
                        fillOpacity={hover === k ? 1 : 0.8}
                        stroke={hover === k ? ui.axisPrimary : 'none'}
                        strokeWidth={hover === k ? 1 : 0}
                      />
                    </g>
                  );
                })}
              </g>
            );
          })}
          {series.map((s) => {
            if (s.mean === null || xMax <= xMin) return null;
            const mx = PAD.l + ((s.mean - xMin) / (xMax - xMin)) * iw;
            const my = s.dir < 0 ? PAD.t + 4 : PAD.t + ih - 4;
            // Si el punto está pegado al borde derecho, la etiqueta va a la
            // izquierda para no chocar con la línea del margen.
            const aLaDerecha = mx + 8 + 36 < PAD.l + iw;
            return (
              <g key={`mean-${s.id}`}>
                <line x1={mx} x2={mx} y1={s.dir < 0 ? PAD.t : midY} y2={s.dir < 0 ? midY : PAD.t + ih} stroke={s.color} strokeDasharray="5 3" strokeWidth="1.5" />
                <circle cx={mx} cy={my} r={4} fill={s.color} />
                <text
                  x={aLaDerecha ? mx + 8 : mx - 8}
                  y={s.dir < 0 ? my + 8 : my - 2}
                  textAnchor={aLaDerecha ? 'start' : 'end'}
                  fontSize="10"
                  fontWeight="700"
                  fill={s.color}
                >
                  {fmtG(s.mean)}
                </text>
              </g>
            );
          })}
          {hover !== null && hover < vn && (() => {
            const gi = i0 + hover;
            return (
            <g transform={`translate(${Math.min(X(hover) + bw + 8, W - 150)},${PAD.t + 6})`}>
              <rect width="140" height={16 + series.length * 13} rx="6" fill={ui.mapHintBg} />
              <text x="7" y="13" fill={ui.mapHintTitle} fontSize="10" fontWeight="700">
                {fmtG(edges[gi])} – {fmtG(edges[gi + 1])} {unit}
              </text>
              {series.map((s, j) => (
                <text key={s.id} x="7" y={26 + j * 13} fill={ui.mapHintText} fontSize="10">
                    {LADOS.find((x) => x.id === s.id)?.label}: {fmtP(s.pcts[gi] ?? 0)}
                  </text>
                ))}
              </g>
            );
          })()}
        </svg>
      )}
    </div>
  );
}
