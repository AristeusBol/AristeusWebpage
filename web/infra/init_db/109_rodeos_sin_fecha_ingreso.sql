-- Rodeos: se quita la fecha de ingreso del lote.
-- La vida del grupo queda capturada en las asignaciones de rotación
-- (fecha_entrada / fecha_salida por parcela).
BEGIN;

ALTER TABLE rodeos DROP COLUMN IF EXISTS fecha_ingreso;

COMMIT;