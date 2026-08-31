from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.security import HTTPAuthorizationCredentials

from core.db import engine
from core.seguridad import resolver_usuario_id, security
from repositorios.filtros import TIPOS_DENSIDAD, listar_fechas_disponibles, listar_fincas_disponibles

router = APIRouter(prefix="/api/mapa", tags=["filtros-mapa"])


@router.get("/filtros")
def get_filtros_opciones(
    finca: Optional[str] = Query(None, description="Finca seleccionada. Si se envía, las fechas se filtran solo para esa finca (cascada)"),
    usuario_id: Optional[int] = Query(None, description="ID usuario solo para dev/test sin token"),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    usuario_id_resuelto = resolver_usuario_id(credentials, usuario_id)
    finca_norm = finca.strip() if finca and finca.strip() else None

    with engine.connect() as conn:
        fincas = listar_fincas_disponibles(conn, usuario_id_resuelto)
        fechas = listar_fechas_disponibles(conn, usuario_id_resuelto, finca=finca_norm)

    return {
        "fincas": fincas,
        "fechas": fechas,
        "tipos_densidad": TIPOS_DENSIDAD,
        "filtros_aplicados": {"finca": finca_norm},
    }
