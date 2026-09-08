"""Acceso a datos de parcelas (hijas de potreros_base)."""
import json

from sqlalchemy import text

ESTADOS_VALIDOS = {"activa", "descanso", "excluida", "archivada"}

# Tolerancia de solape entre hermanas: intersección mayor a 1 m² se rechaza
# (compartir borde exacto SÍ está permitido).
SOLAPE_TOL_M2 = 1.0


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
    """True si la geometría candidata está dentro del potrero."""
    row = conn.execute(
        text("""
            SELECT ST_Within(
                ST_SetSRID(ST_GeomFromGeoJSON(:gj), 4326),
                (SELECT geom FROM potreros_base WHERE id = :pid AND usuario_id = :uid)
            ) AS dentro,
            ST_IsValid(ST_SetSRID(ST_GeomFromGeoJSON(:gj), 4326)) AS valida,
            ST_Area(ST_SetSRID(ST_GeomFromGeoJSON(:gj), 4326)::geography) / 10000.0 AS area_ha
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
    row = conn.execute(
        text("""
            SELECT EXISTS(
                SELECT 1 FROM parcelas
                WHERE usuario_id = :uid AND potrero_id = :pid
                  AND (:excluir IS NULL OR id != :excluir)
                  AND ST_Area(ST_Intersection(
                        geom::geography,
                        ST_SetSRID(ST_GeomFromGeoJSON(:gj), 4326)::geography
                      )) > :tol
            ) AS solapa
        """),
        {
            "uid": usuario_id, "pid": potrero_id,
            "excluir": excluir_id, "gj": gj_text, "tol": SOLAPE_TOL_M2,
        },
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
              AND estado != 'archivada'
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
              AND pa.estado != 'archivada'
            ORDER BY pa.nombre ASC
        """),
        {"uid": usuario_id, "finca": finca},
    ).fetchall()


def siguiente_nombre_parcela(conn, potrero_id, usuario_id, base_nombre):
    """Sugiere '<Potrero>-A, -B...' libre. Retorna el primer nombre no usado."""
    pot = potrero_del_usuario(conn, potrero_id, usuario_id)
    base = (pot.nombre if pot else base_nombre or "Parcela").strip() or "Parcela"
    rows = conn.execute(
        text("SELECT nombre FROM parcelas WHERE usuario_id=:uid AND potrero_id=:pid"),
        {"uid": usuario_id, "pid": potrero_id},
    ).fetchall()
    usados = {r.nombre for r in rows}
    for letra in [chr(c) for c in range(ord("A"), ord("Z") + 1)]:
        cand = f"{base}-{letra}"
        if cand not in usados:
            return cand
    i = 1
    while f"{base}-{i}" in usados:
        i += 1
    return f"{base}-{i}"
