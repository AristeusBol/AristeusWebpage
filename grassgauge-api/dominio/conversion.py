"""Conversiones de unidades y normalización de valores de la base.

Las fórmulas de masa forrajera estaban repetidas en varios routers con
literales 1000/10000. Acá viven una sola vez.
"""

from typing import Any, Optional

from dominio.constantes import G_POR_KG, M2_POR_HA


def a_float(valor: Any) -> Optional[float]:
    """float(valor) si no es None; None en caso contrario."""
    if valor is None:
        return None
    return float(valor)


def a_iso(valor: Any) -> Optional[str]:
    """Fecha/datetime a string ISO; tolera valores ya serializados."""
    if valor is None:
        return None
    return valor.isoformat() if hasattr(valor, "isoformat") else str(valor)


def area_m2(area_ha: Optional[float]) -> Optional[float]:
    if area_ha is None:
        return None
    return float(area_ha) * M2_POR_HA


def t_ha(masa_kg: Any, area_ha: Any) -> Optional[float]:
    """Toneladas por hectárea a partir de kg y hectáreas."""
    try:
        if masa_kg is None or area_ha is None or float(area_ha) <= 0:
            return None
        return float(masa_kg) / G_POR_KG / float(area_ha)
    except (TypeError, ValueError):
        return None


def densidad_t_ha(densidad_g_m2: Any) -> Optional[float]:
    """g/m² a t/ha (1 g/m² = 0.01 t/ha)."""
    if densidad_g_m2 is None:
        return None
    return float(densidad_g_m2) * 0.01


def densidad_a_kg(densidad_g_m2: Any, area_m2_valor: Any) -> Optional[float]:
    """Densidad (g/m²) por superficie (m²) a kg de materia seca."""
    if densidad_g_m2 is None or area_m2_valor is None:
        return None
    return float(densidad_g_m2) * float(area_m2_valor) / G_POR_KG


def kg_a_t(kg: Any) -> Optional[float]:
    if kg is None:
        return None
    return float(kg) / G_POR_KG
