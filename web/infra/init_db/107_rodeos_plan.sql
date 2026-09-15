-- Rodeos, plan ganadero: color fijo por lote (mapa de trayectorias),
-- estado de vida del lote y fecha de ingreso a la categoría.
BEGIN;

ALTER TABLE rodeos ADD COLUMN IF NOT EXISTS color VARCHAR(7);
ALTER TABLE rodeos ADD COLUMN IF NOT EXISTS estado VARCHAR(16) NOT NULL DEFAULT 'activo';
ALTER TABLE rodeos ADD COLUMN IF NOT EXISTS fecha_ingreso DATE;

-- Color único por usuario (nullable: sin color usa la paleta automática).
CREATE UNIQUE INDEX IF NOT EXISTS uq_rodeos_usuario_color
    ON rodeos (usuario_id, color) WHERE color IS NOT NULL;

ALTER TABLE rodeos DROP CONSTRAINT IF EXISTS rodeos_color_ok;
ALTER TABLE rodeos ADD CONSTRAINT rodeos_color_ok
    CHECK (color IS NULL OR color ~ '^#[0-9a-fA-F]{6}$');

ALTER TABLE rodeos DROP CONSTRAINT IF EXISTS rodeos_estado_valido;
ALTER TABLE rodeos ADD CONSTRAINT rodeos_estado_valido
    CHECK (estado IN ('activo', 'engorda', 'vendido', 'encerrado'));

COMMIT;