"""Schemas de la API agrupados por recurso.

Los imports históricos (`from api.schemas import X`) siguen funcionando.
"""

from api.schemas.parcelas import ParcelaCreate, ParcelaUpdate
from api.schemas.potreros import PotreroCreate, PotreroUpdate
from api.schemas.rodeos import RodeoCreate, RodeoUpdate
from api.schemas.rotacion import AsignacionUpdate, FinalizarTrayectoria, SemanaCreate
from api.schemas.usuarios import (
    LoginRequest, LoginRespuesta, UsuarioRegistro, UsuarioRespuesta,
)
from dominio.constantes import CATEGORIAS_RODEO, ESTADOS_PARCELA

__all__ = [
    "UsuarioRegistro", "UsuarioRespuesta", "LoginRequest", "LoginRespuesta",
    "PotreroCreate", "PotreroUpdate", "ParcelaCreate", "ParcelaUpdate",
    "RodeoCreate", "RodeoUpdate", "AsignacionUpdate", "SemanaCreate",
    "FinalizarTrayectoria", "CATEGORIAS_RODEO", "ESTADOS_PARCELA",
]
