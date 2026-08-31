CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE usuarios (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE,
    password_hash VARCHAR(255) NOT NULL
);

CREATE TABLE potreros_base (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    nombre VARCHAR(50) NOT NULL,
    finca VARCHAR(100) NOT NULL,
    geom geometry(Polygon, 4326) NOT NULL
);

CREATE TABLE mapa_color (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    potrero_id INTEGER NOT NULL REFERENCES potreros_base(id) ON DELETE CASCADE,
    finca VARCHAR(100) NOT NULL,
    fecha DATE NOT NULL DEFAULT CURRENT_DATE,
    densidad_verde_g_m2 NUMERIC,
    densidad_muerta_g_m2 NUMERIC,
    densidad_total_g_m2 NUMERIC,
    origen VARCHAR(50) NOT NULL DEFAULT 'interpolacion',
    geom geometry(Point, 4326) NOT NULL
);

CREATE TABLE zonas_exclusion (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    potrero_id INTEGER NOT NULL REFERENCES potreros_base(id) ON DELETE CASCADE,
    finca VARCHAR(100) NOT NULL,
    nombre VARCHAR(50) NOT NULL,
    tipo VARCHAR(50) NOT NULL,
    geom geometry(Polygon, 4326) NOT NULL
);

CREATE TABLE calculos_stock (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    potrero_id INTEGER NOT NULL REFERENCES potreros_base(id) ON DELETE CASCADE,
    finca VARCHAR(100) NOT NULL,
    fecha DATE NOT NULL DEFAULT CURRENT_DATE,
    area_neta_ha NUMERIC,
    masa_seca_verde NUMERIC,
    masa_seca_muerta NUMERIC,
    masa_seca_total NUMERIC NOT NULL,
    UNIQUE (usuario_id, potrero_id, fecha)
);

CREATE INDEX idx_color_geom ON mapa_color USING GIST (geom);
CREATE INDEX idx_mapa_color_potrero_fecha ON mapa_color (potrero_id, fecha);
CREATE INDEX idx_mapa_usuario ON mapa_color (usuario_id);
CREATE INDEX idx_mapa_usuario_potrero_fecha ON mapa_color (usuario_id, potrero_id, fecha);
CREATE INDEX idx_potreros_geom ON potreros_base USING GIST (geom);
CREATE INDEX idx_potreros_usuario ON potreros_base (usuario_id);
CREATE INDEX idx_exclusion_geom ON zonas_exclusion USING GIST (geom);
CREATE INDEX idx_zonas_usuario ON zonas_exclusion (usuario_id);
CREATE INDEX idx_calculos_usuario ON calculos_stock (usuario_id);
CREATE INDEX idx_calculos_usuario_potrero_fecha ON calculos_stock (usuario_id, potrero_id, fecha);
CREATE INDEX idx_mapa_usuario_finca_fecha ON mapa_color (usuario_id, finca, fecha);
CREATE INDEX idx_calculos_usuario_finca_fecha ON calculos_stock (usuario_id, finca, fecha);
CREATE INDEX idx_zonas_potrero_usuario ON zonas_exclusion (potrero_id, usuario_id);
