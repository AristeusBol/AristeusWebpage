import pandas as pd
from sqlalchemy import text

_FECHA_RECIENTE = text("""
    SELECT MAX(fecha) FROM mapa_color WHERE potrero_id = :pid AND usuario_id = :uid
""")


def puntos_por_fecha_geojson(conn, potrero_id, fecha, usuario_id=None):
    if usuario_id is not None:
        query = text("""
            SELECT id, finca, fecha, densidad_verde_g_m2, densidad_muerta_g_m2,
                   densidad_total_g_m2, origen, ST_AsGeoJSON(geom)::json AS geom_json
            FROM mapa_color
            WHERE potrero_id = :pid AND fecha = :fecha AND usuario_id = :uid
        """)
        params = {"pid": potrero_id, "fecha": fecha, "uid": usuario_id}
    else:
        query = text("""
            SELECT id, finca, fecha, densidad_verde_g_m2, densidad_muerta_g_m2,
                   densidad_total_g_m2, origen, ST_AsGeoJSON(geom)::json AS geom_json
            FROM mapa_color
            WHERE potrero_id = :pid AND fecha = :fecha
        """)
        params = {"pid": potrero_id, "fecha": fecha}
    res = conn.execute(query, params).fetchall()

    features = [{
        "type": "Feature",
        "geometry": row.geom_json,
        "properties": {
            "id": row.id,
            "finca": row.finca,
            "fecha": row.fecha.isoformat(),
            "densidad_verde_g_m2": float(row.densidad_verde_g_m2) if row.densidad_verde_g_m2 is not None else None,
            "densidad_muerta_g_m2": float(row.densidad_muerta_g_m2) if row.densidad_muerta_g_m2 is not None else None,
            "densidad_total_g_m2": float(row.densidad_total_g_m2) if row.densidad_total_g_m2 is not None else None,
            "origen": row.origen,
        },
    } for row in res]

    return {
        "type": "FeatureCollection",
        "features": features,
    }


def puntos_recientes_geojson(conn, potrero_id, usuario_id=None):
    if usuario_id is not None:
        query = text("""
            SELECT fecha FROM mapa_color WHERE potrero_id = :pid AND usuario_id = :uid ORDER BY fecha DESC LIMIT 1
        """)
        res = conn.execute(query, {"pid": potrero_id, "uid": usuario_id}).fetchone()
        if not res:
            return {"type": "FeatureCollection", "features": []}
        return puntos_por_fecha_geojson(conn, potrero_id, res.fecha, usuario_id)
    else:
        query = text("""
            SELECT fecha FROM mapa_color WHERE potrero_id = :pid ORDER BY fecha DESC LIMIT 1
        """)
        res = conn.execute(query, {"pid": potrero_id}).fetchone()
        if not res:
            return {"type": "FeatureCollection", "features": []}
        return puntos_por_fecha_geojson(conn, potrero_id, res.fecha)


def fechas_mapa_color(conn, potrero_id, usuario_id=None):
    if usuario_id is not None:
        query = text("""
            SELECT DISTINCT fecha FROM mapa_color WHERE potrero_id = :pid AND usuario_id = :uid ORDER BY fecha
        """)
        res = conn.execute(query, {"pid": potrero_id, "uid": usuario_id}).fetchall()
    else:
        query = text("""
            SELECT DISTINCT fecha FROM mapa_color WHERE potrero_id = :pid ORDER BY fecha
        """)
        res = conn.execute(query, {"pid": potrero_id}).fetchall()
    return [row.fecha.isoformat() for row in res]


def densidades_recientes(engine, potrero_id, usuario_id=None):
    if usuario_id is not None:
        query = text("""
            SELECT fecha, densidad_verde_g_m2, densidad_muerta_g_m2, densidad_total_g_m2
            FROM mapa_color
            WHERE potrero_id = :pid AND usuario_id = :uid
              AND fecha = (SELECT MAX(fecha) FROM mapa_color WHERE potrero_id = :pid AND usuario_id = :uid)
        """)
        params = {"pid": potrero_id, "uid": usuario_id}
    else:
        query = text("""
            SELECT fecha, densidad_verde_g_m2, densidad_muerta_g_m2, densidad_total_g_m2
            FROM mapa_color
            WHERE potrero_id = :pid
              AND fecha = (SELECT MAX(fecha) FROM mapa_color WHERE potrero_id = :pid)
        """)
        params = {"pid": potrero_id}
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params=params)
    return df
