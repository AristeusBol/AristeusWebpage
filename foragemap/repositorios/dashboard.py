from sqlalchemy import text


def obtener_totales_dashboard(conn, usuario_id: int, finca: str, fecha) -> dict:
    # agregacion simple por finca y fecha, usa indice compuesto
    sql = text("""
        SELECT
            COALESCE(SUM(area_neta_ha), 0)      AS area_total_ha,
            COALESCE(SUM(masa_seca_verde), 0)   AS masa_verde,
            COALESCE(SUM(masa_seca_muerta), 0)  AS masa_muerta,
            COALESCE(SUM(masa_seca_total), 0)   AS masa_total,
            COUNT(*)                            AS potreros_count
        FROM calculos_stock
        WHERE usuario_id = :uid
          AND finca = :finca
          AND fecha = :fecha
    """)
    row = conn.execute(sql, {"uid": usuario_id, "finca": finca, "fecha": fecha}).fetchone()
    return {
        "area_total_ha": float(row.area_total_ha),
        "masa_verde": float(row.masa_verde),
        "masa_muerta": float(row.masa_muerta),
        "masa_total": float(row.masa_total),
        "potreros_count": int(row.potreros_count),
    }
