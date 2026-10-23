from typing import Optional

from pydantic import BaseModel, field_validator

from api.schemas.comunes import (
    MAX_NOMBRE, MAX_NOTAS,
    texto_obligatorio, texto_opcional_a_none, texto_opcional_no_vacio, validar_color,
)
from dominio.constantes import CATEGORIAS_RODEO


def validar_categoria(v: str) -> str:
    v = (v or "").strip().lower()
    if v not in CATEGORIAS_RODEO:
        raise ValueError(f"categoría inválida. Use: {sorted(CATEGORIAS_RODEO)}")
    return v


def validar_cabezas(v: int) -> int:
    if v is None or int(v) < 1:
        raise ValueError("mínimo 1 cabeza")
    return int(v)


def validar_peso(v: float) -> float:
    if v is None or float(v) <= 0:
        raise ValueError("peso positivo requerido")
    return float(v)


def validar_consumo(v: Optional[float]) -> Optional[float]:
    if v is None:
        return v
    if not 0.5 <= float(v) <= 6.0:
        raise ValueError("consumo entre 0.5 y 6.0 %")
    return float(v)


class RodeoCreate(BaseModel):
    nombre: str
    categoria: str
    cabezas: int
    peso_prom_kg: float
    consumo_pct: Optional[float] = None
    notas: Optional[str] = None
    color: Optional[str] = None

    _categoria = field_validator("categoria")(classmethod(lambda cls, v: validar_categoria(v)))
    _color = field_validator("color")(classmethod(lambda cls, v: validar_color(v)))
    _nombre = field_validator("nombre")(classmethod(lambda cls, v: texto_obligatorio(v, MAX_NOMBRE)))
    _cabezas = field_validator("cabezas")(classmethod(lambda cls, v: validar_cabezas(v)))
    _peso = field_validator("peso_prom_kg")(classmethod(lambda cls, v: validar_peso(v)))
    _consumo = field_validator("consumo_pct")(classmethod(lambda cls, v: validar_consumo(v)))
    _notas = field_validator("notas")(classmethod(lambda cls, v: texto_opcional_a_none(v, MAX_NOTAS)))


class RodeoUpdate(BaseModel):
    nombre: Optional[str] = None
    categoria: Optional[str] = None
    cabezas: Optional[int] = None
    peso_prom_kg: Optional[float] = None
    consumo_pct: Optional[float] = None
    notas: Optional[str] = None
    color: Optional[str] = None

    _categoria = field_validator("categoria")(classmethod(lambda cls, v: validar_categoria(v) if v is not None else v))
    _color = field_validator("color")(classmethod(lambda cls, v: validar_color(v)))
    _nombre = field_validator("nombre")(classmethod(lambda cls, v: texto_opcional_no_vacio(v, MAX_NOMBRE)))
    _cabezas = field_validator("cabezas")(classmethod(lambda cls, v: v if v is None else validar_cabezas(v)))
    _peso = field_validator("peso_prom_kg")(classmethod(lambda cls, v: v if v is None else validar_peso(v)))
    _consumo = field_validator("consumo_pct")(classmethod(lambda cls, v: validar_consumo(v)))
    _notas = field_validator("notas")(classmethod(lambda cls, v: texto_opcional_a_none(v, MAX_NOTAS)))
