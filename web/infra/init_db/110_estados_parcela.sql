-- Parcelas: estados forrajeros renombrados.
-- sobrepastoreo->critico, recuperacion->desarrollo, aceptable->optimo,
-- transicion->maduro, envejecido->pasado. Se elimina por completo el
-- antiguo set del ciclo de vida (activa/descanso/excluida/archivada).
BEGIN;

UPDATE parcelas
SET estado = CASE estado
    WHEN 'sobrepastoreo' THEN 'critico'
    WHEN 'recuperacion'  THEN 'desarrollo'
    WHEN 'aceptable'     THEN 'optimo'
    WHEN 'transicion'    THEN 'maduro'
    WHEN 'envejecido'    THEN 'pasado'
    ELSE estado
END
WHERE estado IN ('sobrepastoreo', 'recuperacion', 'aceptable', 'transicion', 'envejecido');

ALTER TABLE parcelas ALTER COLUMN estado SET DEFAULT 'optimo';

ALTER TABLE parcelas DROP CONSTRAINT IF EXISTS parcelas_estado_valido;
ALTER TABLE parcelas ADD CONSTRAINT parcelas_estado_valido
    CHECK (estado IN ('critico', 'desarrollo', 'optimo', 'maduro', 'pasado'));

COMMIT;