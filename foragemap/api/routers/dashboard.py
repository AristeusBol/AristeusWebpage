from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import text

from core.db import engine
from core.seguridad import resolver_usuario_id, security
from repositorios.dashboard import obtener_totales_dashboard

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/resumen")
def get_resumen_dashboard(
    finca: str = Query(..., description="Finca exacta, ej: La Esperanza"),
    fecha: date = Query(..., description="Fecha YYYY-MM-DD, ej: 2024-04-01"),
    usuario_id: Optional[int] = Query(None, description="Solo dev/test sin token"),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    usuario_id_resuelto = resolver_usuario_id(credentials, usuario_id)

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
