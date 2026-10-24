"""Celdas precalculadas del mapa de masa seca + caché compartida de tiles.

Problema que resuelve: el tile MVT de `/api/mapa/tiles/...` construía las
celdas de densidad (punto -> cuadrado 16x16m -> ∩ potrero -> − exclusiones)
on-the-fly por tile: ~2-7s por tile, ~9s por carga inicial del mapa.

Acá esas celdas se materializan UNA vez por ingesta en `mapa_celdas`
(geometría ya recortada y en 3857), y el tile pasa a ser un escaneo por
índice GIST + ST_AsMVT (~50-150ms). Los bytes MVT terminados se cachean
además en `mapa_tiles_cache` (compartida entre workers de uvicorn).

Semántica reproducida 1:1 del query viejo (ver api/routers/mapa.py):
  - dedupe por coordenada (DISTINCT ON x,y con desempate por potrero_id, id):
    dos lotes vecinos pueden compartir el punto exacto del borde;
  - descarta puntos cuyo centro cae dentro de una zona de exclusión
    (ST_Covers, borde = dentro);
  - celda = ST_Expand(8m) ∩ potrero, y si choca con la unión de
    exclusiones de la FINCA se le resta (no por potrero: el query viejo
    restaba la unión finca-entera, se mantiene igual).

Nota de equivalencia: el dedupe viejo era por (x, y, tipo) — un punto con
densidad NULL "cedía" la coordenada al siguiente potrero para ese tipo. Acá
el ganador se elige sin mirar valores. Coincide siempre que las tres
densidades estén completas, que es lo único que admite la ingesta
(`_validar_completitud` en ingestar_csv.py rechaza celdas vacías), y en los
datos actuales no hay coordenadas compartidas entre lotes.
"""

from datetime import date
import hashlib
from typing import Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from dominio.constantes import MEDIO_LADO_M as _MEDIO_LADO_M
from repositorios.sql import EXCLUIR_CELDAS_MC

# ---------------------------------------------------------------------------
# Esquema
# ---------------------------------------------------------------------------

