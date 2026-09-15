CREATE TABLE IF NOT EXISTS fotos_calibracion (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    potrero_id INTEGER NOT NULL,
    finca VARCHAR(100) NOT NULL,
    fecha DATE NOT NULL,
    geom geometry(Point, 4326) NOT NULL,
    foto_path TEXT NOT NULL,
    mime VARCHAR(50) NOT NULL DEFAULT 'image/jpeg',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (usuario_id, potrero_id) REFERENCES potreros_base(usuario_id, id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_fotos_usuario_potrero ON fotos_calibracion (usuario_id, potrero_id);
CREATE INDEX IF NOT EXISTS idx_fotos_geom ON fotos_calibracion USING GIST (geom);
