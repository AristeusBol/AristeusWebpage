"""Cálculos forrajeros reutilizables por routers, repositorios y CLI."""

from typing import Any, Optional

from dominio.conversion import area_m2, densidad_a_kg, densidad_t_ha, t_ha


def consumo_diario(cabezas: Any, peso_prom_kg: Any, consumo_pct: Any) -> Optional[float]:
    """kg MS/día que consume el rodeo: cabezas × peso × %/100."""
    try:
        if cabezas is None or peso_prom_kg is None or consumo_pct is None:
            return None
        return round(int(cabezas) * float(peso_prom_kg) * float(consumo_pct) / 100.0, 1)
    except (TypeError, ValueError):
        return None


def prorrateo(area_parcela_ha: Optional[float], calc) -> dict:
    """Prorratea el cálculo del potrero padre a una parcela por área.

    Retorna dict con masas/t_ha + flag estimado_por_prorrateo.
    """
    if calc is None:
        return {
            "masa_verde_kg": None, "masa_muerta_kg": None, "masa_total_kg": None,
            "t_ha_verde": None, "t_ha_muerta": None, "t_ha_total": None,
            "tiene_calculo": False, "estimado_por_prorrateo": False,
        }
    try:
        area_neta = float(calc.area_neta_ha) if calc.area_neta_ha is not None else 0
    except (TypeError, ValueError):
        area_neta = 0
    if not area_neta or area_neta <= 0 or not area_parcela_ha or area_parcela_ha <= 0:
        return {
            "masa_verde_kg": None, "masa_muerta_kg": None, "masa_total_kg": None,
            "t_ha_verde": t_ha(calc.masa_seca_verde, calc.area_neta_ha),
            "t_ha_muerta": t_ha(calc.masa_seca_muerta, calc.area_neta_ha),
            "t_ha_total": t_ha(calc.masa_seca_total, calc.area_neta_ha),
            "tiene_calculo": calc.masa_seca_total is not None,
            "estimado_por_prorrateo": False,
        }
    ratio = float(area_parcela_ha) / float(area_neta)
    verde = float(calc.masa_seca_verde) * ratio if calc.masa_seca_verde is not None else None
    muerta = float(calc.masa_seca_muerta) * ratio if calc.masa_seca_muerta is not None else None
    total = float(calc.masa_seca_total) * ratio if calc.masa_seca_total is not None else None
    return {
        "masa_verde_kg": verde, "masa_muerta_kg": muerta, "masa_total_kg": total,
        "t_ha_verde": t_ha(calc.masa_seca_verde, calc.area_neta_ha),
        "t_ha_muerta": t_ha(calc.masa_seca_muerta, calc.area_neta_ha),
        "t_ha_total": t_ha(calc.masa_seca_total, calc.area_neta_ha),
        "tiene_calculo": total is not None,
        "estimado_por_prorrateo": total is not None,
    }


def zonal_row_to_dict(n: Any, vmean: Any, mmean: Any, tmean: Any,
                      area_ha: Any, incluir_estimado: bool = True) -> dict:
    """Promedios zonales de una parcela/potrero a masas y t/ha."""
    n = int(n or 0)
    area_ha = float(area_ha) if area_ha is not None else None
    vacio = {
        "masa_verde_kg": None, "masa_muerta_kg": None, "masa_total_kg": None,
        "t_ha_verde": None, "t_ha_muerta": None, "t_ha_total": None,
        "tiene_calculo": False,
        "n_puntos": n, "area_ha": area_ha,
    }
    if incluir_estimado:
        vacio["estimado_zonal"] = False
    if n == 0 or area_ha is None or area_ha <= 0:
        return vacio
    if vmean is None or mmean is None or tmean is None:
        return vacio

    vmean, mmean, tmean = float(vmean), float(mmean), float(tmean)
    superficie_m2 = area_m2(area_ha)
    salida = {
        "masa_verde_kg": densidad_a_kg(vmean, superficie_m2),
        "masa_muerta_kg": densidad_a_kg(mmean, superficie_m2),
        "masa_total_kg": densidad_a_kg(tmean, superficie_m2),
        "t_ha_verde": densidad_t_ha(vmean),
        "t_ha_muerta": densidad_t_ha(mmean),
        "t_ha_total": densidad_t_ha(tmean),
        "densidad_promedio_verde_g_m2": vmean,
        "densidad_promedio_muerta_g_m2": mmean,
        "densidad_promedio_total_g_m2": tmean,
        "tiene_calculo": True,
        "n_puntos": n, "area_ha": area_ha,
    }
    if incluir_estimado:
        salida["estimado_zonal"] = True
    return salida
