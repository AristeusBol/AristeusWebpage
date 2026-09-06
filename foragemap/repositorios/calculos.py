from sqlalchemy import text


def upsert_calculo(conn, potrero_id, finca, fecha, area_neta_ha, masa_seca_verde, masa_seca_muerta, masa_seca_total, usuario_id=None):
    if usuario_id is None:
        res = conn.execute(text("SELECT usuario_id FROM potreros_base WHERE id=:pid"), {"pid": potrero_id}).fetchone()
        if res:
            usuario_id = res.usuario_id
        else:
            raise ValueError("usuario_id requerido para upsert_calculo y potrero no encontrado")

    consulta_actualizar = text("""
        INSERT INTO calculos_stock (usuario_id, potrero_id, finca, fecha, area_neta_ha,
                                    masa_seca_verde, masa_seca_muerta, masa_seca_total)
        VALUES (:uid, :p, :finca, :fecha, :area, :verde, :muerta, :total)
        ON CONFLICT (usuario_id, potrero_id, fecha)
        DO UPDATE SET finca = EXCLUDED.finca,
                      area_neta_ha = EXCLUDED.area_neta_ha,
                      masa_seca_verde = EXCLUDED.masa_seca_verde,
                      masa_seca_muerta = EXCLUDED.masa_seca_muerta,
                      masa_seca_total = EXCLUDED.masa_seca_total
    """)
    conn.execute(consulta_actualizar, {
        "uid": usuario_id,
        "p": potrero_id,
        "finca": finca,
        "fecha": fecha,
        "area": area_neta_ha,
        "verde": masa_seca_verde,
        "muerta": masa_seca_muerta,
        "total": masa_seca_total,
    })


def listar_calculos_por_potrero(conn, potrero_id, usuario_id=None):
    if usuario_id is not None:
        consulta = text("""
            SELECT id, potrero_id, finca, fecha, area_neta_ha, masa_seca_verde,
                   masa_seca_muerta, masa_seca_total
            FROM calculos_stock
            WHERE potrero_id = :pid AND usuario_id = :uid
            ORDER BY fecha DESC, id DESC
        """)
        res = conn.execute(consulta, {"pid": potrero_id, "uid": usuario_id}).fetchall()
    else:
        consulta = text("""
            SELECT id, potrero_id, finca, fecha, area_neta_ha, masa_seca_verde,
                   masa_seca_muerta, masa_seca_total
            FROM calculos_stock
            WHERE potrero_id = :pid
            ORDER BY fecha DESC, id DESC
        """)
        res = conn.execute(consulta, {"pid": potrero_id}).fetchall()
    return [{
        "id": row.id,
        "potrero_id": row.potrero_id,
        "finca": row.finca,
        "fecha": row.fecha.isoformat(),
        "area_neta_ha": float(row.area_neta_ha) if row.area_neta_ha is not None else None,
        "masa_seca_verde": float(row.masa_seca_verde) if row.masa_seca_verde is not None else None,
        "masa_seca_muerta": float(row.masa_seca_muerta) if row.masa_seca_muerta is not None else None,
        "masa_seca_total": float(row.masa_seca_total) if row.masa_seca_total is not None else None,
    } for row in res]
