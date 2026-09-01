import geopandas as gpd
from sqlalchemy import text


def listar_potreros(conn, usuario_id):
    query = text("""
        SELECT id, nombre, finca, ST_AsGeoJSON(geom)::json AS geom_json
        FROM potreros_base
        WHERE usuario_id = :uid
        ORDER BY id
    """)
    return conn.execute(query, {"uid": usuario_id}).fetchall()


def listar_potreros_todos(conn):
    query = text("""
        SELECT id, nombre, finca, ST_AsGeoJSON(geom)::json AS geom_json
        FROM potreros_base
        ORDER BY id
    """)
    return conn.execute(query).fetchall()


def potrero_y_exclusiones_geojson(conn, potrero_id, usuario_id):
    query_potrero = text("""
        SELECT id, nombre, finca, ST_AsGeoJSON(geom)::json AS geom_json
        FROM potreros_base
        WHERE id = :pid AND usuario_id = :uid
    """)
    res_potrero = conn.execute(query_potrero, {"pid": potrero_id, "uid": usuario_id}).fetchone()
    if not res_potrero:
        return None

    query_exclusiones = text("""
        SELECT id, nombre, tipo, finca, ST_AsGeoJSON(geom)::json AS geom_json
        FROM zonas_exclusion
        WHERE potrero_id = :pid AND usuario_id = :uid
    """)
    res_exclusiones = conn.execute(query_exclusiones, {"pid": potrero_id, "uid": usuario_id}).fetchall()

    features = [{
        "type": "Feature",
        "geometry": res_potrero.geom_json,
        "properties": {
            "id": res_potrero.id,
            "tipo": "potrero_base",
            "nombre": res_potrero.nombre,
            "finca": res_potrero.finca,
        },
    }]
    for exc in res_exclusiones:
        features.append({
            "type": "Feature",
            "geometry": exc.geom_json,
            "properties": {
                "id": exc.id,
                "tipo": "exclusion",
                "nombre": exc.nombre,
                "subtipo": exc.tipo,
                "finca": exc.finca,
            },
        })

    return {
        "type": "FeatureCollection",
        "features": features,
    }


def exclusiones_geojson(conn, potrero_id, usuario_id):
    query_exclusiones = text("""
        SELECT id, nombre, tipo, finca, ST_AsGeoJSON(geom)::json AS geom_json
        FROM zonas_exclusion
        WHERE potrero_id = :pid AND usuario_id = :uid
    """)
    res_exclusiones = conn.execute(query_exclusiones, {"pid": potrero_id, "uid": usuario_id}).fetchall()

    features = [{
        "type": "Feature",
        "geometry": exc.geom_json,
        "properties": {
            "id": exc.id,
            "tipo": "exclusion",
            "nombre": exc.nombre,
            "subtipo": exc.tipo,
            "finca": exc.finca,
        },
    } for exc in res_exclusiones]

    return {
        "type": "FeatureCollection",
        "features": features,
    }


def geometria_potrero(engine, potrero_id, usuario_id=None):
    if usuario_id is not None:
        query = text("""
            SELECT nombre, finca, geom FROM potreros_base WHERE id = :pid AND usuario_id = :uid
        """)
        params = {"pid": potrero_id, "uid": usuario_id}
    else:
        query = text("""
            SELECT nombre, finca, geom FROM potreros_base WHERE id = :pid
        """)
        params = {"pid": potrero_id}
    with engine.connect() as conn:
        gdf = gpd.read_postgis(query, conn, geom_col="geom", params=params)
    return gdf


def geometrias_exclusion(engine, potrero_id, usuario_id=None):
    if usuario_id is not None:
        query = text("""
            SELECT geom FROM zonas_exclusion WHERE potrero_id = :pid AND usuario_id = :uid
        """)
        params = {"pid": potrero_id, "uid": usuario_id}
    else:
        query = text("""
            SELECT geom FROM zonas_exclusion WHERE potrero_id = :pid
        """)
        params = {"pid": potrero_id}
    with engine.connect() as conn:
        gdf = gpd.read_postgis(query, conn, geom_col="geom", params=params)
    return gdf
