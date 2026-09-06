from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text

from core.db import engine
from core.seguridad import get_current_user_id
from repositorios.dashboard import obtener_totales_dashboard

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/resumen")
def get_resumen_dashboard(
    finca: str = Query(..., description="Finca exacta, ej: La Esperanza"),
    fecha: date = Query(..., description="Fecha YYYY-MM-DD, ej: 2024-04-01"),
    usuario_id_resuelto: int = Depends(get_current_user_id),
):
    """Métricas agregadas por finca y fecha. Devuelve {metricas, cobertura}."""
    finca_norm = finca.strip()
    if not finca_norm:
        raise HTTPException(status_code=400, detail="finca requerida")

    with engine.connect() as conn:
        totales = obtener_totales_dashboard(conn, usuario_id_resuelto, finca_norm, fecha)

    sin_datos = totales["potreros_count"] == 0

    return {
        "filtros": {
            "finca": finca_norm,
            "fecha": fecha.isoformat(),
            "usuario_id": usuario_id_resuelto,
        },
        "metricas": {
            "area": {
                "total_ha": totales["area_total_ha"],
                "unidad": "ha",
            },
            "masa_seca": {
                "verde_kg": totales["masa_verde"],
                "muerta_kg": totales["masa_muerta"],
                "total_kg": totales["masa_total"],
                "unidad": "kg",
            },
        },
        "cobertura": {
            "potreros_incluidos": totales["potreros_count"],
        },
        "sin_datos": sin_datos,
    }


@router.get("/serie")
def get_serie_temporal(
    finca: str = Query(..., description="Finca exacta, ej: Finca Don Carlos"),
    potrero_id: Optional[int] = Query(None, description="Si se pasa, serie solo de ese lote"),
    usuario_id_resuelto: int = Depends(get_current_user_id),
):
    """Serie temporal de stock por fecha. Devuelve {filtros, puntos}."""
    finca_norm = finca.strip()
    if not finca_norm:
        raise HTTPException(status_code=400, detail="finca requerida")

    with engine.connect() as conn:
        if potrero_id is not None:
            dueno = conn.execute(
                text("SELECT 1 FROM potreros_base WHERE id = :pid AND usuario_id = :uid"),
                {"pid": potrero_id, "uid": usuario_id_resuelto},
            ).fetchone()
            if not dueno:
                raise HTTPException(status_code=404, detail=f"Potrero {potrero_id} no existe o no es tuyo")
            sql = text("""
                SELECT fecha,
                        COALESCE(SUM(area_neta_ha), 0)    AS area,
                        COALESCE(SUM(masa_seca_verde), 0) AS verde,
                        COALESCE(SUM(masa_seca_muerta), 0) AS muerta,
                        COALESCE(SUM(masa_seca_total), 0) AS total,
                        COUNT(*) AS n
                FROM calculos_stock
                WHERE usuario_id = :uid
                  AND finca = :finca
                  AND potrero_id = :pid
                GROUP BY fecha
                ORDER BY fecha ASC
            """)
            params = {"uid": usuario_id_resuelto, "finca": finca_norm, "pid": potrero_id}
            rows = conn.execute(sql, params).fetchall()
        else:
            sql = text("""
                SELECT fecha,
                       COALESCE(SUM(area_neta_ha), 0)    AS area,
                       COALESCE(SUM(masa_seca_verde), 0) AS verde,
                       COALESCE(SUM(masa_seca_muerta), 0) AS muerta,
                       COALESCE(SUM(masa_seca_total), 0) AS total,
                       COUNT(*) AS n
                FROM calculos_stock
                WHERE usuario_id = :uid
                  AND finca = :finca
                GROUP BY fecha
                ORDER BY fecha ASC
            """)
            params = {"uid": usuario_id_resuelto, "finca": finca_norm}
            rows = conn.execute(sql, params).fetchall()

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
            "usuario_id": usuario_id_resuelto,
        },
        "puntos": puntos,
    }
