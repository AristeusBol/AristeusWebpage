from sqlalchemy import text
import pandas as pd

from repositorios import mapa_color, potreros


M2_POR_HA = 10000
G_POR_KG = 1000
# densidad en g/m2, area en m2 -> masa en kg


def calcular_stock_potrero(engine, potrero_id, usuario_id=None):
    with engine.connect() as conn:
        if usuario_id is not None:
            res = conn.execute(
                text("SELECT nombre, finca, ST_Area(geom::geography) AS area_m2, usuario_id FROM potreros_base WHERE id = :pid AND usuario_id = :uid"),
                {"pid": potrero_id, "uid": usuario_id},
            ).fetchone()
            if not res:
                return None
            nombre, finca, area_bruta_m2 = res.nombre, res.finca, float(res.area_m2) if res.area_m2 is not None else 0.0
        else:
            res = conn.execute(
                text("SELECT nombre, finca, ST_Area(geom::geography) AS area_m2, usuario_id FROM potreros_base WHERE id = :pid"),
                {"pid": potrero_id},
            ).fetchone()
            if not res:
                return None
            nombre, finca, area_bruta_m2 = res.nombre, res.finca, float(res.area_m2) if res.area_m2 is not None else 0.0
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

        # evita area negativa si las exclusiones vienen desalineadas
        area_neta_m2 = max(0.0, area_bruta_m2 - area_exclusion_m2)
        area_neta_ha = max(0.0, area_bruta_ha - area_exclusion_ha)


        df_puntos = pd.read_sql(
            text("""
                SELECT fecha, densidad_verde_g_m2, densidad_muerta_g_m2, densidad_total_g_m2
                FROM mapa_color m
                WHERE m.potrero_id = :pid AND m.usuario_id = :uid
                  AND ST_Within(m.geom, (SELECT geom FROM potreros_base WHERE id = :pid AND usuario_id = :uid))
                  AND m.fecha = (
                      SELECT MAX(fecha) FROM mapa_color
                      WHERE potrero_id = :pid AND usuario_id = :uid
                        AND ST_Within(geom, (SELECT geom FROM potreros_base WHERE id = :pid AND usuario_id = :uid))
                  )
            """),
            conn,
            params={"pid": potrero_id, "uid": usuario_id},
        )


        # compatibilidad con datos antiguos sin interseccion espacial
        if df_puntos.empty:
            df_puntos = pd.read_sql(
                text("""
                    SELECT fecha, densidad_verde_g_m2, densidad_muerta_g_m2, densidad_total_g_m2
                    FROM mapa_color
                    WHERE potrero_id = :pid AND usuario_id = :uid
                      AND fecha = (SELECT MAX(fecha) FROM mapa_color WHERE potrero_id = :pid AND usuario_id = :uid)
                """),
                conn,
                params={"pid": potrero_id, "uid": usuario_id},
            )
            if df_puntos.empty:
                return None


    densidad_promedio_verde_g_m2 = float(df_puntos["densidad_verde_g_m2"].mean())
    densidad_promedio_muerta_g_m2 = float(df_puntos["densidad_muerta_g_m2"].mean())
    densidad_promedio_total_g_m2 = float(df_puntos["densidad_total_g_m2"].mean())


    suma = densidad_promedio_verde_g_m2 + densidad_promedio_muerta_g_m2
    if densidad_promedio_total_g_m2 and suma:
        if abs(densidad_promedio_total_g_m2 - suma) / max(suma, 1) > 0.05:
            pass


    masa_total_potrero_verde_kg = densidad_promedio_verde_g_m2 * area_neta_m2 / G_POR_KG
    masa_total_potrero_muerta_kg = densidad_promedio_muerta_g_m2 * area_neta_m2 / G_POR_KG
    masa_total_potrero_total_kg = densidad_promedio_total_g_m2 * area_neta_m2 / G_POR_KG

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
        "densidad_promedio_verde_g_m2": densidad_promedio_verde_g_m2,
        "densidad_promedio_muerta_g_m2": densidad_promedio_muerta_g_m2,
        "densidad_promedio_total_g_m2": densidad_promedio_total_g_m2,
        "masa_total_potrero_verde_kg": masa_total_potrero_verde_kg,
        "masa_total_potrero_muerta_kg": masa_total_potrero_muerta_kg,
        "masa_total_potrero_total_kg": masa_total_potrero_total_kg,
        "masa_seca_verde": masa_total_potrero_verde_kg,
        "masa_seca_muerta": masa_total_potrero_muerta_kg,
        "masa_seca_total": masa_total_potrero_total_kg,
    }
