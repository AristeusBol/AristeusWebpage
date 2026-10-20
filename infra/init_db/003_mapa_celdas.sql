-- Celdas precalculadas del mapa de masa seca + caché compartida de tiles MVT.
-- Motivo: el tile construía las celdas (punto -> 16x16m -> ∩ potrero ->
-- − exclusiones) on-the-fly: ~2-7s por tile, ~9s por carga inicial del mapa.
-- Ahora las celdas se generan una vez por ingesta (motor_analitico/
-- precalcular_celdas.py o el hook de ingestar_csv.py) y el tile solo las
-- escanea por índice (~50-150ms); los MVT terminados se cachean.
-- NOTA: en bases ya existentes estas tablas las crea la API al arrancar
-- (repositorios/celdas.py:asegurar_esquema, idempotente).

CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE mapa_celdas (
    id                   INTEGER PRIMARY KEY,  -- id del punto origen (mapa_color.id)
    usuario_id           INTEGER NOT NULL,
    potrero_id           INTEGER NOT NULL,
    finca                VARCHAR(100) NOT NULL,
    fecha                DATE NOT NULL,
    geom                 geometry(MultiPolygon, 3857) NOT NULL,
    densidad_verde_g_m2  NUMERIC,
    densidad_muerta_g_m2 NUMERIC,
    densidad_total_g_m2  NUMERIC
);

CREATE INDEX idx_celdas_geom ON mapa_celdas USING GIST (geom);
CREATE INDEX idx_celdas_usuario_finca_fecha ON mapa_celdas (usuario_id, finca, fecha);
-- Compuesto (btree_gist): igualdad de grupo + filtro espacial en un solo
-- Index Cond (evita escanear las 12 fechas y descartar ~400k filas).
CREATE INDEX idx_celdas_grupo_geom ON mapa_celdas USING GIST (usuario_id, finca, fecha, geom);

-- Caché de tiles MVT ya renderizados (NULL = tile vacío cacheado).
-- Se invalida por (usuario, finca, fecha) al re-ingerir datos y se poda
-- a los 7 días (lo que sale de la caché se regenera en ~100ms).
CREATE TABLE mapa_tiles_cache (
    usuario_id INTEGER NOT NULL,
    finca      VARCHAR(100) NOT NULL,
    fecha      DATE NOT NULL,
    tipo       VARCHAR(10) NOT NULL,
    z          SMALLINT NOT NULL,
    x          INTEGER NOT NULL,
    y          INTEGER NOT NULL,
    mvt        BYTEA,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (usuario_id, finca, fecha, tipo, z, x, y)
);

CREATE INDEX idx_tiles_cache_created ON mapa_tiles_cache (created_at);
