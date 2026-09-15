-- Rodeos simplificados: sin estado de vida del lote.
-- Si un grupo se vende/retira, se elimina directamente (sus pastoreos
-- se borran en cascada). El índice de color único por usuario se mantiene.
BEGIN;

ALTER TABLE rodeos DROP CONSTRAINT IF EXISTS rodeos_estado_valido;
ALTER TABLE rodeos DROP COLUMN IF EXISTS estado;

COMMIT;