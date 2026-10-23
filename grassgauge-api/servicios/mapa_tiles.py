"""Render y caché de tiles MVT del mapa de densidad."""

from collections import OrderedDict
from datetime import date
import random
import threading
import time
from typing import Optional

from fastapi.responses import Response
from sqlalchemy import text

from core.db import engine
from dominio.constantes import BUF_M, MEDIO_LADO_M
from repositorios import celdas as repo_celdas
from repositorios.sql import EXCLUIR_CELDAS_MC

COL_DENSIDAD = {
    "verde": "densidad_verde_g_m2",
    "muerta": "densidad_muerta_g_m2",
    "total": "densidad_total_g_m2",
}
TIPOS_VALIDOS = set(COL_DENSIDAD.keys())

# Caché en proceso (por worker): LRU con TTL. El TTL importa: al re-ingerir
# datos se invalida `mapa_tiles_cache` (BD compartida), pero este mapa vivo
# no se entera, y sin vencimiento serviría el MVT viejo hasta la eviction.
_LRU_MAX = 128
_LRU_TTL_S = 300.0
_lru: "OrderedDict[tuple, tuple]" = OrderedDict()  # clave -> (creado_en, mvt)
_lru_lock = threading.Lock()


def _lru_get(clave: tuple) -> Optional[bytes]:
    with _lru_lock:
        entrada = _lru.get(clave)
        if entrada is None:
            return None
        creado, mvt = entrada
        if time.time() - creado > _LRU_TTL_S:
            _lru.pop(clave, None)
            return None
        _lru.move_to_end(clave)
        return mvt


def _lru_put(clave: tuple, valor: bytes) -> None:
    with _lru_lock:
        _lru[clave] = (time.time(), valor)
        _lru.move_to_end(clave)
        while len(_lru) > _LRU_MAX:
            _lru.popitem(last=False)


# ¿El grupo (uid, finca, fecha) ya tiene celdas precalculadas? Se cachea un
# rato para no hacer un SELECT por cada tile del viewport.
_disp: dict[tuple, tuple] = {}
_disp_lock = threading.Lock()
_DISP_TTL_S = 60.0


def _celdas_listas(uid: int, finca: str, fecha: date) -> bool:
    clave = (uid, finca, fecha)
    ahora = time.time()
    with _disp_lock:
        hit = _disp.get(clave)
        if hit and hit[1] > ahora:
            return bool(hit[0])
    try:
        with engine.connect() as conn:
            ok = repo_celdas.celdas_disponibles(conn, uid, finca, fecha)
    except Exception:
        # Sin tabla de celdas (migración aún no aplicada): query viejo.
        ok = False
    with _disp_lock:
        _disp[clave] = (ok, ahora + _DISP_TTL_S)
    return ok


def _bordes_mvt(row) -> Optional[bytes]:
    if row is None or row[0] is None:
        return b""
    mvt = row[0]
    if isinstance(mvt, memoryview):
        return mvt.tobytes()
    if isinstance(mvt, str):
        return mvt.encode()
    return bytes(mvt)


def _tile_celdas(conn, uid: int, finca: str, fecha: date, z: int, x: int, y: int, columna: str) -> bytes:
    """Ruta rápida: celdas ya recortadas, solo escaneo GIST/btree + ST_AsMVT.

    `rec` MATERIALIZED: sin eso PG reevaluaría ST_AsMVTGeom en cada predicado
    del filtro de afuera (2-3 veces por celda). `env` NO va materializado a
    propósito: inlineado, el planner ve el envelope como constante y usa el
    índice (usuario, finca, fecha): 348ms -> 112ms en el tile z13 más grande.
    """
    row = conn.execute(
        text(f"""
            WITH env AS (
                SELECT ST_TileEnvelope(:z, :x, :y) AS tile
            ),
            rec AS MATERIALIZED (
                SELECT ST_AsMVTGeom(c.geom, e.tile, 4096, 0, true) AS geom,
                       c.{columna} AS valor
                FROM mapa_celdas c, env e
                WHERE c.usuario_id = :uid
                  AND c.finca = :finca
                  AND c.fecha = :fecha
                  AND c.{columna} IS NOT NULL
                  AND c.geom && e.tile
            )
            SELECT ST_AsMVT(m, 'densidad', 4096, 'geom')
            FROM (SELECT geom, valor FROM rec WHERE geom IS NOT NULL AND NOT ST_IsEmpty(geom)) m
        """),
        {"z": z, "x": x, "y": y, "uid": uid, "finca": finca, "fecha": fecha},
    ).fetchone()
    return _bordes_mvt(row)


