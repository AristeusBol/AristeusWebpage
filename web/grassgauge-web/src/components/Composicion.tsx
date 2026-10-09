import { useMemo } from 'react';
import type { PotreroProps } from '../lib/api';

interface Props {
  /** Lote seleccionado; si es null se agregan todos los lotes. */
  lote: PotreroProps | null;
  lotes: PotreroProps[];
}

/** Composición de Masa Seca en tira horizontal compacta. */
export default function Composicion({ lote, lotes }: Props) {
  const comp = useMemo(() => {
    const base = lote ? [lote] : lotes;
    let area = 0, verdeKg = 0, muertaKg = 0, totalKg = 0;
    for (const l of base) {
      const ha = l.area_neta_ha ?? 0;
      if (!ha || ha <= 0) continue;
      area += ha;
      verdeKg += l.masa_verde_kg ?? 0;
      muertaKg += l.masa_muerta_kg ?? 0;
      totalKg += l.masa_total_kg ?? 0;
    }
    if (area <= 0 || totalKg <= 0) return null;
    const t = (kg: number) => (kg / 1000 / area);
    return {
      area,
      verde: t(verdeKg),
      muerta: t(muertaKg),
      total: t(totalKg),
      pctVerde: (verdeKg / totalKg) * 100,
      pctMuerta: (muertaKg / totalKg) * 100,
    };
  }, [lote, lotes]);

  const titulo = lote ? lote.nombre : 'Estancia';
  const fmt1 = (v: number) => v.toLocaleString('es-AR', { maximumFractionDigits: 1 });
  const fmt0 = (v: number) => v.toLocaleString('es-AR', { maximumFractionDigits: 0 });
  const fmt2 = (v: number) => v.toLocaleString('es-AR', { maximumFractionDigits: 2 });

  const colVerde: React.CSSProperties = { color: 'var(--densidad-verde)' };
  const colMuerta: React.CSSProperties = { color: 'var(--densidad-muerta)' };
  const colTotal: React.CSSProperties = { color: 'var(--densidad-total)' };

  return (
    <div className="comp-strip">
      <strong className="comp-strip-title">{titulo} <span className="comp-arrow">→</span></strong>
      {!comp ? (
        <span className="muted">Sin cálculos para esta fecha.</span>
      ) : (
        <div className="comp-strip-vals">
          <span><em>Área:</em> {fmt2(comp.area)} ha</span>
          <span className="sep">·</span>
          <span><em>Verde:</em> <span style={colVerde}>{fmt1(comp.verde)} t/ha</span> <small>({fmt0(comp.pctVerde)}%)</small></span>
          <span className="sep">·</span>
          <span><em>Muerta:</em> <span style={colMuerta}>{fmt1(comp.muerta)} t/ha</span> <small>({fmt0(comp.pctMuerta)}%)</small></span>
          <span className="sep">·</span>
          <span><em>Total:</em> <span style={colTotal}>{fmt1(comp.total)} t/ha</span></span>
        </div>
      )}
    </div>
  );
}
