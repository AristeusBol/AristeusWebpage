from sqlalchemy import text


TIPOS_DENSIDAD = ["verde", "muerta", "total"]


def listar_fincas_disponibles(conn, usuario_id: int) -> list[str]:
    # calculos_stock es liviana, no trae geometrias
    sql = text("""
        SELECT DISTINCT finca
        FROM calculos_stock
        WHERE usuario_id = :uid
        ORDER BY finca ASC
    """)
    rows = conn.execute(sql, {"uid": usuario_id}).fetchall()
    return [r[0] for r in rows]


def listar_fechas_disponibles(conn, usuario_id: int, finca: str | None = None) -> list[str]:
    if finca:
        sql = text("""
            SELECT DISTINCT fecha
            FROM calculos_stock
            WHERE usuario_id = :uid AND finca = :finca
            ORDER BY fecha DESC
        """)
        rows = conn.execute(sql, {"uid": usuario_id, "finca": finca}).fetchall()
    else:
        sql = text("""
            SELECT DISTINCT fecha
            FROM calculos_stock
            WHERE usuario_id = :uid
            ORDER BY fecha DESC
        """)
        rows = conn.execute(sql, {"uid": usuario_id}).fetchall()

    return [r[0].isoformat() if hasattr(r[0], "isoformat") else str(r[0]) for r in rows]
