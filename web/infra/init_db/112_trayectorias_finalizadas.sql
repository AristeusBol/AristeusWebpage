-- Rotaciones finalizadas: una marca por trayectoria (grupo identificado por
-- trayectoria_inicio) que mueve la trayectoria al historial del lote.
-- La Fila de etapas en asignaciones no cambia: es solo un marcador.
BEGIN;

CREATE TABLE IF NOT EXISTS trayectorias_finalizadas (
    usuario_id integer NOT NULL,
    rodeo_id integer NOT NULL,
    trayectoria_inicio date NOT NULL,
    finalizada_en timestamp NOT NULL DEFAULT now(),
    PRIMARY KEY (usuario_id, rodeo_id, trayectoria_inicio),
    FOREIGN KEY (usuario_id, rodeo_id) REFERENCES rodeos(usuario_id, id) ON DELETE CASCADE
);

COMMIT;