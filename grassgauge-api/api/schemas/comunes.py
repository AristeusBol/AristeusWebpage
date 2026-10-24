"""Validadores compartidos por los schemas de la API."""

import re
from typing import Any, Dict, Optional

from dominio.constantes import ESTADOS_PARCELA

MAX_NOMBRE = 50
MAX_FINCA = 100
MAX_NOTAS = 280


def validar_polygon_geom(v: Any) -> Dict[str, Any]:
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


def geom_opcional(v: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    return validar_polygon_geom(v) if v is not None else v


def texto_obligatorio(v: str, max_len: int, campo: str = "nombre") -> str:
    v = (v or "").strip()
    if not v:
        raise ValueError("requerido")
    if len(v) > max_len:
        raise ValueError(f"máximo {max_len} caracteres")
    return v


def texto_opcional_no_vacio(v: Optional[str], max_len: int) -> Optional[str]:
    """None se conserva; un string vacío se rechaza."""
    if v is None:
        return v
    v = v.strip()
    if not v:
        raise ValueError("no puede ser vacío")
    if len(v) > max_len:
        raise ValueError(f"máximo {max_len} caracteres")
    return v


def texto_opcional_a_none(v: Optional[str], max_len: int) -> Optional[str]:
    """None o vacío se normalizan a None (para notas y nombre de parcela)."""
    if v is None:
        return v
    v = v.strip()
    if not v:
        return None
    if len(v) > max_len:
        raise ValueError(f"máximo {max_len} caracteres")
    return v


def validar_estado(v: str) -> str:
    v = (v or "optimo").strip().lower()
    if v not in ESTADOS_PARCELA:
        raise ValueError(f"estado inválido. Use: {sorted(ESTADOS_PARCELA)}")
    return v


def estado_opcional(v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    return validar_estado(v)


def validar_id_positivo(v: int, campo: str) -> int:
    if v is None or int(v) < 1:
        raise ValueError(f"{campo} inválido")
    return int(v)


def validar_color(v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    v = (v or "").strip().lower()
    if not v:
        return None
    if not re.fullmatch(r"#[0-9a-f]{6}", v):
        raise ValueError("color inválido. Use el formato #RRGGBB")
    return v
