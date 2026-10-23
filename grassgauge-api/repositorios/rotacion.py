"""Consultas de asignaciones de pastoreo y trayectorias."""

from sqlalchemy import text

FILAS_SQL = """
    SELECT a.id AS asignacion_id, a.fecha_entrada, a.fecha_salida, a.notas,
           a.trayectoria_inicio,
           r.id AS rodeo_id, r.nombre AS rodeo, r.categoria,
           r.cabezas, r.peso_prom_kg, r.consumo_pct,
           p.id AS parcela_id, p.nombre AS parcela, p.estado,
           pt.id AS potrero_id, pt.nombre AS potrero, pt.finca
    FROM asignaciones a
    JOIN rodeos r ON r.id = a.rodeo_id AND r.usuario_id = :uid
    JOIN parcelas p ON p.id = a.parcela_id AND p.usuario_id = :uid
    JOIN potreros_base pt ON pt.id = p.potrero_id AND pt.usuario_id = :uid
    WHERE a.usuario_id = :uid
"""


def listar_asignaciones(conn, uid: int, orden: str):
    return conn.execute(text(FILAS_SQL + orden), {"uid": uid}).fetchall()


def listar_lotes(conn, uid: int):
    return conn.execute(
        text("""
            SELECT id, nombre, color, cabezas, peso_prom_kg, consumo_pct
            FROM rodeos WHERE usuario_id = :uid
            ORDER BY nombre ASC
        """),
        {"uid": uid},
    ).fetchall()


def listar_finalizadas(conn, uid: int):
    return conn.execute(
        text("""
            SELECT rodeo_id, trayectoria_inicio, finalizada_en
            FROM trayectorias_finalizadas WHERE usuario_id = :uid
        """),
        {"uid": uid},
    ).fetchall()
