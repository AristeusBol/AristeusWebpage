"""Histograma de densidades del mapa (bordes comunes verde/muerta/total)."""

from datetime import date
import json
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import text

from core.db import engine
from repositorios.sql import EXCLUIR_PUNTOS_M
from servicios.mapa_tiles import COL_DENSIDAD


def _params(uid: int, finca: str, fecha: date, gj_text: Optional[str], potrero_id: Optional[int]) -> dict:
    p = {"uid": uid, "finca": finca, "fecha": fecha, "gj": gj_text or ""}
    if potrero_id is not None:
        p["pid"] = potrero_id
    return p


def _serie(v: dict, n_s: int, factor: float, conteos: list, pcts: list) -> dict:
    return {
        "min": v["vmin"] * factor if v["vmin"] is not None else None,
        "max": v["vmax"] * factor if v["vmax"] is not None else None,
        "mean": v["vmean"] * factor if v["vmean"] is not None else None,
        "count": n_s,
        "counts": conteos,
        "pcts": pcts,
    }


def generar_histograma(
    finca: str,
    fecha: date,
    bins: int,
    potrero_id: Optional[int],
    parcela_id: Optional[int],
    usuario_id_resuelto: int,
) -> dict:
    """Arma la distribución comparada verde/muerta/total sobre bines comunes."""
    finca_norm = finca.strip()
    if not finca_norm:
        raise HTTPException(status_code=400, detail="estancia requerida")

    # Parcela: resuelve potrero padre + geometría (la parcela está contenida
    # en su potrero, así que se filtra por potrero_id y se recorta espacialmente).
    # Si también vino potrero_id debe coincidir con el padre (si no, 400).
    gj_text: Optional[str] = None
    if parcela_id is not None:
        with engine.connect() as conn:
            pa = conn.execute(
                text("""
                    SELECT pa.potrero_id AS potrero_id,
                           ST_AsGeoJSON(pa.geom)::json AS geom_json
                    FROM parcelas pa
                    JOIN potreros_base pb ON pb.id = pa.potrero_id AND pb.usuario_id = pa.usuario_id
                    WHERE pa.id = :parc AND pa.usuario_id = :uid AND pb.finca = :finca
                """),
                {"parc": parcela_id, "uid": usuario_id_resuelto, "finca": finca_norm},
            ).fetchone()
        if not pa:
            raise HTTPException(status_code=404, detail=f"Parcela {parcela_id} no existe o no es tuya")
        if potrero_id is not None and int(pa.potrero_id) != potrero_id:
            raise HTTPException(status_code=400, detail=f"La parcela {parcela_id} no pertenece al potrero {potrero_id}")
        potrero_id = int(pa.potrero_id)
        gj_text = json.dumps(pa.geom_json)
    recorte_parcela = " AND ST_Covers(ST_SetSRID(ST_GeomFromGeoJSON(:gj), 4326), m.geom)" if gj_text else ""

    if potrero_id is not None and parcela_id is None:
        with engine.connect() as conn:
            dueno = conn.execute(
                text("SELECT 1 FROM potreros_base WHERE id = :pid AND usuario_id = :uid AND finca = :finca"),
                {"pid": potrero_id, "uid": usuario_id_resuelto, "finca": finca_norm},
            ).fetchone()
        if not dueno:
            raise HTTPException(status_code=404, detail=f"Potrero {potrero_id} no existe o no es tuyo")

    # Filtro por potrero como fragmento condicional (mismo estilo que
    # recorte_parcela). Evita `(:pid IS NULL OR ... = :pid)`: con psycopg3 un
    # parámetro None no tiene tipo inferible y Postgres rechaza la consulta
    # con AmbiguousParameter ("could not determine data type of parameter").
    filtro_potrero_base = " AND p.id = :pid" if potrero_id is not None else ""
    filtro_potrero_mapa = " AND potrero_id = :pid" if potrero_id is not None else ""

    # Área neta (bruta menos exclusiones) de la estancia, del potrero o de
    # la parcela: el factor kg/punto debe repartir el área productiva, no la
    # bruta. Antes se usaba el área bruta, sobreestimando los kg cuando hay
    # zonas de exclusión.
    if gj_text:
        area_sql = text("""
            SELECT ST_Area(
                COALESCE(
                    ST_Difference(
                        ST_SetSRID(ST_GeomFromGeoJSON(:gj), 4326),
                        (SELECT ST_Union(z.geom) FROM zonas_exclusion z
                         WHERE z.usuario_id = :uid AND z.potrero_id = :pid)
                    ),
                    ST_SetSRID(ST_GeomFromGeoJSON(:gj), 4326)
                )::geography) AS area_m2
        """)
        area_params = {"uid": usuario_id_resuelto, "pid": potrero_id, "gj": gj_text}
    else:
        area_sql = text(f"""
        SELECT COALESCE(SUM(ST_Area(p.geom::geography)), 0)
              - COALESCE(SUM(ST_Area(ST_Intersection(
                     p.geom,
                     COALESCE(u.geom_union, ST_GeomFromText('GEOMETRYCOLLECTION EMPTY', 4326))
                   )::geography)), 0) AS area_m2
        FROM potreros_base p
        LEFT JOIN (
            SELECT potrero_id, ST_Union(geom) AS geom_union
            FROM zonas_exclusion
            WHERE usuario_id = :uid
            GROUP BY potrero_id
        ) u ON u.potrero_id = p.id
        WHERE p.usuario_id = :uid AND p.finca = :finca{filtro_potrero_base}
    """)
        area_params = {"uid": usuario_id_resuelto, "finca": finca_norm}
        if potrero_id is not None:
            area_params["pid"] = potrero_id
    with engine.connect() as conn:
        area_row = conn.execute(area_sql, area_params).fetchone()
    area_m2 = float(area_row[0]) if area_row and area_row[0] else 0.0

    stats_sql = text(f"""
        SELECT COUNT(*) AS n,
               COUNT(densidad_verde_g_m2) AS n_verde,
               MIN(densidad_verde_g_m2) AS vmin_verde,
               MAX(densidad_verde_g_m2) AS vmax_verde,
               AVG(densidad_verde_g_m2) AS vmean_verde,
               COUNT(densidad_muerta_g_m2) AS n_muerta,
               MIN(densidad_muerta_g_m2) AS vmin_muerta,
               MAX(densidad_muerta_g_m2) AS vmax_muerta,
               AVG(densidad_muerta_g_m2) AS vmean_muerta,
               COUNT(densidad_total_g_m2) AS n_total,
               MIN(densidad_total_g_m2) AS vmin_total,
               MAX(densidad_total_g_m2) AS vmax_total,
               AVG(densidad_total_g_m2) AS vmean_total
        FROM mapa_color m
        WHERE usuario_id = :uid
          AND finca = :finca
          AND fecha = :fecha{filtro_potrero_mapa}{recorte_parcela}
          AND {EXCLUIR_PUNTOS_M}
    """)
    stats_params = _params(usuario_id_resuelto, finca_norm, fecha, gj_text, potrero_id)
    with engine.connect() as conn:
        stats = conn.execute(stats_sql, stats_params).fetchone()

    filtros = {
        "finca": finca_norm,
        "fecha": fecha.isoformat(),
        "bins": bins,
        "potrero_id": potrero_id,
        "parcela_id": parcela_id,
        "usuario_id": usuario_id_resuelto,
        "area_ha": round(area_m2 / 10000.0, 2),
    }
    per = {}
    for t in ("verde", "muerta", "total"):
        vmin = getattr(stats, f"vmin_{t}", None)
        vmax = getattr(stats, f"vmax_{t}", None)
        vmean = getattr(stats, f"vmean_{t}", None)
        per[t] = {
            "count": int(getattr(stats, f"n_{t}", 0) or 0),
            "vmin": float(vmin) if vmin is not None else None,
            "vmax": float(vmax) if vmax is not None else None,
            "vmean": float(vmean) if vmean is not None else None,
        }
    count = int(stats.n or 0)
    validos = {t: v for t, v in per.items() if v["vmin"] is not None and v["vmax"] is not None and v["count"] > 0}
    if count == 0 or area_m2 <= 0 or not validos:
        return {
            "filtros": filtros,
            "stats": {"count": 0},
            "edges": [],
            "series": {t: {"min": None, "max": None, "mean": None, "count": 0, "counts": [], "pcts": []} for t in ("verde", "muerta", "total")},
            "sin_datos": True,
        }

    # Bordes fijos por estancia: mínimo/máximo global de todas las fechas y
    # lotes (misma exclusión), para comparar histogramas entre sí.
    global_sql = text(f"""
        SELECT MIN(densidad_verde_g_m2) AS gmin_verde,
               MAX(densidad_verde_g_m2) AS gmax_verde,
               MIN(densidad_muerta_g_m2) AS gmin_muerta,
               MAX(densidad_muerta_g_m2) AS gmax_muerta,
               MIN(densidad_total_g_m2) AS gmin_total,
               MAX(densidad_total_g_m2) AS gmax_total
        FROM mapa_color m
        WHERE usuario_id = :uid
          AND finca = :finca
          AND {EXCLUIR_PUNTOS_M}
    """)
    with engine.connect() as conn:
        grow = conn.execute(global_sql, {"uid": usuario_id_resuelto, "finca": finca_norm}).fetchone()
    gmin = min(float(v) for t in ("verde", "muerta", "total") if (v := getattr(grow, f"gmin_{t}", None)) is not None)
    gmax = max(float(v) for t in ("verde", "muerta", "total") if (v := getattr(grow, f"gmax_{t}", None)) is not None)
    factor = (area_m2 / count) / 1000.0

    def buckets_de(columna: str):
        q = text(f"""
            SELECT WIDTH_BUCKET({columna}, :vmin, :vmax, :bins) AS bucket, COUNT(*) AS c
            FROM mapa_color m
            WHERE usuario_id = :uid
              AND finca = :finca
              AND fecha = :fecha{filtro_potrero_mapa}{recorte_parcela}
              AND {columna} IS NOT NULL
              AND {EXCLUIR_PUNTOS_M}
            GROUP BY bucket
        """)
        with engine.connect() as conn:
            return conn.execute(q, {**stats_params, "vmin": gmin, "vmax": gmax, "bins": bins}).fetchall()

    def plegar(filas):
        conteos = [0] * bins
        for r in filas:
            idx = int(r.bucket) - 1
            if 0 <= idx < bins:
                conteos[idx] = int(r.c)
            elif int(r.bucket) > bins:
                conteos[bins - 1] += int(r.c)
            elif int(r.bucket) < 1:
                conteos[0] += int(r.c)
        return conteos

    series = {}
    if gmax <= gmin:
        edges = [round(gmin * factor, 2), round(gmax * factor, 2)]
        for t in ("verde", "muerta", "total"):
            v = per[t]
            n_s = v["count"]
            series[t] = _serie(v, n_s, factor, [n_s], [100.0])
    else:
        edges = [round((gmin + i * (gmax - gmin) / bins) * factor, 2) for i in range(bins + 1)]
        for t, columna in COL_DENSIDAD.items():
            v = per[t]
            n_s = v["count"]
            conteos = plegar(buckets_de(columna)) if n_s > 0 else [0] * bins
            series[t] = _serie(
                v, n_s, factor, conteos,
                [round(c / n_s * 100.0, 1) if n_s > 0 else 0.0 for c in conteos],
            )

    return {
        "filtros": filtros,
        "stats": {"count": count},
        "edges": edges,
        "series": series,
        "sin_datos": False,
    }
