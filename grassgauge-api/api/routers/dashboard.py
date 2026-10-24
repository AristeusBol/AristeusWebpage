from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text

from core.db import engine
from core.seguridad import get_current_user_id
from dominio.stock import zonal_row_to_dict
from repositorios import parcelas as repo_parcelas

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/serie")
def get_serie_temporal(
    finca: str = Query(..., description="Estancia exacta, ej: Finca Don Carlos"),
    potrero_id: Optional[int] = Query(None, description="Si se pasa, serie solo de ese lote"),
    parcela_id: Optional[int] = Query(None, description="Si se pasa, serie solo de esa parcela (excluyente con potrero_id)"),
    usuario_id_resuelto: int = Depends(get_current_user_id),
):
    """Serie temporal de stock por fecha. Devuelve {filtros, puntos}."""
    finca_norm = finca.strip()
    if not finca_norm:
        raise HTTPException(status_code=400, detail="estancia requerida")

    with engine.connect() as conn:
        if parcela_id is not None:
            pa = conn.execute(
                text("""
                    SELECT pa.potrero_id AS potrero_id
                    FROM parcelas pa
                    JOIN potreros_base pb ON pb.id = pa.potrero_id AND pb.usuario_id = pa.usuario_id
                    WHERE pa.id = :parc AND pa.usuario_id = :uid AND pb.finca = :finca
                """),
                {"parc": parcela_id, "uid": usuario_id_resuelto, "finca": finca_norm},
            ).fetchone()
            if not pa:
                raise HTTPException(status_code=404, detail=f"Parcela {parcela_id} no existe o no es tuya")
            if potrero_id is not None and int(pa.potrero_id) != potrero_id:
                raise HTTPException(status_code=400, detail=f"La parcela {parcela_id} no pertenece al potrero {potrero_id}")
            rows = repo_parcelas.serie_zonal_parcela(conn, parcela_id, usuario_id_resuelto)
            puntos = []
            for r in rows:
                z = zonal_row_to_dict(r.n, r.vmean, r.mmean, r.tmean, r.area_ha,
                                      incluir_estimado=False)
                if not z["tiene_calculo"]:
                    continue
                puntos.append({
                    "fecha": r.fecha.isoformat() if hasattr(r.fecha, "isoformat") else str(r.fecha),
                    "area_ha": z["area_ha"],
                    "verde_kg": z["masa_verde_kg"],
                    "muerta_kg": z["masa_muerta_kg"],
                    "total_kg": z["masa_total_kg"],
                    "t_ha": z["t_ha_total"],
                    "potreros": z["n_puntos"],
                })
            return {
                "filtros": {
                    "finca": finca_norm,
                    "potrero_id": int(pa.potrero_id),
                    "parcela_id": parcela_id,
                    "usuario_id": usuario_id_resuelto,
                },
                "puntos": puntos,
            }
        filtro_potrero = ""
        params = {"uid": usuario_id_resuelto, "finca": finca_norm}
        if potrero_id is not None:
            dueno = conn.execute(
                text("SELECT 1 FROM potreros_base WHERE id = :pid AND usuario_id = :uid"),
                {"pid": potrero_id, "uid": usuario_id_resuelto},
            ).fetchone()
            if not dueno:
                raise HTTPException(status_code=404, detail=f"Potrero {potrero_id} no existe o no es tuyo")
            filtro_potrero = " AND potrero_id = :pid"
            params["pid"] = potrero_id
        rows = conn.execute(
            text(f"""
                SELECT fecha,
                       COALESCE(SUM(area_neta_ha), 0)    AS area,
                       COALESCE(SUM(masa_seca_verde), 0) AS verde,
                       COALESCE(SUM(masa_seca_muerta), 0) AS muerta,
                       COALESCE(SUM(masa_seca_total), 0) AS total,
                       COUNT(*) AS n
                FROM calculos_stock
                WHERE usuario_id = :uid
                  AND finca = :finca{filtro_potrero}
                GROUP BY fecha
                ORDER BY fecha ASC
            """),
            params,
        ).fetchall()

    puntos = []
    for r in rows:
        area = float(r.area)
        total = float(r.total)
        puntos.append({
            "fecha": r.fecha.isoformat() if hasattr(r.fecha, "isoformat") else str(r.fecha),
            "area_ha": area,
            "verde_kg": float(r.verde),
            "muerta_kg": float(r.muerta),
            "total_kg": total,
            "t_ha": (total / 1000.0 / area) if area > 0 else None,
            "potreros": int(r.n),
        })

    return {
        "filtros": {
            "finca": finca_norm,
            "potrero_id": potrero_id,
            "parcela_id": None,
            "usuario_id": usuario_id_resuelto,
        },
        "puntos": puntos,
    }
