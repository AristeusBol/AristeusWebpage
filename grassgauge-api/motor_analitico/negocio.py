from sqlalchemy import text
import math
import pandas as pd

from dominio.constantes import G_POR_KG, M2_POR_HA
from repositorios.sql import EXCLUIR_PUNTOS_PID


def calcular_stock_potrero(engine, potrero_id, usuario_id=None, fecha=None):
    with engine.connect() as conn:
        sql = "SELECT nombre, finca, ST_Area(geom::geography) AS area_m2, usuario_id FROM potreros_base WHERE id = :pid"
        params: dict = {"pid": potrero_id}
        if usuario_id is not None:
            sql += " AND usuario_id = :uid"
            params["uid"] = usuario_id
        res = conn.execute(text(sql), params).fetchone()
        if not res:
            return None
        nombre, finca = res.nombre, res.finca
        area_bruta_m2 = float(res.area_m2) if res.area_m2 is not None else 0.0
        usuario_id = res.usuario_id

        area_bruta_ha = area_bruta_m2 / M2_POR_HA

        res_ex = conn.execute(
            text("""
                SELECT COALESCE(
                    ST_Area(
                        ST_Intersection(
                            p.geom,
                            COALESCE(u.geom_union, ST_GeomFromText('GEOMETRYCOLLECTION EMPTY', 4326))
                        )::geography
                    ), 0
                ) AS area_exclusion_m2
                FROM potreros_base p
                LEFT JOIN (
                    SELECT ST_Union(geom) AS geom_union
                    FROM zonas_exclusion
                    WHERE potrero_id = :pid AND usuario_id = :uid
                ) u ON true
                WHERE p.id = :pid AND p.usuario_id = :uid
            """),
            {"pid": potrero_id, "uid": usuario_id},
        ).fetchone()
        area_exclusion_m2 = float(res_ex.area_exclusion_m2) if res_ex and res_ex.area_exclusion_m2 is not None else 0.0
        area_exclusion_ha = area_exclusion_m2 / M2_POR_HA

        area_neta_m2 = max(0.0, area_bruta_m2 - area_exclusion_m2)
        area_neta_ha = max(0.0, area_bruta_ha - area_exclusion_ha)

        # Fecha objetivo: explícita o la más reciente con datos dentro del potrero.
        fecha_obj = fecha
        if fecha_obj is None:
            res_fecha = conn.execute(
                text("""
                    SELECT MAX(fecha) AS f FROM mapa_color
                    WHERE potrero_id = :pid AND usuario_id = :uid
                      AND ST_Covers((SELECT geom FROM potreros_base WHERE id = :pid AND usuario_id = :uid), geom)
                """),
                {"pid": potrero_id, "uid": usuario_id},
            ).fetchone()
            fecha_obj = res_fecha.f if res_fecha else None
        if fecha_obj is None:
            return None

        df_puntos = pd.read_sql(
            text(f"""
                SELECT fecha, densidad_verde_g_m2, densidad_muerta_g_m2, densidad_total_g_m2
                FROM mapa_color m
                WHERE m.potrero_id = :pid AND m.usuario_id = :uid
                  AND ST_Covers((SELECT geom FROM potreros_base WHERE id = :pid AND usuario_id = :uid), m.geom)
                  AND {EXCLUIR_PUNTOS_PID}
                  AND m.fecha = :fecha
            """),
            conn,
            params={"pid": potrero_id, "uid": usuario_id, "fecha": fecha_obj},
        )

        if df_puntos.empty:
            return None

    for col in ("densidad_verde_g_m2", "densidad_muerta_g_m2", "densidad_total_g_m2"):
        serie = df_puntos[col].dropna()
        if serie.empty:
            return None
    verde_mean = float(df_puntos["densidad_verde_g_m2"].dropna().mean())
    muerta_mean = float(df_puntos["densidad_muerta_g_m2"].dropna().mean())
    total_mean = float(df_puntos["densidad_total_g_m2"].dropna().mean())
    if any(math.isnan(v) or math.isinf(v) for v in (verde_mean, muerta_mean, total_mean)):
        return None
    masa_total_potrero_verde_kg = verde_mean * area_neta_m2 / G_POR_KG
    masa_total_potrero_muerta_kg = muerta_mean * area_neta_m2 / G_POR_KG
    masa_total_potrero_total_kg = total_mean * area_neta_m2 / G_POR_KG
    if any(not math.isfinite(v) for v in (
        masa_total_potrero_verde_kg, masa_total_potrero_muerta_kg, masa_total_potrero_total_kg,
    )):
        return None

    return {
        "nombre": nombre,
        "finca": finca,
        "fecha": df_puntos["fecha"].iloc[0],
        "usuario_id": usuario_id,
        "area_bruta_m2": float(area_bruta_m2),
        "area_bruta_ha": float(area_bruta_ha),
        "area_exclusion_m2": float(area_exclusion_m2),
        "area_exclusion_ha": float(area_exclusion_ha),
        "area_neta_ha": float(area_neta_ha),
        "area_neta_m2": float(area_neta_m2),
        "densidad_promedio_verde_g_m2": verde_mean,
        "densidad_promedio_muerta_g_m2": muerta_mean,
        "densidad_promedio_total_g_m2": total_mean,
        "masa_total_potrero_verde_kg": masa_total_potrero_verde_kg,
        "masa_total_potrero_muerta_kg": masa_total_potrero_muerta_kg,
        "masa_total_potrero_total_kg": masa_total_potrero_total_kg,
        "masa_seca_verde": masa_total_potrero_verde_kg,
        "masa_seca_muerta": masa_total_potrero_muerta_kg,
        "masa_seca_total": masa_total_potrero_total_kg,
    }
