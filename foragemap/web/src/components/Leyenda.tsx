import { useRef, useState } from 'react';
import { DENSIDAD_CEILING, RAMPA_DENSIDAD } from '../lib/masaSeca';

// Leyenda de la capa de puntos de densidad (g/m²).
// Barra de gradiente continua que replica la rampa compartida (rojo→verde).
// Panel flotante arrastrable desde su cabecera.

const STOPS = RAMPA_DENSIDAD;

const CEILING = DENSIDAD_CEILING;
const GRADIENT = `linear-gradient(to right, ${STOPS.map((s) => `${s.color} ${Math.round((s.v / CEILING) * 100)}%`).join(', ')})`;

const TICKS = [0, 30, 60, 90, 120];

export default function Leyenda({ tipo, conDatos }: { tipo: string; conDatos?: boolean }) {
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
        Densidad (g/m²)
      </strong>
      <div className="leyenda-gradient" style={{ background: GRADIENT }} />
      <div className="leyenda-ticks">
        {TICKS.map((v) => (
          <span key={v}>{v}</span>
        ))}
      </div>
      <span className="muted small">Malla 10 m · {tipo}</span>
      {conDatos !== false && (
        <div className="muted small" style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 6 }}>
          <span className="swatch" style={{ background: '#111827', border: '1px dashed #e5e7eb' }} />
          Exclusión (sin forraje)
        </div>
      )}
    </div>
  );
}
