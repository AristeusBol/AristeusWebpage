import re
from datetime import date
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, field_validator


class UsuarioRegistro(BaseModel):
    email: str
    password: str


class UsuarioRespuesta(BaseModel):
    id: int
    nombre: str
    email: str


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginRespuesta(BaseModel):
    access_token: str
    token_type: str = "bearer"
    id: int
    nombre: str
    email: str


ESTADOS_PARCELA = {"critico", "desarrollo", "optimo", "maduro", "pasado"}


def _validar_polygon_geom(v: Any) -> Dict[str, Any]:
    if not isinstance(v, dict):
        raise ValueError("geom debe ser un GeoJSON Polygon")
    if v.get("type") != "Polygon":
        raise ValueError("geom.type debe ser 'Polygon'")
    coords = v.get("coordinates")
    if not isinstance(coords, list) or not coords or not isinstance(coords[0], list):
        raise ValueError("geom.coordinates inválidas para Polygon")
    ring = coords[0]
    if len(ring) < 4:
        raise ValueError("El polígono necesita al menos 4 posiciones (anillo cerrado)")
    if ring[0] != ring[-1]:
        raise ValueError("El anillo del polígono debe estar cerrado (primera == última posición)")
    for pos in ring:
        if (not isinstance(pos, (list, tuple)) or len(pos) < 2
                or not isinstance(pos[0], (int, float)) or not isinstance(pos[1], (int, float))):
            raise ValueError("Cada posición debe ser [lon, lat] numéricos")
        if not (-180 <= pos[0] <= 180 and -90 <= pos[1] <= 90):
            raise ValueError("Coordenadas fuera de rango (lon -180..180, lat -90..90)")
    if len(str(v)) > 500_000:
        raise ValueError("Geometría demasiado grande")
    return v


