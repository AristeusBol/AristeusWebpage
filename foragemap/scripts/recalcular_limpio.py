"""Recalcula calculos_stock por (potrero, fecha) excluyendo puntos en zonas de exclusión.

Replica motor_analitico/negocio.calcular_stock_potrero pero por fecha explícita
y con filtro NOT EXISTS contra zonas_exclusion (ST_Covers = borde dentro).
Uso: .venv/bin/python scripts/recalcular_limpio.py [--aplicar]
Sin --aplicar solo muestra el diff (dry-run).
"""
import argparse
import math

import pandas as pd
from sqlalchemy import text

from core.db import engine
from repositorios import calculos

M2_POR_HA = 10000
G_POR_KG = 1000


def recalcular(potrero_id, usuario_id, fecha_iso, conn, aplicar):
    pot = conn.execute(
        text("""SELECT nombre, finca, ST_Area(geom::geography) AS area_m2
                FROM potreros_base WHERE id=:pid AND usuario_id=:uid"""),
        {"pid": potrero_id, "uid": usuario_id},
    ).fetchone()
    if not pot:
        return None
    area_bruta_m2 = float(pot.area_m2)
    area_exc = conn.execute(
        text("""SELECT COALESCE(ST_Area(ST_Intersection(p.geom,
            COALESCE(u.geom_union, ST_GeomFromText('GEOMETRYCOLLECTION EMPTY', 4326)))::geography),0) AS m2
            FROM potreros_base p LEFT JOIN (
              SELECT ST_Union(geom) AS geom_union FROM zonas_exclusion
              WHERE potrero_id=:pid AND usuario_id=:uid) u ON true
            WHERE p.id=:pid AND p.usuario_id=:uid"""),
        {"pid": potrero_id, "uid": usuario_id},
    ).fetchone()
    area_exc_m2 = float(area_exc.m2 or 0.0)
    area_neta_m2 = max(0.0, area_bruta_m2 - area_exc_m2)
    area_neta_ha = area_neta_m2 / M2_POR_HA

    df = pd.read_sql(
        text("""SELECT densidad_verde_g_m2, densidad_muerta_g_m2, densidad_total_g_m2
                FROM mapa_color m
                WHERE m.potrero_id=:pid AND m.usuario_id=:uid AND m.fecha=:fecha
                  AND ST_Covers((SELECT geom FROM potreros_base WHERE id=:pid AND usuario_id=:uid), m.geom)
                  AND NOT EXISTS (SELECT 1 FROM zonas_exclusion z
                    WHERE z.potrero_id=:pid AND z.usuario_id=:uid AND ST_Covers(z.geom, m.geom))"""),
        conn,
        params={"pid": potrero_id, "uid": usuario_id, "fecha": fecha_iso},
    )
    if df.empty:
        return None
    for col in ("densidad_verde_g_m2", "densidad_muerta_g_m2", "densidad_total_g_m2"):
        if df[col].dropna().empty:
            return None
    v = float(df["densidad_verde_g_m2"].dropna().mean())
    mu = float(df["densidad_muerta_g_m2"].dropna().mean())
    t = float(df["densidad_total_g_m2"].dropna().mean())
    if any(math.isnan(x) or math.isinf(x) for x in (v, mu, t)):
        return None
    nuevo = {
        "area_neta_ha": area_neta_ha,
        "verde": v * area_neta_m2 / G_POR_KG,
        "muerta": mu * area_neta_m2 / G_POR_KG,
        "total": t * area_neta_m2 / G_POR_KG,
        "n": len(df),
    }
    viejo = conn.execute(
        text("""SELECT area_neta_ha, masa_seca_verde, masa_seca_muerta, masa_seca_total
                FROM calculos_stock WHERE usuario_id=:uid AND potrero_id=:pid AND fecha=:fecha"""),
        {"uid": usuario_id, "pid": potrero_id, "fecha": fecha_iso},
    ).fetchone()
    if aplicar:
        calculos.upsert_calculo(
            conn, potrero_id, pot.finca, fecha_iso,
            nuevo["area_neta_ha"], nuevo["verde"], nuevo["muerta"], nuevo["total"],
            usuario_id=usuario_id,
        )
    return {"potrero": potrero_id, "fecha": fecha_iso, "n": nuevo["n"],
            "viejo_total": float(viejo.masa_seca_total) if viejo else None,
            "nuevo_total": nuevo["total"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()
    with engine.begin() if args.aplicar else engine.connect() as conn:
        pares = conn.execute(
            text("""SELECT DISTINCT m.potrero_id, m.usuario_id FROM mapa_color m
                    JOIN zonas_exclusion z ON z.usuario_id=m.usuario_id AND z.potrero_id=m.potrero_id
                    ORDER BY 1""")
        ).fetchall()
        # incluir potreros con exclusión aunque ya no tengan puntos dentro
        pares = conn.execute(
            text("SELECT potrero_id, usuario_id FROM zonas_exclusion ORDER BY 1")
        ).fetchall()
        for potrero_id, usuario_id in pares:
            fechas = conn.execute(
                text("""SELECT DISTINCT fecha FROM mapa_color
                        WHERE potrero_id=:pid AND usuario_id=:uid ORDER BY fecha"""),
                {"pid": potrero_id, "uid": usuario_id},
            ).fetchall()
            for (f,) in fechas:
                r = recalcular(potrero_id, usuario_id, f.isoformat(), conn, args.aplicar)
                if r:
                    print(f"potrero {r['potrero']} {r['fecha']}: n={r['n']} "
                          f"total {r['viejo_total']} -> {r['nuevo_total']:.1f} "
                          f"{'[APLICADO]' if args.aplicar else '[dry-run]'}")
    print("OK" + (" (aplicado)" if args.aplicar else " (dry-run, usar --aplicar)"))


if __name__ == "__main__":
    main()
