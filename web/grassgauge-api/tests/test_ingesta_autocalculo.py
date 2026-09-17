"""Auto-cálculo tras ingesta de mapa_color: un grupo (usuario, potrero, fecha)
calcula y guarda; los fallos no voltean a los demás; --sin-calcular y otras
tablas jamás disparan cálculo."""
from datetime import date
from unittest.mock import MagicMock, patch
import sys

import pandas as pd

# geopandas solo se usa en el flujo CLI completo (GeoDataFrame); para estos
# tests unitarios se stubbea y la suite sigue corriendo sin esa dependencia.
sys.modules.setdefault("geopandas", MagicMock())

from motor_analitico import ingestar_csv


def _gdf(filas):
    return pd.DataFrame(filas)


def _res(seed=1):
    return {
        "nombre": "P", "finca": "F", "fecha": date(2026, 9, 1),
        "usuario_id": seed,
        "area_neta_ha": 10.0, "area_neta_m2": 100000.0,
        "densidad_promedio_verde_g_m2": 100.0,
        "densidad_promedio_muerta_g_m2": 50.0,
        "densidad_promedio_total_g_m2": 150.0,
        "masa_total_potrero_verde_kg": 10000.0,
        "masa_total_potrero_muerta_kg": 5000.0,
        "masa_total_potrero_total_kg": 15000.0,
    }


def test_grupos_mapa_agrupa_por_usuario_potrero_fecha():
    gdf = _gdf([
        {"usuario_id": 1, "potrero_id": 2, "fecha": "2026-09-01"},
        {"usuario_id": 1, "potrero_id": 2, "fecha": "2026-09-01"},
        {"usuario_id": 1, "potrero_id": 3, "fecha": "2026-09-01"},
        {"usuario_id": 1, "potrero_id": 2, "fecha": "2026-09-02"},
    ])
    assert sorted(ingestar_csv._grupos_mapa(gdf)) == [
        (1, 2, date(2026, 9, 1)),
        (1, 2, date(2026, 9, 2)),
        (1, 3, date(2026, 9, 1)),
    ]


def test_calcular_grupos_guarda_todos():
    gdf = _gdf([
        {"usuario_id": 1, "potrero_id": 2, "fecha": "2026-09-01"},
        {"usuario_id": 1, "potrero_id": 3, "fecha": "2026-09-01"},
    ])
    eng = MagicMock()
    with patch.object(ingestar_csv, "engine", eng), \
         patch.object(ingestar_csv, "calcular_stock_potrero", return_value=_res()) as calc, \
         patch.object(ingestar_csv.calculos, "upsert_calculo") as upsert:
        ok, fallos = ingestar_csv._calcular_grupos(gdf)
    assert (ok, fallos) == (2, [])
    assert calc.call_count == 2
    assert upsert.call_count == 2
    pids = sorted(c[0][1] for c in upsert.call_args_list)
    assert pids == [2, 3]


def test_calcular_grupos_fallo_no_voltea_resto():
    gdf = _gdf([
        {"usuario_id": 1, "potrero_id": 2, "fecha": "2026-09-01"},
        {"usuario_id": 1, "potrero_id": 3, "fecha": "2026-09-01"},
    ])
    eng = MagicMock()
    with patch.object(ingestar_csv, "engine", eng), \
         patch.object(ingestar_csv, "calcular_stock_potrero", side_effect=[None, _res()]), \
         patch.object(ingestar_csv.calculos, "upsert_calculo") as upsert:
        ok, fallos = ingestar_csv._calcular_grupos(gdf)
    assert ok == 1
    assert len(fallos) == 1
    assert fallos[0][:3] == (1, 2, "2026-09-01")
    assert upsert.call_count == 1
