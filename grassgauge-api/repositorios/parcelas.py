"""Acceso a datos de parcelas (hijas de potreros_base)."""
import json

from sqlalchemy import text

ESTADOS_VALIDOS = {"critico", "desarrollo", "optimo", "maduro", "pasado"}

# Tolerancia de solape entre hermanas: intersección mayor a 1 m² se rechaza
# (compartir borde exacto SÍ está permitido).
SOLAPE_TOL_M2 = 1.0

# Tolerancia de área fuera del potrero: el snap al borde puede dejar el
# polígono unas fracciones de mm afuera por redondeo de coordenadas. Hasta
# 1 m² se considera un borde compartido y se recorta; más, se rechaza.
FUERA_TOL_M2 = 1.0


def geom_geojson_text(geom: dict) -> str:
    return json.dumps(geom)


def potrero_del_usuario(conn, potrero_id, usuario_id):
    row = conn.execute(
        text("""
            SELECT id, nombre, finca,
                   ST_AsGeoJSON(geom)::json AS geom_json,
                   ST_Area(geom::geography) / 10000.0 AS area_bruta_ha
            FROM potreros_base
            WHERE id = :pid AND usuario_id = :uid
        """),
        {"pid": potrero_id, "uid": usuario_id},
    ).fetchone()
    return row


def calculo_potrero(conn, potrero_id, usuario_id, fecha_iso):
    """Cálculo forrajero del potrero padre para prorrateo. None si no hay."""
    if not fecha_iso:
        return None
    return conn.execute(
        text("""
            SELECT area_neta_ha, masa_seca_verde, masa_seca_muerta, masa_seca_total
            FROM calculos_stock
            WHERE usuario_id = :uid AND potrero_id = :pid AND fecha = :fecha
        """),
        {"uid": usuario_id, "pid": potrero_id, "fecha": fecha_iso},
    ).fetchone()


def validar_contenida(conn, gj_text, potrero_id, usuario_id):
    """Valida la geometría candidata contra el potrero.

    Se usa ST_Covers (no ST_Within) para permitir compartir borde exacto con el
    potrero. Además se calcula el área que queda fuera: el snap al borde del
    mapa interpola coordenadas y puede dejar el punto a una fracción de
    milímetro fuera por error de coma flotante, que ST_Covers exacto rechaza.
    """
    row = conn.execute(
        text("""
            SELECT ST_Covers(p.geom, c.geom) AS dentro,
                   ST_IsValid(c.geom) AS valida,
                   ST_Area(c.geom::geography) / 10000.0 AS area_ha,
                   ST_Area(ST_Difference(c.geom, p.geom)::geography) AS fuera_m2
            FROM (SELECT geom FROM potreros_base WHERE id = :pid AND usuario_id = :uid) p,
                 (SELECT ST_SetSRID(ST_GeomFromGeoJSON(:gj), 4326) AS geom) c
        """),
        {"gj": gj_text, "pid": potrero_id, "uid": usuario_id},
    ).fetchone()
    return row


def geometria_recortada(conn, gj_text, potrero_id, usuario_id):
    """Recorta la geometría candidata al potrero y resta zonas de exclusión.

    El recorte al potrero elimina el error de coma flotante de los vértices
    pegados al borde (snap), garantizando que la parcela guardada quede
    realmente dentro. Retorna fila con geom_json y area_ha resultante.
    """
    row = conn.execute(
        text("""
            WITH cand AS (
                SELECT ST_SetSRID(ST_GeomFromGeoJSON(:gj), 4326) AS g
            ),
            exc AS (
                SELECT ST_Union(z.geom) AS u
                FROM zonas_exclusion z
                WHERE z.usuario_id = :uid AND z.potrero_id = :pid
            ),
            base AS (
                SELECT p.geom AS pot,
                       CASE WHEN e.u IS NULL
                            THEN c.g
                            ELSE ST_Difference(c.g, e.u)
                       END AS g
                FROM cand c
                JOIN potreros_base p
                  ON p.id = :pid AND p.usuario_id = :uid
                LEFT JOIN exc e ON true
            ),
            rec AS (
                SELECT CASE WHEN g IS NULL OR ST_IsEmpty(g)
                            THEN NULL
                            ELSE ST_CollectionExtract(ST_Intersection(g, pot), 3)
                       END AS g
                FROM base
            )
            SELECT
                ST_AsGeoJSON(g)::json AS geom_json,
                ST_Area(g::geography) / 10000.0 AS area_ha
            FROM rec
        """),
        {"gj": gj_text, "pid": potrero_id, "uid": usuario_id},
    ).fetchone()
    return row


