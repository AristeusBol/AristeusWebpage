"""Fragmentos SQL reutilizables.

El filtro de exclusiones se repetía en cada consulta de puntos de mapa_color;
si cambia la semántica (hoy: borde cuenta como dentro, ST_Covers) tiene que
cambiar en un solo lugar.
"""

# Puntos de mapa_color alias `m`, excluyendo los que caen en una zona de
# exclusión del mismo usuario/potrero.
EXCLUIR_PUNTOS_M = """NOT EXISTS (
            SELECT 1 FROM zonas_exclusion z
            WHERE z.usuario_id = m.usuario_id AND z.potrero_id = m.potrero_id
              AND ST_Covers(z.geom, m.geom)
        )"""

# Misma regla para celdas precalculadas alias `mc`.
EXCLUIR_CELDAS_MC = """NOT EXISTS (
            SELECT 1 FROM zonas_exclusion z
            WHERE z.usuario_id = mc.usuario_id AND z.potrero_id = mc.potrero_id
              AND ST_Covers(z.geom, mc.geom)
        )"""

# Variante del motor analítico, que filtra por parámetros :pid/:uid.
EXCLUIR_PUNTOS_PID = """NOT EXISTS (
            SELECT 1 FROM zonas_exclusion z
            WHERE z.potrero_id = :pid AND z.usuario_id = :uid
              AND ST_Covers(z.geom, m.geom)
        )"""
