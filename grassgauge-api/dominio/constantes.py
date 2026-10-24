"""Constantes compartidas del dominio.

Antes vivían dispersas en routers, repositorios y el motor analítico; acá
queda una única definición para evitar que se desincronicen.
"""

# Unidades
M2_POR_HA = 10_000.0
G_POR_KG = 1_000.0
M2_POR_HECTAREA = M2_POR_HA

# Mapa: media celda de 8m (~16x16m sobre grilla de ~10.4m).
MEDIO_LADO_M = 8
BUF_M = 20  # buffer del tile legacy (solo fallback on-the-fly)

# Tolerancias geométricas
SOLAPE_TOL_M2 = 1.0
FUERA_TOL_M2 = 1.0
AREA_MIN_HA = 0.01

# Balance forrajero
UMBRAL_URGENTE = 7.0
UMBRAL_ATENTO = 21.0
UTILIZACION_VALIDA = {40, 50, 60}

# Estados y categorías
ESTADOS_PARCELA = {"critico", "desarrollo", "optimo", "maduro", "pasado"}

CATEGORIAS_RODEO: dict[str, dict[str, object]] = {
    "vaca_lactancia": {"label": "Vaca con cría", "peso": 450.0, "consumo": 2.8},
    "vaca_seca": {"label": "Vaca seca", "peso": 420.0, "consumo": 2.0},
    "vaquillona": {"label": "Vaquillona", "peso": 300.0, "consumo": 2.5},
    "novillo": {"label": "Novillo", "peso": 380.0, "consumo": 2.6},
    "toro": {"label": "Toro", "peso": 650.0, "consumo": 2.0},
    "ternero": {"label": "Ternero/a destete", "peso": 180.0, "consumo": 3.0},
}
