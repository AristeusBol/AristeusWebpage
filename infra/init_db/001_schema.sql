-- GrassGauge — esquema canónico.
-- Consolida 098..113: base + fotos + titularidad + calidad + email lower +
-- parcelas + rodeos (solo color) + asignaciones + trayectorias.
-- Init fresco: este archivo + 002_seed.sql. Futuros cambios: 003_*.sql.
-- NOTA: datos descartables asumidos al squashear (ver git history 098..113).

CREATE EXTENSION IF NOT EXISTS postgis;

-- Usuarios (email siempre lower; ver 002 seed y api/routers/auth.py)
CREATE TABLE usuarios (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL,
    password_hash VARCHAR(255) NOT NULL
);
CREATE UNIQUE INDEX uq_usuarios_email_lower ON usuarios (lower(email));

-- Potreros: la finca canónica vive acá.
CREATE TABLE potreros_base (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    nombre VARCHAR(50) NOT NULL,
    finca VARCHAR(100) NOT NULL,
    geom geometry(Polygon, 4326) NOT NULL,
    CONSTRAINT uq_potreros_usuario_id UNIQUE (usuario_id, id),
    CONSTRAINT uq_potreros_usuario_finca_nombre UNIQUE (usuario_id, finca, nombre)
);

-- Puntos de densidad (finca denormalizada a propósito: filtros por finca sin JOIN)
CREATE TABLE mapa_color (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    potrero_id INTEGER NOT NULL,
    finca VARCHAR(100) NOT NULL,
    fecha DATE NOT NULL DEFAULT CURRENT_DATE,
    densidad_verde_g_m2 NUMERIC,
    densidad_muerta_g_m2 NUMERIC,
    densidad_total_g_m2 NUMERIC,
    origen VARCHAR(50) NOT NULL DEFAULT 'interpolacion',
    geom geometry(Point, 4326) NOT NULL,
    CONSTRAINT fk_mapa_titularidad FOREIGN KEY (usuario_id, potrero_id)
        REFERENCES potreros_base(usuario_id, id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT ck_mapa_no_negativos CHECK (
        (densidad_verde_g_m2 IS NULL OR densidad_verde_g_m2 >= 0) AND
        (densidad_muerta_g_m2 IS NULL OR densidad_muerta_g_m2 >= 0) AND
        (densidad_total_g_m2 IS NULL OR densidad_total_g_m2 >= 0)),
    CONSTRAINT ck_mapa_total_coherente CHECK (
        densidad_verde_g_m2 IS NULL OR densidad_muerta_g_m2 IS NULL OR densidad_total_g_m2 IS NULL OR
        abs(densidad_total_g_m2 - (densidad_verde_g_m2 + densidad_muerta_g_m2))
            <= 0.05 * GREATEST(densidad_verde_g_m2 + densidad_muerta_g_m2, 1))
);

CREATE TABLE zonas_exclusion (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    potrero_id INTEGER NOT NULL,
    finca VARCHAR(100) NOT NULL,
    nombre VARCHAR(50) NOT NULL,
    tipo VARCHAR(50) NOT NULL,
    geom geometry(Polygon, 4326) NOT NULL,
    CONSTRAINT fk_zonas_titularidad FOREIGN KEY (usuario_id, potrero_id)
        REFERENCES potreros_base(usuario_id, id) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE calculos_stock (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    potrero_id INTEGER NOT NULL,
    finca VARCHAR(100) NOT NULL,
    fecha DATE NOT NULL DEFAULT CURRENT_DATE,
    area_neta_ha NUMERIC,
    masa_seca_verde NUMERIC,
    masa_seca_muerta NUMERIC,
    masa_seca_total NUMERIC NOT NULL,
    CONSTRAINT uq_calculos_usuario_potrero_fecha UNIQUE (usuario_id, potrero_id, fecha),
    CONSTRAINT fk_calculos_titularidad FOREIGN KEY (usuario_id, potrero_id)
        REFERENCES potreros_base(usuario_id, id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT ck_calculos_no_negativos CHECK (
        (area_neta_ha IS NULL OR area_neta_ha >= 0) AND
        (masa_seca_verde IS NULL OR masa_seca_verde >= 0) AND
        (masa_seca_muerta IS NULL OR masa_seca_muerta >= 0) AND
        (masa_seca_total >= 0)
    )
);

CREATE TABLE fotos_calibracion (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    potrero_id INTEGER NOT NULL,
    finca VARCHAR(100) NOT NULL,
    fecha DATE NOT NULL,
    geom geometry(Point, 4326) NOT NULL,
    foto_path TEXT NOT NULL,
    mime VARCHAR(50) NOT NULL DEFAULT 'image/jpeg',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_fotos_titularidad FOREIGN KEY (usuario_id, potrero_id)
        REFERENCES potreros_base(usuario_id, id) ON DELETE CASCADE ON UPDATE CASCADE
);

-- Parcelas: SIN columna finca (patrón modelo: se resuelve por JOIN a potreros_base).
CREATE TABLE parcelas (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    potrero_id INTEGER NOT NULL,
    nombre VARCHAR(50) NOT NULL,
    estado VARCHAR(20) NOT NULL DEFAULT 'optimo',
    geom geometry(Polygon, 4326) NOT NULL,
    CONSTRAINT uq_parcelas_usuario_id UNIQUE (usuario_id, id),
    CONSTRAINT uq_parcelas_usuario_potrero_nombre UNIQUE (usuario_id, potrero_id, nombre),
    CONSTRAINT fk_parcelas_titularidad FOREIGN KEY (usuario_id, potrero_id)
        REFERENCES potreros_base(usuario_id, id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT ck_parcelas_estado CHECK (estado IN ('critico', 'desarrollo', 'optimo', 'maduro', 'pasado')),
    CONSTRAINT ck_parcelas_geom_valida CHECK (ST_IsValid(geom))
);

-- Rodeos: titularidad por usuario; solo color (sin estado/fecha_ingreso: churn 107-109 eliminado).
CREATE TABLE rodeos (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    nombre VARCHAR(50) NOT NULL,
    categoria VARCHAR(30) NOT NULL,
    cabezas INTEGER NOT NULL CHECK (cabezas >= 1),
    peso_prom_kg NUMERIC NOT NULL CHECK (peso_prom_kg > 0),
    consumo_pct NUMERIC NOT NULL DEFAULT 2.5 CHECK (consumo_pct >= 0.5 AND consumo_pct <= 6),
    notas VARCHAR(280),
    color VARCHAR(7),
    CONSTRAINT uq_rodeos_usuario_id UNIQUE (usuario_id, id),
    CONSTRAINT uq_rodeos_usuario_nombre UNIQUE (usuario_id, nombre),
    CONSTRAINT ck_rodeos_categoria CHECK (categoria IN (
        'vaca_lactancia', 'vaca_seca', 'vaquillona', 'novillo', 'toro', 'ternero')),
    CONSTRAINT ck_rodeos_color CHECK (color IS NULL OR color ~ '^#[0-9a-fA-F]{6}$')
);
CREATE UNIQUE INDEX uq_rodeos_usuario_color ON rodeos (usuario_id, color) WHERE color IS NOT NULL;

-- Rotación: ventana de fechas; fecha_salida NULL = abierto.
CREATE TABLE asignaciones (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    rodeo_id INTEGER NOT NULL,
    parcela_id INTEGER NOT NULL,
    fecha_entrada DATE NOT NULL,
    fecha_salida DATE,
    notas VARCHAR(280),
    trayectoria_inicio DATE NOT NULL,
    CONSTRAINT uq_asignaciones_usuario_id UNIQUE (usuario_id, id),
    CONSTRAINT ck_asignaciones_fechas CHECK (fecha_salida IS NULL OR fecha_salida >= fecha_entrada),
    CONSTRAINT fk_asig_rodeo FOREIGN KEY (usuario_id, rodeo_id)
        REFERENCES rodeos(usuario_id, id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_asig_parcela FOREIGN KEY (usuario_id, parcela_id)
        REFERENCES parcelas(usuario_id, id) ON DELETE CASCADE ON UPDATE CASCADE
);

-- Marca de trayectoria finalizada (historial del lote; las etapas no cambian).
CREATE TABLE trayectorias_finalizadas (
    usuario_id INTEGER NOT NULL,
    rodeo_id INTEGER NOT NULL,
    trayectoria_inicio DATE NOT NULL,
    finalizada_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (usuario_id, rodeo_id, trayectoria_inicio),
    CONSTRAINT fk_trayfin_rodeo FOREIGN KEY (usuario_id, rodeo_id)
        REFERENCES rodeos(usuario_id, id) ON DELETE CASCADE ON UPDATE CASCADE
);

-- Índices: solo compuestos con usuario_id + GIST. Se eliminaron los
-- prefijo-duplicados (idx_mapa_color_potrero_fecha, idx_mapa_usuario,
-- idx_calculos_usuario, idx_zonas_potrero_usuario, idx_zonas_usuario,
-- idx_parcelas_usuario, idx_potreros_usuario, idx_rodeos_usuario,
-- idx_asignaciones_usuario): cubiertos por los UNIQUE compuestos o por
-- los compuestos con fecha.
CREATE INDEX idx_potreros_geom ON potreros_base USING GIST (geom);
CREATE INDEX idx_mapa_geom ON mapa_color USING GIST (geom);
CREATE INDEX idx_mapa_usuario_potrero_fecha ON mapa_color (usuario_id, potrero_id, fecha);
CREATE INDEX idx_mapa_usuario_finca_fecha ON mapa_color (usuario_id, finca, fecha);
CREATE INDEX idx_zonas_geom ON zonas_exclusion USING GIST (geom);
CREATE INDEX idx_zonas_usuario_potrero ON zonas_exclusion (usuario_id, potrero_id);
CREATE INDEX idx_calculos_usuario_potrero_fecha ON calculos_stock (usuario_id, potrero_id, fecha);
CREATE INDEX idx_calculos_usuario_finca_fecha ON calculos_stock (usuario_id, finca, fecha);
CREATE INDEX idx_fotos_usuario_potrero ON fotos_calibracion (usuario_id, potrero_id);
CREATE INDEX idx_fotos_geom ON fotos_calibracion USING GIST (geom);
CREATE INDEX idx_parcelas_geom ON parcelas USING GIST (geom);
CREATE INDEX idx_parcelas_usuario_potrero ON parcelas (usuario_id, potrero_id);
CREATE INDEX idx_asignaciones_usuario_fechas ON asignaciones (usuario_id, fecha_entrada, fecha_salida);
CREATE INDEX idx_asignaciones_usuario_rodeo ON asignaciones (usuario_id, rodeo_id);
CREATE INDEX idx_asignaciones_usuario_parcela ON asignaciones (usuario_id, parcela_id);
CREATE INDEX idx_asignaciones_trayectoria ON asignaciones (usuario_id, rodeo_id, trayectoria_inicio);
