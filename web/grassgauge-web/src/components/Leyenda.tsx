import { useRef, useState } from 'react';
import { DENSIDAD_CEILING, paradasDegradado, tHaAPct } from '../lib/masaSeca';

// Leyenda de la capa de densidad (g/m²) con degradado suave, igual que el mapa:
// tramos sólidos por zona y fundido corto en cada corte.
// Panel flotante arrastrable desde su cabecera.

const STOPS = paradasDegradado();

const CEILING = DENSIDAD_CEILING;
const GRADIENT = `linear-gradient(to right, ${STOPS.map((s) => `${s.color} ${Math.round((s.v / CEILING) * 100)}%`).join(', ')})`;

/** Eje 0–4 con tick final ">5": cada etiqueta cae sobre su corte de banda. */
const TICKS_PCT = [0, 1, 2, 3, 4].map((tHa) => ({
  tHa,
  pct: tHaAPct(tHa),
}));

export default function Leyenda() {
  const ref = useRef<HTMLDivElement | null>(null);
  const drag = useRef<{ dx: number; dy: number } | null>(null);
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);
  const [moviendo, setMoviendo] = useState(false);

  const onPointerDown = (e: React.PointerEvent) => {
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    drag.current = { dx: e.clientX - r.left, dy: e.clientY - r.top };
    setMoviendo(true);
    (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
  };

  const onPointerMove = (e: React.PointerEvent) => {
    if (!drag.current || !ref.current) return;
    e.preventDefault();
    const wrap = ref.current.offsetParent as HTMLElement | null;
    const wr = wrap?.getBoundingClientRect();
    const ox = wr ? wr.left : 0;
    const oy = wr ? wr.top : 0;
    setPos({
      x: Math.max(0, e.clientX - ox - drag.current.dx),
      y: Math.max(0, e.clientY - oy - drag.current.dy),
    });
  };

  const onPointerUp = () => {
    drag.current = null;
    setMoviendo(false);
  };

  return (
    <div
      ref={ref}
      className="leyenda"
      style={pos ? { left: pos.x, top: pos.y } : undefined}
    >
      <strong
        className={`leyenda-handle ${moviendo ? 'moviendo' : ''}`}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        title="Arrastrar para mover"
      >
        Densidad (t MS/ha)
      </strong>
      <div className="leyenda-gradient" style={{ background: GRADIENT }} />
      <div className="leyenda-ticks" style={{ display: 'block', position: 'relative', height: 12 }}>
        {TICKS_PCT.map(({ tHa, pct }, i) => (
          <span
            key={tHa}
            style={{
              position: 'absolute',
              left: `${pct}%`,
              transform: i === 0 ? 'translateX(0)' : 'translateX(-50%)',
            }}
          >
            {tHa.toLocaleString('es-AR')}
          </span>
        ))}
        <span
          title="Mayor o igual a 5 t/ha"
          style={{
            position: 'absolute',
            left: '100%',
            transform: 'translateX(-100%)',
            whiteSpace: 'nowrap',
          }}
        >
          ≥5
        </span>
      </div>
    </div>
  );
}
