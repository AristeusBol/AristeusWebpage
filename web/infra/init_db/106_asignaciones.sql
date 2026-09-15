-- Rotación: qué rodeo pasta en qué parcela, con ventana de fechas.
-- fecha_salida NULL = pastoreo abierto (sigue vigente hoy).
BEGIN;

-- La FK compuesta (usuario_id, rodeo_id) exige unicidad compuesta en rodeos
-- (mismo patrón que parcelas.UNIQUE (usuario_id, id)).
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'rodeos_usuario_id_id_key'
    ) THEN
        ALTER TABLE rodeos ADD CONSTRAINT rodeos_usuario_id_id_key UNIQUE (usuario_id, id);
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS asignaciones (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    rodeo_id INTEGER NOT NULL,
    parcela_id INTEGER NOT NULL,
    fecha_entrada DATE NOT NULL,
    fecha_salida DATE,
    notas VARCHAR(280),
    UNIQUE (usuario_id, id),
    CONSTRAINT asignaciones_fechas CHECK (fecha_salida IS NULL OR fecha_salida >= fecha_entrada),
    FOREIGN KEY (usuario_id, rodeo_id) REFERENCES rodeos(usuario_id, id) ON DELETE CASCADE,
    FOREIGN KEY (usuario_id, parcela_id) REFERENCES parcelas(usuario_id, id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_asignaciones_usuario ON asignaciones (usuario_id);
CREATE INDEX IF NOT EXISTS idx_asignaciones_fechas ON asignaciones (usuario_id, fecha_entrada, fecha_salida);
CREATE INDEX IF NOT EXISTS idx_asignaciones_rodeo ON asignaciones (usuario_id, rodeo_id);
CREATE INDEX IF NOT EXISTS idx_asignaciones_parcela ON asignaciones (usuario_id, parcela_id);

COMMIT;