DDL = [
    # El índice compuesto de mapa_celdas usa btree_gist: la extensión va primero.
    "CREATE EXTENSION IF NOT EXISTS btree_gist",
    """
    CREATE TABLE IF NOT EXISTS mapa_celdas (
        id                   INTEGER PRIMARY KEY,  -- id del punto origen (mapa_color.id)
        usuario_id           INTEGER NOT NULL,
        potrero_id           INTEGER NOT NULL,
        finca                VARCHAR(100) NOT NULL,
        fecha                DATE NOT NULL,
        geom                 geometry(MultiPolygon, 3857) NOT NULL,
        densidad_verde_g_m2  NUMERIC,
        densidad_muerta_g_m2 NUMERIC,
        densidad_total_g_m2  NUMERIC
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_celdas_geom ON mapa_celdas USING GIST (geom)",
    "CREATE INDEX IF NOT EXISTS idx_celdas_usuario_finca_fecha ON mapa_celdas (usuario_id, finca, fecha)",
    # Índice compuesto: resuelve igualdad de grupo + filtro espacial en un solo
    # Index Cond. Con los dos índices sueltos, PG escaneaba por GIST las 12
    # fechas y descartaba ~400k filas por filtro (112ms -> 85ms, 606 vs 19740
    # heap blocks).
    "CREATE INDEX IF NOT EXISTS idx_celdas_grupo_geom ON mapa_celdas USING GIST (usuario_id, finca, fecha, geom)",
    """
    CREATE TABLE IF NOT EXISTS mapa_tiles_cache (
        usuario_id INTEGER NOT NULL,
        finca      VARCHAR(100) NOT NULL,
        fecha      DATE NOT NULL,
        tipo       VARCHAR(10) NOT NULL,
        z          SMALLINT NOT NULL,
        x          INTEGER NOT NULL,
        y          INTEGER NOT NULL,
        mvt        BYTEA,                 -- NULL = tile vacío (cacheado también)
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (usuario_id, finca, fecha, tipo, z, x, y)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_tiles_cache_created ON mapa_tiles_cache (created_at)",
]


def asegurar_esquema(engine) -> None:
    """Crea tablas/índices si no existen (idempotente; también sirve para BDs
    vivas que ya pasaron por 001_schema.sql sin estas tablas).

    Varios workers de uvicorn lo llaman al arrancar: las carreras de
    "ya existe" (42P07/42710) se ignoran; el resto se propaga.
    """
    duplicado = {"42P07", "42710", "42P06", "23505"}
    # engine.begin() (no connect()): el DDL de PG es transaccional y sin
    # commit explícito el CREATE se revierte al cerrar la conexión.
    with engine.begin() as conn:
        for stmt in DDL:
            # SAVEPOINT por sentencia: en PG un error aborta la transacción
            # entera, y con varios workers corriendo el DDL a la vez algún
            # "ya existe" es esperable.
            try:
                with conn.begin_nested():
                    conn.execute(text(stmt))
            except Exception as e:  # noqa: BLE001 - solo nos importa el código pg
                pgcode = getattr(getattr(e, "orig", None), "pgcode", None)
                if pgcode not in duplicado:
                    raise


# ---------------------------------------------------------------------------
# Precálculo de celdas
# ---------------------------------------------------------------------------

# INSERT…SELECT que replica la construcción de celdas del query viejo de tiles.
# Los CTE van MATERIALIZED a propósito: si PG aplana los subqueries, reescribe
# el CASE/ST_Intersection del SELECT de salida dentro del Filter y lo evalúa
# ~9 veces por fila (con un ST_Transform(potreros_base.geom) incluido en cada
# una): 6s -> 43s. Materializado, cada expresión cara corre una sola vez.
_SQL_PRECALCULAR = """
    WITH puntos AS MATERIALIZED (
        SELECT DISTINCT ON (ST_X(mc.geom), ST_Y(mc.geom))
               mc.id, mc.usuario_id, mc.potrero_id, mc.finca, mc.fecha,
               mc.densidad_verde_g_m2, mc.densidad_muerta_g_m2, mc.densidad_total_g_m2,
               ST_Transform(mc.geom, 3857) AS g
        FROM mapa_color mc
        WHERE mc.usuario_id = :uid
          AND mc.finca = :finca
          AND {cond_fecha}
          AND {excluir}
        ORDER BY ST_X(mc.geom), ST_Y(mc.geom), mc.potrero_id, mc.id
    ),
    lotes AS MATERIALIZED (
        SELECT id, ST_Transform(geom, 3857) AS g
        FROM potreros_base
        WHERE usuario_id = :uid AND finca = :finca
    ),
    excl AS MATERIALIZED (
        SELECT finca, ST_Union(ST_Transform(geom, 3857)) AS u
        FROM zonas_exclusion
        WHERE usuario_id = :uid AND finca = :finca
        GROUP BY finca
    ),
    recortadas AS MATERIALIZED (
        -- Recorte real al lote (igual que el query viejo): solo filtrar por
        -- intersección dejaría la celda sobresaliendo ~2% del área sobre el
        -- borde del potrero. La vacía por no tocar el lote la baja el filtro
        -- de abajo, igual que en el viejo.
        SELECT p.id, p.usuario_id, p.potrero_id, p.finca, p.fecha,
               p.densidad_verde_g_m2, p.densidad_muerta_g_m2, p.densidad_total_g_m2,
               ST_Intersection(ST_Expand(p.g, :medio_lado), l.g) AS cel,
               e.u AS u
        FROM puntos p
        JOIN lotes l ON l.id = p.potrero_id
        LEFT JOIN excl e ON e.finca = p.finca
    ),
    celdas AS MATERIALIZED (
        SELECT r.id, r.usuario_id, r.potrero_id, r.finca, r.fecha,
               r.densidad_verde_g_m2, r.densidad_muerta_g_m2, r.densidad_total_g_m2,
               -- CollectionExtract baja los recortes que quedan solo en
               -- líneas/puntos (borde del potrero): no son superficie.
               ST_CollectionExtract(
                   CASE WHEN r.u IS NOT NULL AND ST_Intersects(r.cel, r.u)
                        THEN ST_Difference(r.cel, r.u)
                        ELSE r.cel END,
                   3
               ) AS geom
        FROM recortadas r
    )
    INSERT INTO mapa_celdas (id, usuario_id, potrero_id, finca, fecha, geom,
                             densidad_verde_g_m2, densidad_muerta_g_m2, densidad_total_g_m2)
    SELECT id, usuario_id, potrero_id, finca, fecha, ST_Multi(geom),
           densidad_verde_g_m2, densidad_muerta_g_m2, densidad_total_g_m2
    FROM celdas
    WHERE geom IS NOT NULL
      AND NOT ST_IsEmpty(geom)
      AND ST_GeometryType(geom) IN ('ST_Polygon', 'ST_MultiPolygon')
"""


def _borrar_grupo(conn: Connection, tabla: str, uid: int, finca: str,
                  fecha: Optional[date] = None) -> None:
    params: dict = {"uid": uid, "finca": finca}
    cond = ""
    if fecha is not None:
        params["fecha"] = fecha
        cond = " AND fecha = :fecha"
    conn.execute(
        text(f"DELETE FROM {tabla} WHERE usuario_id = :uid AND finca = :finca{cond}"),
        params,
    )


def precalcular_grupo(conn: Connection, uid: int, finca: str, fecha: Optional[date] = None) -> int:
    """Regenera las celdas de un grupo (usuario, finca[, fecha]).

    Borra primero todo el grupo (el dedupe por coordenada es cruzado entre
    potreros: si cambió una exclusión puede ganar otro punto del borde) y
    reinserta. Devuelve la cantidad de celdas generadas.
    """
    # El motor pone statement_timeout=30s (para no colgar los tiles); acá no
    # aplica: generar ~209k celdas clippeadas tarda ~10-40s por fecha.
    # SET LOCAL vive solo en esta transacción (los llamadores usan engine.begin()).
    try:
        conn.execute(text("SET LOCAL statement_timeout = '600s'"))
    except Exception:  # noqa: BLE001 - sin transacción queda solo un warning de PG
        pass
    _borrar_grupo(conn, "mapa_celdas", uid, finca, fecha)
    params: dict = {"uid": uid, "finca": finca, "medio_lado": _MEDIO_LADO_M}
    if fecha is not None:
        params["fecha"] = fecha
    # Condición de fecha armada en Python (psycopg no infiere tipos de
    # parámetros comparados contra NULL; ver _cond_fecha).
    sql = (_SQL_PRECALCULAR
           .replace("{cond_fecha}", "mc.fecha = :fecha" if fecha is not None else "TRUE")
           .replace("{excluir}", EXCLUIR_CELDAS_MC))
    res = conn.execute(text(sql), params)
    return int(res.rowcount or 0)


# ---------------------------------------------------------------------------
# Caché de tiles MVT
# ---------------------------------------------------------------------------


def leer_tile_cache(conn: Connection, uid: int, finca: str, fecha: date,
                    tipo: str, z: int, x: int, y: int) -> Optional[bytes]:
    """None si no hay cacheado; b'' si el tile está cacheado como vacío."""
    row = conn.execute(
        text("""
            SELECT mvt FROM mapa_tiles_cache
            WHERE usuario_id = :uid AND finca = :finca AND fecha = :fecha
              AND tipo = :tipo AND z = :z AND x = :x AND y = :y
        """),
        {"uid": uid, "finca": finca, "fecha": fecha, "tipo": tipo, "z": z, "x": x, "y": y},
    ).fetchone()
    if row is None:
        return None
    if row[0] is None:
        return b""
    mvt = row[0]
    return bytes(mvt) if not isinstance(mvt, bytes) else mvt


def guardar_tile_cache(conn: Connection, uid: int, finca: str, fecha: date,
                       tipo: str, z: int, x: int, y: int, mvt: bytes) -> None:
    """Upsert. Un tile vacío se cachea como NULL (también evita recalcularlo)."""
    conn.execute(
        text("""
            INSERT INTO mapa_tiles_cache (usuario_id, finca, fecha, tipo, z, x, y, mvt)
            VALUES (:uid, :finca, :fecha, :tipo, :z, :x, :y, :mvt)
            ON CONFLICT (usuario_id, finca, fecha, tipo, z, x, y)
            DO UPDATE SET mvt = EXCLUDED.mvt, created_at = now()
        """),
        {"uid": uid, "finca": finca, "fecha": fecha, "tipo": tipo,
         "z": z, "x": x, "y": y, "mvt": mvt or None},
    )


def _clave_lock_tile(uid: int, finca: str, fecha: date, tipo: str,
                     z: int, x: int, y: int) -> int:
    """Entero de 64 bits CON SIGNO para pg_advisory_lock(bigint).

    El digest es de 8 bytes; interpretarlo sin signo da valores > 2^63 que
    psycopg manda como `numeric` y PG rechaza (no hay pg_advisory_lock(numeric)).
    """
    crudo = f"{uid}|{finca}|{fecha.isoformat()}|{tipo}|{z}|{x}|{y}"
    return int.from_bytes(hashlib.blake2b(crudo.encode(), digest_size=8).digest(), "big", signed=True)


def tomar_lock_tile(conn: Connection, uid: int, finca: str, fecha: date, tipo: str,
                    z: int, x: int, y: int) -> None:
    """Lock a nivel BD (funciona entre los 4 workers de uvicorn).

    Sin esto, dos workers que piden el mismo tile frío lo calculan los dos
    (~1.4s el pico del z13 grande). OJO: hay que soltarlo con `soltar_lock_tile`
    o al cerrar la conexión (los advisory locks son por sesión).
    """
    conn.execute(text("SELECT pg_advisory_lock(:k)"), {"k": _clave_lock_tile(uid, finca, fecha, tipo, z, x, y)})


def soltar_lock_tile(conn: Connection, uid: int, finca: str, fecha: date, tipo: str,
                     z: int, x: int, y: int) -> None:
    conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": _clave_lock_tile(uid, finca, fecha, tipo, z, x, y)})


def invalidar_cache_tiles(conn: Connection, uid: int, finca: str,
                          fecha: Optional[date] = None) -> None:
    """Tras re-ingerir datos: sin tiles cacheados de ese grupo (cualquier zoom/tipo)."""
    _borrar_grupo(conn, "mapa_tiles_cache", uid, finca, fecha)


def podar_cache_tiles(conn: Connection, dias: int = 7) -> int:
    """Borra tiles cacheados viejos (la data se regenera, no hace falta eterno)."""
    res = conn.execute(
        text("DELETE FROM mapa_tiles_cache WHERE created_at < now() - (interval '1 day' * :dias)"),
        {"dias": dias},
    )
    return int(res.rowcount or 0)


def celdas_disponibles(conn: Connection, uid: int, finca: str, fecha: date) -> bool:
    """¿Este grupo ya tiene celdas precalculadas? Si no, el endpoint usa el query viejo."""
    row = conn.execute(
        text("""
            SELECT 1 FROM mapa_celdas
            WHERE usuario_id = :uid AND finca = :finca AND fecha = :fecha
            LIMIT 1
        """),
        {"uid": uid, "finca": finca, "fecha": fecha},
    ).fetchone()
    return row is not None


def limpiar_celdas(conn: Connection, uid: int, finca: str, fecha: Optional[date] = None) -> None:
    """Fuerza el fallback al query viejo (p. ej. si el precalculo falló a medio camino)."""
    _borrar_grupo(conn, "mapa_celdas", uid, finca, fecha)