class PotreroCreate(BaseModel):
    nombre: str
    finca: str
    geom: Dict[str, Any]

    _geom = field_validator("geom")(classmethod(lambda cls, v: _validar_polygon_geom(v)))

    @field_validator("nombre")
    @classmethod
    def _nombre_no_vacio(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("requerido")
        if len(v) > 50:
            raise ValueError("máximo 50 caracteres")
        return v

    @field_validator("finca")
    @classmethod
    def _finca_no_vacia(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("requerido")
        if len(v) > 100:
            raise ValueError("máximo 100 caracteres")
        return v


class PotreroUpdate(BaseModel):
    """Renombra / redibuja un potrero propio. La finca la gestiona el
    operador (cambiarla dejaría hijas con finca stale): no se expone."""

    nombre: Optional[str] = None
    geom: Optional[Dict[str, Any]] = None

    _geom = field_validator("geom")(classmethod(lambda cls, v: _validar_polygon_geom(v) if v is not None else v))

    @field_validator("nombre")
    @classmethod
    def _nombre_opt(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("no puede ser vacío")
        if len(v) > 50:
            raise ValueError("máximo 50 caracteres")
        return v


class ParcelaCreate(BaseModel):
    nombre: Optional[str] = None
    estado: str = "optimo"
    geom: Dict[str, Any]

    _geom = field_validator("geom")(classmethod(lambda cls, v: _validar_polygon_geom(v)))

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        if len(v) > 50:
            raise ValueError("máximo 50 caracteres")
        return v

    @field_validator("estado")
    @classmethod
    def _estado(cls, v: str) -> str:
        v = (v or "optimo").strip().lower()
        if v not in ESTADOS_PARCELA:
            raise ValueError(f"estado inválido. Use: {sorted(ESTADOS_PARCELA)}")
        return v


class ParcelaUpdate(BaseModel):
    nombre: Optional[str] = None
    estado: Optional[str] = None
    geom: Optional[Dict[str, Any]] = None

    _geom = field_validator("geom")(classmethod(lambda cls, v: _validar_polygon_geom(v) if v is not None else v))

    @field_validator("nombre")
    @classmethod
    def _nombre_opt(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("no puede ser vacío")
        if len(v) > 50:
            raise ValueError("máximo 50 caracteres")
        return v

    @field_validator("estado")
    @classmethod
    def _estado_opt(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip().lower()
        if v not in ESTADOS_PARCELA:
            raise ValueError(f"estado inválido. Use: {sorted(ESTADOS_PARCELA)}")
        return v


# Categorías de rodeo con peso típico (kg) y consumo sugerido (% PV en MS/día).
# El rodeo guarda sus propios valores (editables): la categoría solo precarga.
CATEGORIAS_RODEO: dict[str, dict[str, object]] = {
    "vaca_lactancia": {"label": "Vaca con cría", "peso": 450.0, "consumo": 2.8},
    "vaca_seca": {"label": "Vaca seca", "peso": 420.0, "consumo": 2.0},
    "vaquillona": {"label": "Vaquillona", "peso": 300.0, "consumo": 2.5},
    "novillo": {"label": "Novillo", "peso": 380.0, "consumo": 2.6},
    "toro": {"label": "Toro", "peso": 650.0, "consumo": 2.0},
    "ternero": {"label": "Ternero/a destete", "peso": 180.0, "consumo": 3.0},
}


def _validar_categoria_rodeo(v: str) -> str:
    v = (v or "").strip().lower()
    if v not in CATEGORIAS_RODEO:
        raise ValueError(f"categoría inválida. Use: {sorted(CATEGORIAS_RODEO)}")
    return v


def _validar_color_rodeo(v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    v = (v or "").strip().lower()
    if not v:
        return None
    if not re.fullmatch(r"#[0-9a-f]{6}", v):
        raise ValueError("color inválido. Use el formato #RRGGBB")
    return v


class RodeoCreate(BaseModel):
    nombre: str
    categoria: str
    cabezas: int
    peso_prom_kg: float
    consumo_pct: Optional[float] = None
    notas: Optional[str] = None
    color: Optional[str] = None

    _categoria = field_validator("categoria")(classmethod(lambda cls, v: _validar_categoria_rodeo(v)))
    _color = field_validator("color")(classmethod(lambda cls, v: _validar_color_rodeo(v)))

    @field_validator("nombre")
    @classmethod
    def _nombre_no_vacio(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("requerido")
        if len(v) > 50:
            raise ValueError("máximo 50 caracteres")
        return v

    @field_validator("cabezas")
    @classmethod
    def _cabezas_min(cls, v: int) -> int:
        if v is None or int(v) < 1:
            raise ValueError("mínimo 1 cabeza")
        return int(v)

    @field_validator("peso_prom_kg")
    @classmethod
    def _peso_positivo(cls, v: float) -> float:
        if v is None or float(v) <= 0:
            raise ValueError("peso positivo requerido")
        return float(v)

    @field_validator("consumo_pct")
    @classmethod
    def _consumo_rango(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        if not 0.5 <= float(v) <= 6.0:
            raise ValueError("consumo entre 0.5 y 6.0 %")
        return float(v)

    @field_validator("notas")
    @classmethod
    def _notas_opt(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        if len(v) > 280:
            raise ValueError("máximo 280 caracteres")
        return v


def _validar_id_positivo(v: int, campo: str) -> int:
    if v is None or int(v) < 1:
        raise ValueError(f"{campo} inválido")
    return int(v)


def _validar_notas_opt(v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    v = v.strip()
    if not v:
        return None
    if len(v) > 280:
        raise ValueError("máximo 280 caracteres")
    return v


class AsignacionUpdate(BaseModel):
    fecha_salida: Optional[date] = None
    notas: Optional[str] = None

    _notas = field_validator("notas")(classmethod(lambda cls, v: _validar_notas_opt(v)))


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

    _rodeo_id = field_validator("rodeo_id")(classmethod(lambda cls, v: _validar_id_positivo(v, "rodeo_id")))

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


class RodeoUpdate(BaseModel):
    nombre: Optional[str] = None
    categoria: Optional[str] = None
    cabezas: Optional[int] = None
    peso_prom_kg: Optional[float] = None
    consumo_pct: Optional[float] = None
    notas: Optional[str] = None
    color: Optional[str] = None

    _categoria = field_validator("categoria")(classmethod(lambda cls, v: _validar_categoria_rodeo(v) if v is not None else v))
    _color = field_validator("color")(classmethod(lambda cls, v: _validar_color_rodeo(v)))

    @field_validator("nombre")
    @classmethod
    def _nombre_opt(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("no puede ser vacío")
        if len(v) > 50:
            raise ValueError("máximo 50 caracteres")
        return v

    @field_validator("cabezas")
    @classmethod
    def _cabezas_opt(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        if int(v) < 1:
            raise ValueError("mínimo 1 cabeza")
        return int(v)

    @field_validator("peso_prom_kg")
    @classmethod
    def _peso_opt(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        if float(v) <= 0:
            raise ValueError("peso positivo requerido")
        return float(v)

    @field_validator("consumo_pct")
    @classmethod
    def _consumo_opt(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        if not 0.5 <= float(v) <= 6.0:
            raise ValueError("consumo entre 0.5 y 6.0 %")
        return float(v)

    @field_validator("notas")
    @classmethod
    def _notas_opt(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        if len(v) > 280:
            raise ValueError("máximo 280 caracteres")
        return v
