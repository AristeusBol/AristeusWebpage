from sqlalchemy import text


TIPOS_DENSIDAD = ["verde", "muerta", "total"]


def listar_fincas_disponibles(conn, usuario_id: int) -> list[str]:
    """Fincas del usuario: las que tienen potreros (aunque aún no tengan
    cálculos) más las que tengan cálculos. UNION para no repetir."""
    sql = text("""
        SELECT finca FROM (
            SELECT DISTINCT finca FROM potreros_base WHERE usuario_id = :uid
            UNION
            SELECT DISTINCT finca FROM calculos_stock WHERE usuario_id = :uid
        ) AS f
        ORDER BY finca ASC
    """)
    rows = conn.execute(sql, {"uid": usuario_id}).fetchall()
    return [r[0] for r in rows]


def _fechas_desde(conn, tabla: str, usuario_id: int, finca: str | None):
    if finca:
        sql = text(f"""
            SELECT DISTINCT fecha
            FROM {tabla}
            WHERE usuario_id = :uid AND finca = :finca
            ORDER BY fecha DESC
        """)
        return conn.execute(sql, {"uid": usuario_id, "finca": finca}).fetchall()
    sql = text(f"""
        SELECT DISTINCT fecha
        FROM {tabla}
        WHERE usuario_id = :uid
        ORDER BY fecha DESC
    """)
    return conn.execute(sql, {"uid": usuario_id}).fetchall()


def listar_fechas_disponibles(conn, usuario_id: int, finca: str | None = None) -> list[str]:
    """Fechas con cálculos; si no hay, fallback a fechas con puntos de mapa
    (sin geometrías: solo la columna fecha). Así una finca recién cargada
    ya ofrece fechas antes de calcular el stock."""
    rows = _fechas_desde(conn, "calculos_stock", usuario_id, finca)
    if not rows:
        rows = _fechas_desde(conn, "mapa_color", usuario_id, finca)

    return [r[0].isoformat() if hasattr(r[0], "isoformat") else str(r[0]) for r in rows]
