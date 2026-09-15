from typing import Optional

from fastapi import APIRouter, Depends, Query

from core.db import engine
from core.seguridad import get_current_user_id
from repositorios.filtros import TIPOS_DENSIDAD, listar_fechas_disponibles, listar_fincas_disponibles

router = APIRouter(prefix="/api/mapa", tags=["filtros-mapa"])


@router.get("/filtros")
def get_filtros_opciones(
    finca: Optional[str] = Query(None, description="Estancia seleccionada. Si se envía, las fechas se filtran solo para esa estancia (cascada)"),
    usuario_id_resuelto: int = Depends(get_current_user_id),
):
    """Filtros en cascada. Devuelve {fincas, fechas, tipos_densidad}."""
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
