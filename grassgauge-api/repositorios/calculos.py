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