def _tile_legacy(conn, uid: int, finca: str, fecha: date, z: int, x: int, y: int, columna: str) -> bytes:
    """Fallback on-the-fly (celdas construidas por tile). Para grupos sin
    precalcular, p. ej. tras una ingesta con el hook desactivado."""
    sql = text(f"""
        WITH env AS (
            SELECT ST_TileEnvelope(:z, :x, :y) AS tile,
                    ST_Expand(ST_TileEnvelope(:z, :x, :y), :buf) AS tile_buf
        ),
        exc AS (
            SELECT ST_Union(ST_Transform(geom, 3857)) AS u
            FROM zonas_exclusion
            WHERE usuario_id = :uid AND finca = :finca
        ),
        pts AS (
            -- DISTINCT solo por coordenada (sin potrero_id): la grilla es
            -- regular y dos lotes vecinos pueden compartir el punto exacto
            -- del borde; así se evita dibujar dos celdas superpuestas.
            SELECT DISTINCT ON (ST_X(mc.geom), ST_Y(mc.geom))
                mc.id AS id,
                mc.potrero_id AS potrero_id,
                {columna} AS valor,
                ST_Transform(mc.geom, 3857) AS g
            FROM mapa_color mc, env
            WHERE mc.usuario_id = :uid
              AND mc.finca = :finca
              AND mc.fecha = :fecha
              AND {columna} IS NOT NULL
              -- Prefiltro barato con índice GIST (idx_mapa_geom); el chequeo
              -- exacto con ST_Transform va después.
              AND mc.geom && ST_Transform(env.tile_buf, 4326)
              AND ST_Intersects(
                    ST_Transform(mc.geom, 3857),
                    env.tile_buf
                  )
              AND {EXCLUIR_CELDAS_MC}
            ORDER BY ST_X(mc.geom), ST_Y(mc.geom), mc.potrero_id, mc.id
        ),
        cell AS (
            SELECT
                ST_Intersection(
                    ST_Expand(p.g, :medio_lado, :medio_lado),
                    ST_Transform(pb.geom, 3857)
                ) AS inter,
                p.id AS id,
                p.valor AS valor
            FROM pts p
            JOIN potreros_base pb
              ON pb.id = p.potrero_id
             AND pb.usuario_id = :uid
            WHERE ST_Intersects(
                    ST_Expand(p.g, :medio_lado, :medio_lado),
                    (SELECT tile FROM env)
                  )
        )
        SELECT ST_AsMVT(mvt_q, 'densidad', 4096, 'geom') AS mvt
        FROM (
            SELECT
                ST_AsMVTGeom(
                    CASE
                        WHEN (SELECT u FROM exc) IS NULL THEN c.inter
                        ELSE ST_Difference(c.inter, (SELECT u FROM exc))
                    END,
                    (SELECT tile FROM env),
                    4096, 0, true
                ) AS geom,
                c.id AS id,
                c.valor AS valor
            FROM cell c
            WHERE c.inter IS NOT NULL AND NOT ST_IsEmpty(c.inter)
        ) AS mvt_q
    """)
    row = conn.execute(sql, {
        "z": z, "x": x, "y": y,
        "buf": BUF_M,
        "medio_lado": MEDIO_LADO_M,
        "uid": uid,
        "finca": finca,
        "fecha": fecha,
    }).fetchone()
    return _bordes_mvt(row)


def renderizar_tile(uid: int, finca: str, fecha: date, tipo: str,
                    z: int, x: int, y: int, columna: str) -> bytes:
    """Cachea (LRU + BD) y devuelve el tile. Si el grupo no tiene celdas
    precalculadas, cae al query viejo."""
    clave = (uid, finca, fecha, tipo, z, x, y)
    mvt = _lru_get(clave)
    if mvt is not None:
        return mvt
    try:
        with engine.connect() as conn:
            mvt = repo_celdas.leer_tile_cache(conn, uid, finca, fecha, tipo, z, x, y)
    except Exception:
        mvt = None
    if mvt is not None:
        _lru_put(clave, mvt)
        return mvt

    # Antiduplicado entre workers: si otro proceso está calculando este mismo
    # tile, esperamos a que termine y lo leemos de la caché compartida en vez
    # de hacer el trabajo dos veces (era el pico de ~1.4s del z13 grande).
    with engine.begin() as conn:
        repo_celdas.tomar_lock_tile(conn, uid, finca, fecha, tipo, z, x, y)
        try:
            mvt = repo_celdas.leer_tile_cache(conn, uid, finca, fecha, tipo, z, x, y)
            if mvt is None:
                con_celdas = _celdas_listas(uid, finca, fecha)
                mvt = (_tile_celdas if con_celdas else _tile_legacy)(
                    conn, uid, finca, fecha, z, x, y, columna)
                repo_celdas.guardar_tile_cache(conn, uid, finca, fecha, tipo, z, x, y, mvt)
                if random.random() < 0.02:
                    repo_celdas.podar_cache_tiles(conn)
        finally:
            repo_celdas.soltar_lock_tile(conn, uid, finca, fecha, tipo, z, x, y)

    _lru_put(clave, mvt)
    return mvt


def respuesta_mvt(mvt: bytes) -> Response:
    return Response(
        content=mvt,
        media_type="application/x-protobuf",
        headers={
            "Content-Disposition": "inline",
            # El contenido va direccionado por (finca, fecha, tipo): si esos
            # no cambian, el tile es inmutable. Además hay caché server-side
            # (mapa_tiles_cache), así que el 1h del navegador solo evita
            # re-transferir. Tras re-ingestar datos se invalida server-side;
            # para forzar en el cliente: Ctrl+Shift+R.
            "Cache-Control": "public, max-age=3600",
        },
    )
