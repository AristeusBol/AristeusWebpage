from datetime import date
from typing import List, Optional

from pydantic import BaseModel, field_validator

from api.schemas.comunes import MAX_NOTAS, texto_opcional_a_none, validar_id_positivo


class AsignacionUpdate(BaseModel):
    fecha_salida: Optional[date] = None
    notas: Optional[str] = None

    _notas = field_validator("notas")(classmethod(lambda cls, v: texto_opcional_a_none(v, MAX_NOTAS)))


class SemanaCreate(BaseModel):
    """Trayectoria de un lote: ventana fija de hasta 7 días desde `inicio`.

    dias[i] = lista de parcelas del día inicio+i ([] = día libre/bloqueado).
    Debe tener entre 1 y 7 listas; nunca superar los 7 días desde el inicio.
    Una parcela puede repetirse en días seguidos (se fusiona en un solo tramo
    de pastoreo). reemplazar_inicio: al editar, inicio de la trayectoria
    anterior a reemplazar (null = trayectoria nueva).
    """
    rodeo_id: int
    inicio: date
    dias: List[List[int]]
    reemplazar_inicio: Optional[date] = None

    _rodeo_id = field_validator("rodeo_id")(classmethod(lambda cls, v: validar_id_positivo(v, "rodeo_id")))

    @field_validator("dias")
    @classmethod
    def _dias_semana(cls, v: List[List[int]]) -> List[List[int]]:
        if not v or not (1 <= len(v) <= 7):
            raise ValueError("La trayectoria debe tener entre 1 y 7 días (una lista por posición)")
        for dia in v:
            if not isinstance(dia, list):
                raise ValueError("Cada día debe ser una lista de parcelas")
            for x in dia:
                if not (isinstance(x, int) and x > 0):
                    raise ValueError("parcela_id debe ser un entero positivo")
        return v


class FinalizarTrayectoria(BaseModel):
    """Pide al finalizar una trayectoria: marcar además sus parcelas como crítico."""
    enviar_critico: bool = False
