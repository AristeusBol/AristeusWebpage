-- Rodeos (grupos de animales por categoría/peso) para gestión de consumo.
-- Titularidad simple por usuario (sin geometría: el consumo es cabeza × peso × %).
BEGIN;

CREATE TABLE IF NOT EXISTS rodeos (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    nombre VARCHAR(50) NOT NULL,
    categoria VARCHAR(30) NOT NULL,
    cabezas INTEGER NOT NULL CHECK (cabezas >= 1),
    peso_prom_kg NUMERIC NOT NULL CHECK (peso_prom_kg > 0),
    consumo_pct NUMERIC NOT NULL DEFAULT 2.5 CHECK (consumo_pct >= 0.5 AND consumo_pct <= 6),
    notas VARCHAR(280),
    UNIQUE (usuario_id, nombre),
    CONSTRAINT rodeos_categoria_valida CHECK (categoria IN (
        'vaca_lactancia', 'vaca_seca', 'vaquillona', 'novillo', 'toro', 'ternero'
    ))
);

CREATE INDEX IF NOT EXISTS idx_rodeos_usuario ON rodeos (usuario_id);

COMMIT;
