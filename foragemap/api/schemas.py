from typing import Any, Dict, Optional

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


ESTADOS_PARCELA = {"activa", "descanso", "excluida", "archivada"}


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

    @field_validator("nombre", "finca")
    @classmethod
    def _no_vacio(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("requerido")
        if len(v) > 100:
            raise ValueError("máximo 100 caracteres")
        return v


class PotreroUpdate(BaseModel):
    nombre: Optional[str] = None
    finca: Optional[str] = None
    geom: Optional[Dict[str, Any]] = None

    _geom = field_validator("geom")(classmethod(lambda cls, v: _validar_polygon_geom(v) if v is not None else v))

    @field_validator("nombre", "finca")
    @classmethod
    def _no_vacio_opt(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("no puede ser vacío")
        if len(v) > 100:
            raise ValueError("máximo 100 caracteres")
        return v


class ParcelaCreate(BaseModel):
    nombre: str
    estado: str = "activa"
    geom: Dict[str, Any]

    _geom = field_validator("geom")(classmethod(lambda cls, v: _validar_polygon_geom(v)))

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("requerido")
        if len(v) > 50:
            raise ValueError("máximo 50 caracteres")
        return v

    @field_validator("estado")
    @classmethod
    def _estado(cls, v: str) -> str:
        v = (v or "activa").strip().lower()
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