def area_choque_exclusiones(conn, gj_text, potrero_id, usuario_id):
    """Área (m²) de la geometría candidata que pisa zonas de exclusión del potrero.

    Las parcelas solo pueden dibujarse en área útil: dentro del potrero y
    fuera de sus zonas de exclusión.
    """
    row = conn.execute(
        text("""
            SELECT COALESCE(SUM(ST_Area(ST_Intersection(
                z.geom::geography,
                ST_SetSRID(ST_GeomFromGeoJSON(:gj), 4326)::geography
            ))), 0) AS area_m2
            FROM zonas_exclusion z
            WHERE z.usuario_id = :uid AND z.potrero_id = :pid
        """),
        {"uid": usuario_id, "pid": potrero_id, "gj": gj_text},
    ).fetchone()
    return float(row.area_m2 or 0) if row else 0.0


def hay_solape(conn, gj_text, potrero_id, usuario_id, excluir_id=None):
    """True si la geometría candidata solapa (>1m²) con alguna hermana."""
    # Filtro opcional como fragmento: `(:excluir IS NULL OR ...)` hace que
    # Postgres no pueda inferir el tipo del parámetro None (AmbiguousParameter).
    filtro_excluir = " AND id != :excluir" if excluir_id is not None else ""
    params = {"uid": usuario_id, "pid": potrero_id, "gj": gj_text, "tol": SOLAPE_TOL_M2}
    if excluir_id is not None:
        params["excluir"] = excluir_id
    row = conn.execute(
        text(f"""
            SELECT EXISTS(
                SELECT 1 FROM parcelas
                WHERE usuario_id = :uid AND potrero_id = :pid
                  {filtro_excluir}
                  AND ST_Area(ST_Intersection(
                        geom::geography,
                        ST_SetSRID(ST_GeomFromGeoJSON(:gj), 4326)::geography
                      )) > :tol
            ) AS solapa
        """),
        params,
    ).fetchone()
    return bool(row.solapa) if row else False


def insertar_parcela(conn, usuario_id, potrero_id, nombre, estado, gj_text):
    return conn.execute(
        text("""
            INSERT INTO parcelas (usuario_id, potrero_id, nombre, estado, geom)
            VALUES (:uid, :pid, :nombre, :estado,
                    ST_SetSRID(ST_GeomFromGeoJSON(:gj), 4326))
            RETURNING id, ST_Area(geom::geography) / 10000.0 AS area_ha
        """),
        {"uid": usuario_id, "pid": potrero_id, "nombre": nombre,
         "estado": estado, "gj": gj_text},
    ).fetchone()


def obtener_parcela(conn, parcela_id, usuario_id):
    return conn.execute(
        text("""
            SELECT id, potrero_id, nombre, estado,
                   ST_AsGeoJSON(geom)::json AS geom_json,
                   ST_Area(geom::geography) / 10000.0 AS area_ha
            FROM parcelas
            WHERE id = :id AND usuario_id = :uid
        """),
        {"id": parcela_id, "uid": usuario_id},
    ).fetchone()


def listar_parcelas_potrero(conn, potrero_id, usuario_id):
    return conn.execute(
        text("""
            SELECT id, potrero_id, nombre, estado,
                   ST_AsGeoJSON(geom)::json AS geom_json,
                   ST_Area(geom::geography) / 10000.0 AS area_ha
            FROM parcelas
            WHERE potrero_id = :pid AND usuario_id = :uid
            ORDER BY nombre ASC
        """),
        {"pid": potrero_id, "uid": usuario_id},
    ).fetchall()


def listar_parcelas_finca(conn, usuario_id, finca):
    return conn.execute(
        text("""
            SELECT pa.id, pa.potrero_id, pa.nombre, pa.estado, pb.finca,
                   ST_AsGeoJSON(pa.geom)::json AS geom_json,
                   ST_Area(pa.geom::geography) / 10000.0 AS area_ha
            FROM parcelas pa
            JOIN potreros_base pb ON pb.id = pa.potrero_id AND pb.usuario_id = pa.usuario_id
            WHERE pa.usuario_id = :uid AND pb.finca = :finca
            ORDER BY pa.nombre ASC
        """),
        {"uid": usuario_id, "finca": finca},
    ).fetchall()


