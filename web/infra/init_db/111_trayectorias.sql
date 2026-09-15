-- Trayectorias independientes: agrupa las asignaciones de un lote en
-- ventanas de 7 días (cada trayectoria = su propio grupo). El inicio de la
-- ventana queda en trayectoria_inicio (date). NULL solo para filas legadas
-- antes de esta migración (se backfillean de forma determinística).
BEGIN;

-- Columna opcional para que el backfill viejo conviva con lo nuevo siempre.
ALTER TABLE asignaciones ADD COLUMN IF NOT EXISTS trayectoria_inicio DATE;

-- Backfill: agrupa las filas existentes por lote en corridas contiguas.
-- Nueva corrida cuando no hay fila anterior, cuando hay un hueco (prev.salida
-- < entrada - 1) o cuando la fila anterior cerró en domingo (la trayectoria
-- termina un domingo y la siguiente arranca el lunes).
WITH orden AS (
    SELECT id, usuario_id, rodeo_id, fecha_entrada, fecha_salida,
           LAG(fecha_salida) OVER w AS prev_salida,
           ROW_NUMBER() OVER w AS rn
    FROM asignaciones
    WINDOW w AS (PARTITION BY usuario_id, rodeo_id ORDER BY fecha_entrada, id)
),
marcas AS (
    SELECT *,
           CASE
               WHEN prev_salida IS NULL THEN 1
               WHEN prev_salida < fecha_entrada - 1 THEN 1
               WHEN EXTRACT(DOW FROM prev_salida) = 0 THEN 1
               ELSE 0
           END AS empieza
    FROM orden
),
grupos AS (
    SELECT *,
           SUM(empieza) OVER (PARTITION BY usuario_id, rodeo_id ORDER BY fecha_entrada, id) AS grp
    FROM marcas
),
inicios AS (
    SELECT usuario_id, rodeo_id, grp, MIN(fecha_entrada) AS inicio
    FROM grupos
    GROUP BY usuario_id, rodeo_id, grp
)
UPDATE asignaciones AS a
SET trayectoria_inicio = i.inicio
FROM grupos g
JOIN inicios i USING (usuario_id, rodeo_id, grp)
WHERE a.id = g.id;

CREATE INDEX IF NOT EXISTS idx_asignaciones_trayectoria
    ON asignaciones (usuario_id, rodeo_id, trayectoria_inicio);

COMMIT;