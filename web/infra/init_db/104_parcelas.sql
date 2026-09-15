-- Parcelas dentro de potreros (gestión predial desde la interfaz).
-- Titularidad compuesta (usuario_id, potrero_id) igual que zonas_exclusion/mapa_color.
BEGIN;

CREATE TABLE IF NOT EXISTS parcelas (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    potrero_id INTEGER NOT NULL,
    nombre VARCHAR(50) NOT NULL,
    estado VARCHAR(20) NOT NULL DEFAULT 'optimo',
    geom geometry(Polygon, 4326) NOT NULL,
    UNIQUE (usuario_id, id),
    UNIQUE (usuario_id, potrero_id, nombre),
    FOREIGN KEY (usuario_id, potrero_id) REFERENCES potreros_base(usuario_id, id) ON DELETE CASCADE,
    CONSTRAINT parcelas_estado_valido CHECK (estado IN ('critico', 'desarrollo', 'optimo', 'maduro', 'pasado'))
);

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'parcelas_geom_valida') THEN
        ALTER TABLE parcelas ADD CONSTRAINT parcelas_geom_valida CHECK (ST_IsValid(geom));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_parcelas_geom ON parcelas USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_parcelas_potrero_usuario ON parcelas (potrero_id, usuario_id);
CREATE INDEX IF NOT EXISTS idx_parcelas_usuario ON parcelas (usuario_id);

COMMIT;