def siguiente_nombre_parcela(conn, potrero_id, usuario_id, base_nombre):
    """Sugiere '<Potrero>_1, _2...' libre. Retorna el primer N no usado.

    Considera los nombres existentes y reutiliza el primer hueco libre
    (1, 2, ...) para mantener la serie compacta.
    """
    pot = potrero_del_usuario(conn, potrero_id, usuario_id)
    base = (pot.nombre if pot else base_nombre or "Parcela").strip() or "Parcela"
    rows = conn.execute(
        text("SELECT nombre FROM parcelas WHERE usuario_id=:uid AND potrero_id=:pid"),
        {"uid": usuario_id, "pid": potrero_id},
    ).fetchall()
    usados = {r.nombre for r in rows}
    i = 1
    while f"{base}_{i}" in usados:
        i += 1
    return f"{base}_{i}"


def stock_zonal_parcela(conn, parcela_id, usuario_id, fecha_iso):
    """Promedio real de densidades dentro de la parcela (misma fórmula que potrero).
    Promedia los puntos de mapa_color cubiertos por la parcela (fuera de
    exclusiones) y multiplica por el área neta de la parcela recortada.
    Retorna dict con masas/t_ha/n_puntos/area_ha o None si no hay fecha.
    """
    if not fecha_iso:
        return {
            "masa_verde_kg": None, "masa_muerta_kg": None, "masa_total_kg": None,
            "t_ha_verde": None, "t_ha_muerta": None, "t_ha_total": None,
            "tiene_calculo": False, "n_puntos": 0, "area_ha": None,
        }
    row = conn.execute(
        text("""
            WITH pa AS (
                SELECT geom, potrero_id FROM parcelas
                WHERE id = :parc AND usuario_id = :uid
            ),
            pts AS (
                SELECT m.densidad_verde_g_m2 AS v,
                       m.densidad_muerta_g_m2 AS m,
                       m.densidad_total_g_m2 AS t
                FROM mapa_color m, pa
                WHERE m.usuario_id = :uid
                  AND m.potrero_id = pa.potrero_id
                  AND m.fecha = :fecha
                  AND ST_Covers(pa.geom, m.geom)
                  AND NOT EXISTS (
                      SELECT 1 FROM zonas_exclusion z
                      WHERE z.usuario_id = m.usuario_id
                        AND z.potrero_id = m.potrero_id
                        AND ST_Covers(z.geom, m.geom)
                  )
            ),
            area AS (
                SELECT ST_Area(
                    COALESCE(
                        ST_Difference(
                            pa.geom,
                            (SELECT ST_Union(z.geom) FROM zonas_exclusion z
                             WHERE z.usuario_id = :uid AND z.potrero_id = pa.potrero_id)
                        ),
                        pa.geom
                    )::geography
                ) / 10000.0 AS area_ha
                FROM pa
            )
            SELECT (SELECT COUNT(*) FROM pts) AS n,
                   (SELECT AVG(v) FROM pts) AS vmean,
                   (SELECT AVG(m) FROM pts) AS mmean,
                   (SELECT AVG(t) FROM pts) AS tmean,
                   (SELECT area_ha FROM area) AS area_ha
        """),
        {"parc": parcela_id, "uid": usuario_id, "fecha": fecha_iso},
    ).fetchone()
    n = int(row.n or 0) if row else 0
    area_ha = float(row.area_ha) if row and row.area_ha is not None else None
    if not row or n == 0 or area_ha is None or area_ha <= 0:
        return {
            "masa_verde_kg": None, "masa_muerta_kg": None, "masa_total_kg": None,
            "t_ha_verde": None, "t_ha_muerta": None, "t_ha_total": None,
            "tiene_calculo": False, "n_puntos": n, "area_ha": area_ha,
        }
    vmean = float(row.vmean) if row.vmean is not None else None
    mmean = float(row.mmean) if row.mmean is not None else None
    tmean = float(row.tmean) if row.tmean is not None else None
    if vmean is None or mmean is None or tmean is None:
        return {
            "masa_verde_kg": None, "masa_muerta_kg": None, "masa_total_kg": None,
            "t_ha_verde": None, "t_ha_muerta": None, "t_ha_total": None,
            "tiene_calculo": False, "n_puntos": n, "area_ha": area_ha,
        }
    area_m2 = area_ha * 10000.0
    verde_kg = vmean * area_m2 / 1000.0
    muerta_kg = mmean * area_m2 / 1000.0
    total_kg = tmean * area_m2 / 1000.0
    return {
        "masa_verde_kg": verde_kg, "masa_muerta_kg": muerta_kg, "masa_total_kg": total_kg,
        "t_ha_verde": vmean * 0.01, "t_ha_muerta": mmean * 0.01, "t_ha_total": tmean * 0.01,
        "densidad_promedio_verde_g_m2": vmean,
        "densidad_promedio_muerta_g_m2": mmean,
        "densidad_promedio_total_g_m2": tmean,
        "tiene_calculo": True, "n_puntos": n, "area_ha": area_ha,
    }


