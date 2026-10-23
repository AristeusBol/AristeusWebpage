from typing import Any, Dict, Optional

from pydantic import BaseModel, field_validator

from api.schemas.comunes import (
    MAX_NOMBRE,
    estado_opcional, geom_opcional, texto_opcional_a_none, texto_opcional_no_vacio,
    validar_estado, validar_polygon_geom,
)


class ParcelaCreate(BaseModel):
    nombre: Optional[str] = None
    estado: str = "optimo"
    geom: Dict[str, Any]

    _geom = field_validator("geom")(classmethod(lambda cls, v: validar_polygon_geom(v)))

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, v: Optional[str]) -> Optional[str]:
        return texto_opcional_a_none(v, MAX_NOMBRE)

    @field_validator("estado")
    @classmethod
    def _estado(cls, v: str) -> str:
        return validar_estado(v)


class ParcelaUpdate(BaseModel):
    nombre: Optional[str] = None
    estado: Optional[str] = None
    geom: Optional[Dict[str, Any]] = None

    _geom = field_validator("geom")(classmethod(lambda cls, v: geom_opcional(v)))

    @field_validator("nombre")
    @classmethod
    def _nombre_opt(cls, v: Optional[str]) -> Optional[str]:
        return texto_opcional_no_vacio(v, MAX_NOMBRE)

    @field_validator("estado")
    @classmethod
    def _estado_opt(cls, v: Optional[str]) -> Optional[str]:
        return estado_opcional(v)
