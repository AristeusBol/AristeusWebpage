from typing import Any, Dict, Optional

from pydantic import BaseModel, field_validator

from api.schemas.comunes import (
    MAX_FINCA, MAX_NOMBRE,
    geom_opcional, texto_obligatorio, texto_opcional_no_vacio, validar_polygon_geom,
)


class PotreroCreate(BaseModel):
    nombre: str
    finca: str
    geom: Dict[str, Any]

    _geom = field_validator("geom")(classmethod(lambda cls, v: validar_polygon_geom(v)))

    @field_validator("nombre")
    @classmethod
    def _nombre_no_vacio(cls, v: str) -> str:
        return texto_obligatorio(v, MAX_NOMBRE)

    @field_validator("finca")
    @classmethod
    def _finca_no_vacia(cls, v: str) -> str:
        return texto_obligatorio(v, MAX_FINCA, "finca")


class PotreroUpdate(BaseModel):
    """Renombra / redibuja un potrero propio. La finca la gestiona el
    operador (cambiarla dejaría hijas con finca stale): no se expone."""

    nombre: Optional[str] = None
    geom: Optional[Dict[str, Any]] = None

    _geom = field_validator("geom")(classmethod(lambda cls, v: geom_opcional(v)))

    @field_validator("nombre")
    @classmethod
    def _nombre_opt(cls, v: Optional[str]) -> Optional[str]:
        return texto_opcional_no_vacio(v, MAX_NOMBRE)