def serie_zonal_parcela(conn, parcela_id, usuario_id):
    """Serie por fecha del zonal de una parcela (misma fórmula que potrero).

    Promedia por fecha los puntos de mapa_color cubiertos por la parcela
    (fuera de exclusiones) y multiplica por el área neta de la parcela
    (constante: geometría menos exclusiones del potrero padre).
    Solo incluye fechas con puntos (n > 0). Retorna filas con
    fecha, n, vmean, mmean, tmean y area_ha.
    """
    return conn.execute(
        text("""
            WITH pa AS (
                SELECT geom, potrero_id FROM parcelas
                WHERE id = :parc AND usuario_id = :uid
            ),
            area AS (
                SELECT ST_Area(
                    COALESCE(
                        ST_Difference(
                            pa.geom,
                            (SELECT ST_Union(z.geom) FROM zonas_exclusion z
                             WHERE z.usuario_id = :uid AND z.potrero_id = pa.potrero_id)
                        ),
                        pa.geom
                    )::geography
                ) / 10000.0 AS area_ha
                FROM pa
            )
            SELECT m.fecha AS fecha,
                   COUNT(*) AS n,
                   AVG(m.densidad_verde_g_m2) AS vmean,
                   AVG(m.densidad_muerta_g_m2) AS mmean,
                   AVG(m.densidad_total_g_m2) AS tmean,
                   (SELECT area_ha FROM area) AS area_ha
            FROM mapa_color m, pa
            WHERE m.usuario_id = :uid
              AND m.potrero_id = pa.potrero_id
              AND ST_Covers(pa.geom, m.geom)
              AND NOT EXISTS (
                  SELECT 1 FROM zonas_exclusion z
                  WHERE z.usuario_id = m.usuario_id
                    AND z.potrero_id = m.potrero_id
                    AND ST_Covers(z.geom, m.geom)
              )
            GROUP BY m.fecha
            ORDER BY m.fecha ASC
        """),
        {"parc": parcela_id, "uid": usuario_id},
    ).fetchall()


def zonales_finca(conn, uid, fecha_iso, rows):
    """Promedios zonales por parcela en una sola consulta (misma fórmula que potrero)."""
    if not fecha_iso or not rows:
        return {}
    pids = sorted({r.potrero_id for r in rows})
    res = conn.execute(
        text("""
            WITH pa AS (
                SELECT id, potrero_id, geom FROM parcelas
                WHERE usuario_id = :uid
                  AND potrero_id = ANY(:pids)
            ),
            area AS (
                SELECT pa.id AS pid,
                       ST_Area(COALESCE(
                           ST_Difference(pa.geom, u.u),
                           pa.geom
                       )::geography) / 10000.0 AS area_ha
                FROM pa
                LEFT JOIN LATERAL (
                    SELECT ST_Union(z.geom) AS u FROM zonas_exclusion z
                    WHERE z.usuario_id = :uid AND z.potrero_id = pa.potrero_id
                ) u ON true
            )
            SELECT pa.id AS pid,
                   COUNT(m.geom) AS n,
                   AVG(m.densidad_verde_g_m2) AS vmean,
                   AVG(m.densidad_muerta_g_m2) AS mmean,
                   AVG(m.densidad_total_g_m2) AS tmean,
                   MAX(area.area_ha) AS area_ha
            FROM pa
            JOIN area ON area.pid = pa.id
            LEFT JOIN mapa_color m
              ON m.usuario_id = :uid
             AND m.potrero_id = pa.potrero_id
             AND m.fecha = :fecha
             AND ST_Covers(pa.geom, m.geom)
             AND NOT EXISTS (
                 SELECT 1 FROM zonas_exclusion z
                 WHERE z.usuario_id = m.usuario_id AND z.potrero_id = m.potrero_id
                   AND ST_Covers(z.geom, m.geom)
             )
            GROUP BY pa.id
        """),
        {"uid": uid, "pids": pids, "fecha": fecha_iso},
    ).fetchall()
    return {
        int(r.pid): zonal_row_to_dict(r.n, r.vmean, r.mmean, r.tmean, r.area_ha)
        for r in res
    }
