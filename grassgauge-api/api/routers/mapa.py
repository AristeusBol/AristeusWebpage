from datetime import date
from typing import Optional
import json
import math
import random
import threading
import time
from collections import OrderedDict

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from fastapi.responses import Response
from sqlalchemy import text

from core.db import engine
from core.seguridad import get_current_user_id
from repositorios import celdas as repo_celdas

router = APIRouter(prefix="/api/mapa", tags=["mapa-vector-tiles"])

COL_DENSIDAD = {
    "verde": "densidad_verde_g_m2",
    "muerta": "densidad_muerta_g_m2",
    "total": "densidad_total_g_m2",
}
TIPOS_VALIDOS = set(COL_DENSIDAD.keys())

# Media celda de 8m (~16x16m sobre grilla de ~10.4m): cubre las franjas de
# borde donde la medición no llega hasta el límite del lote. El solape entre
# vecinas no se nota con relleno sólido. (Se aplica al precalcular celdas
# y, como fallback, en el query viejo de abajo.)
MEDIO_LADO_M = 8
BUF_M = 20  # buffer del tile viejo (solo fallback)


# ---------------------------------------------------------------------------
# Caché de tiles: LRU en proceso (por worker) + tabla compartida en la BD.
# Los tiles son inmutables por (finca, fecha, tipo): recalcularlos costaba
# 2-7s cada vez; ahora el segundo pedido es un lookup.
# ---------------------------------------------------------------------------

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
              AND NOT EXISTS (
                    SELECT 1 FROM zonas_exclusion z
                    WHERE z.usuario_id = :uid
                      AND z.potrero_id = mc.potrero_id
                      AND ST_Covers(z.geom, mc.geom)
                  )
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


def _renderizar_tile(uid: int, finca: str, fecha: date, tipo: str,
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


# --- Precalentado bajo demanda ---------------------------------------------
# El navegador pide ~24 tiles por viewport de a 6 (HTTP/1.1). Con el primer
# tile se dispara en segundo plano el render del resto de la grilla de la
# finca para ese mismo zoom, así panear/cambiar de fecha cae casi todo en caché.

_calentando: set = set()
_calentando_lock = threading.Lock()
_CALIENTE_MAX_TILES = 80
_CALIENTE_PAUSA_S = 0.02
# No repetir el pase de precalentado del mismo grupo tan seguido: el
# viewport dispara ~24 requests y cada uno llamaría a esta función.
_CALIENTE_TTL_S = 300.0
_calentado_hasta: dict = {}
_calentado_lock = threading.Lock()


def _rango_tiles(min_lon: float, min_lat: float, max_lon: float, max_lat: float, z: int):
    """Rango de tiles (x, y) que cubren un bbox lon/lat en el zoom dado."""
    n = 1 << z

    def tx(lon: float) -> int:
        return int((lon + 180.0) / 360.0 * n)

    def ty(lat: float) -> int:
        lat = max(min(lat, 85.05112878), -85.05112878)
        r = math.radians(lat)
        return int((1.0 - math.asinh(math.tan(r)) / math.pi) / 2.0 * n)

    x0, x1 = max(0, tx(min_lon)), min(n - 1, tx(max_lon))
    y0, y1 = max(0, ty(max_lat)), min(n - 1, ty(min_lat))
    if x1 < x0 or y1 < y0:
        return [], []
    return list(range(x0, x1 + 1)), list(range(y0, y1 + 1))


def _precalentar_async(uid: int, finca: str, fecha: date, tipo: str, z: int,
                       skip_xy: tuple, columna: str,
                       bbox: Optional[tuple] = None) -> None:
    """Renderiza en segundo plano la grilla de tiles que cubre la finca.

    `bbox` (min_lon, min_lat, max_lon, max_lat) permite acotar a la zona
    visible; sin él se usa el bbox de los potreros. Best-effort: nunca
    propaga errores (corre en un thread).
    """
    if z < 0 or z > 17:
        return
    clave = (uid, finca, fecha, tipo, z, None if bbox is None else tuple(round(v, 4) for v in bbox))
    ahora = time.time()
    with _calentando_lock:
        if clave in _calentando or _calentado_hasta.get(clave, 0) > ahora:
            return
        _calentando.add(clave)

    def tarea() -> None:
        try:
            if bbox is not None:
                xs, ys = _rango_tiles(bbox[0], bbox[1], bbox[2], bbox[3], z)
            else:
                with engine.connect() as conn:
                    ext = conn.execute(
                        text("""
                            SELECT ST_XMin(e), ST_YMin(e), ST_XMax(e), ST_YMax(e)
                            FROM (SELECT ST_Extent(geom) AS e FROM potreros_base
                                  WHERE usuario_id = :uid AND finca = :finca) s
                        """),
                        {"uid": uid, "finca": finca},
                    ).fetchone()
                # len(ext) != 4: engine mockeado/consulta rara. El precalentado es
                # best-effort, no puede tumbar un hilo ni ensuciar los tests.
                if not ext or len(ext) < 4 or ext[0] is None:
                    return
                xs, ys = _rango_tiles(ext[0], ext[1], ext[2], ext[3], z)
            if not xs or not ys or len(xs) * len(ys) > _CALIENTE_MAX_TILES:
                return
            for tx_ in xs:
                for ty_ in ys:
                    if (tx_, ty_) == skip_xy:
                        continue
                    try:
                        _renderizar_tile(uid, finca, fecha, tipo, z, tx_, ty_, columna)
                    except Exception:
                        pass  # best-effort: lo pedirá el navegador si hace falta
                    time.sleep(_CALIENTE_PAUSA_S)
        finally:
            with _calentando_lock:
                _calentando.discard(clave)
                _calentado_hasta[clave] = time.time() + _CALIENTE_TTL_S

    threading.Thread(target=tarea, daemon=True, name=f"warmup-tiles-{finca}").start()


def _respuesta_mvt(mvt: bytes) -> Response:
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


@router.get("/tiles/{z}/{x}/{y}.pbf")
def get_mapa_tile(
    z: int = Path(..., ge=0, le=22, description="Zoom"),
    x: int = Path(..., ge=0),
    y: int = Path(..., ge=0),
    finca: str = Query(..., description="Estancia exacta, ej: La Esperanza"),
    fecha: date = Query(..., description="Fecha YYYY-MM-DD, ej: 2024-04-01"),
    tipo_densidad: str = Query(..., description="verde | muerta | total"),
    usuario_id_resuelto: int = Depends(get_current_user_id),
):
    """Tile vectorial MVT con densidad como superficie continua.

    Los puntos de `mapa_color` forman una grilla regular de ~10.4x10.4m y
    cada punto se expande a su celda cuadrada (~16x16m) recortada por el
    potrero y menos las zonas de exclusion. Esas celdas se precalculan al
    ingerir (`mapa_celdas`, ver repositorios/celdas.py) y el tile solo las
    escanea por indice GIST: ~50-150ms en vez de ~2-7s construyendolas por
    tile. Los bytes MVT quedan cacheados en `mapa_tiles_cache` (+ LRU por
    worker) y la primera vista dispara el precalentado del resto de la grilla.

    Si un (finca, fecha) todavia no tiene celdas (ingesta vieja sin backfill),
    cae al query legacy que las construye on-the-fly.
    """
    tipo = tipo_densidad.strip().lower()
    if tipo not in TIPOS_VALIDOS:
        raise HTTPException(status_code=400, detail=f"tipo_densidad inválido. Use: {list(TIPOS_VALIDOS)}")
    columna = COL_DENSIDAD[tipo]

    # ST_TileEnvelope falla con 500 si x/y están fuera del rango del zoom.
    if x >= (1 << z) or y >= (1 << z):
        raise HTTPException(status_code=404, detail=f"Tile z={z} x={x} y={y} fuera de rango")

    finca_norm = finca.strip()
    if not finca_norm:
        raise HTTPException(status_code=400, detail="estancia requerida")

    mvt = _renderizar_tile(usuario_id_resuelto, finca_norm, fecha, tipo, z, x, y, columna)
    # Precalentar el resto de la grilla de la finca en este zoom (thread
    # aparte, best-effort): hace que panear y volver sea casi instantáneo.
    _precalentar_async(usuario_id_resuelto, finca_norm, fecha, tipo, z, (x, y), columna)
    return _respuesta_mvt(mvt)


@router.post("/precalentar")
def post_mapa_precalentar(
    finca: str = Query(..., description="Estancia exacta, ej: La Esperanza"),
    fecha: date = Query(..., description="Fecha YYYY-MM-DD, ej: 2024-04-01"),
    tipo_densidad: str = Query("total", description="verde | muerta | total"),
    z: int = Query(..., ge=0, le=17, description="Zoom del viewport"),
    min_lon: Optional[float] = Query(None, description="Oeste del viewport"),
    min_lat: Optional[float] = Query(None, description="Sur del viewport"),
    max_lon: Optional[float] = Query(None, description="Este del viewport"),
    max_lat: Optional[float] = Query(None, description="Norte del viewport"),
    usuario_id_resuelto: int = Depends(get_current_user_id),
):
    """Dispara el render de la grilla de tiles en segundo plano (no bloquea).

    Pensado para que el frontend lo llame al abrir el mapa o al cambiar
    fecha/zoom: cuando el navegador pide los ~24 tiles del viewport ya están
    (o están siendo) cacheados, y la primera pintada deja de pagar el arranque
    en frío. Idempotente y con TTL: pedirlo muchas veces no repite trabajo.
    """
    tipo = tipo_densidad.strip().lower()
    if tipo not in TIPOS_VALIDOS:
        raise HTTPException(status_code=400, detail=f"tipo_densidad inválido. Use: {list(TIPOS_VALIDOS)}")
    finca_norm = finca.strip()
    if not finca_norm:
        raise HTTPException(status_code=400, detail="estancia requerida")

    bbox = None
    if None not in (min_lon, min_lat, max_lon, max_lat):
        if min_lon >= max_lon or min_lat >= max_lat:
            raise HTTPException(status_code=400, detail="bbox inválido (min debe ser menor que max)")
        bbox = (min_lon, min_lat, max_lon, max_lat)

    _precalentar_async(usuario_id_resuelto, finca_norm, fecha, tipo, z, None,
                       COL_DENSIDAD[tipo], bbox=bbox)
    return {"estado": "programado", "finca": finca_norm, "fecha": fecha,
            "tipo_densidad": tipo, "z": z}


@router.get("/histograma")
def get_mapa_histograma(
    finca: str = Query(..., description="Estancia"),
    fecha: date = Query(..., description="YYYY-MM-DD"),
    bins: int = Query(20, ge=5, le=50, description="Cantidad de intervalos"),
    potrero_id: Optional[int] = Query(None, description="Si se pasa, histograma solo de ese lote"),
    parcela_id: Optional[int] = Query(None, description="Si se pasa, histograma solo de esa parcela (excluyente con potrero_id)"),
    usuario_id_resuelto: int = Depends(get_current_user_id),
):
    """Distribución comparada verde/muerta/total sobre bines comunes.

    Devuelve {filtros, stats, edges, series}: las 3 densidades comparten los
    mismos bordes para graficar barras agrupadas. Los bordes son FIJOS por
    finca (mínimo/máximo global de todas las fechas y lotes) para que los
    histogramas sean comparables entre fechas y lotes.
    """
    finca_norm = finca.strip()
    if not finca_norm:
        raise HTTPException(status_code=400, detail="estancia requerida")

    # Parcela: resuelve potrero padre + geometría (la parcela está contenida
    # en su potrero, así que se filtra por potrero_id y se recorta espacialmente).
    # Si también vino potrero_id debe coincidir con el padre (si no, 400).
    gj_text: Optional[str] = None
    if parcela_id is not None:
        with engine.connect() as conn:
            pa = conn.execute(
                text("""
                    SELECT pa.potrero_id AS potrero_id,
                           ST_AsGeoJSON(pa.geom)::json AS geom_json
                    FROM parcelas pa
                    JOIN potreros_base pb ON pb.id = pa.potrero_id AND pb.usuario_id = pa.usuario_id
                    WHERE pa.id = :parc AND pa.usuario_id = :uid AND pb.finca = :finca
                """),
                {"parc": parcela_id, "uid": usuario_id_resuelto, "finca": finca_norm},
            ).fetchone()
        if not pa:
            raise HTTPException(status_code=404, detail=f"Parcela {parcela_id} no existe o no es tuya")
        if potrero_id is not None and int(pa.potrero_id) != potrero_id:
            raise HTTPException(status_code=400, detail=f"La parcela {parcela_id} no pertenece al potrero {potrero_id}")
        potrero_id = int(pa.potrero_id)
        gj_text = json.dumps(pa.geom_json)
    recorte_parcela = " AND ST_Covers(ST_SetSRID(ST_GeomFromGeoJSON(:gj), 4326), m.geom)" if gj_text else ""

    if potrero_id is not None and parcela_id is None:
        with engine.connect() as conn:
            dueno = conn.execute(
                text("SELECT 1 FROM potreros_base WHERE id = :pid AND usuario_id = :uid AND finca = :finca"),
                {"pid": potrero_id, "uid": usuario_id_resuelto, "finca": finca_norm},
            ).fetchone()
        if not dueno:
            raise HTTPException(status_code=404, detail=f"Potrero {potrero_id} no existe o no es tuyo")

    # Área neta (bruta menos exclusiones) de la estancia, del potrero o de
    # la parcela: el factor kg/punto debe repartir el área productiva, no la
    # bruta. Antes se usaba el área bruta, sobreestimando los kg cuando hay
    # zonas de exclusión.
    if gj_text:
        area_sql = text("""
            SELECT ST_Area(
                COALESCE(
                    ST_Difference(
                        ST_SetSRID(ST_GeomFromGeoJSON(:gj), 4326),
                        (SELECT ST_Union(z.geom) FROM zonas_exclusion z
                         WHERE z.usuario_id = :uid AND z.potrero_id = :pid)
                    ),
                    ST_SetSRID(ST_GeomFromGeoJSON(:gj), 4326)
                )::geography) AS area_m2
        """)
        area_params = {"uid": usuario_id_resuelto, "pid": potrero_id, "gj": gj_text}
    else:
        area_sql = text("""
        SELECT COALESCE(SUM(ST_Area(p.geom::geography)), 0)
              - COALESCE(SUM(ST_Area(ST_Intersection(
                     p.geom,
                     COALESCE(u.geom_union, ST_GeomFromText('GEOMETRYCOLLECTION EMPTY', 4326))
                   )::geography)), 0) AS area_m2
        FROM potreros_base p
        LEFT JOIN (
            SELECT potrero_id, ST_Union(geom) AS geom_union
            FROM zonas_exclusion
            WHERE usuario_id = :uid
            GROUP BY potrero_id
        ) u ON u.potrero_id = p.id
        WHERE p.usuario_id = :uid AND p.finca = :finca
          AND (:pid IS NULL OR p.id = :pid)
    """)
        area_params = {"uid": usuario_id_resuelto, "finca": finca_norm, "pid": potrero_id}
    with engine.connect() as conn:
        area_row = conn.execute(area_sql, area_params).fetchone()
    area_m2 = float(area_row[0]) if area_row and area_row[0] else 0.0

    stats_sql = text(f"""
        SELECT COUNT(*) AS n,
               COUNT(densidad_verde_g_m2) AS n_verde,
               MIN(densidad_verde_g_m2) AS vmin_verde,
               MAX(densidad_verde_g_m2) AS vmax_verde,
               AVG(densidad_verde_g_m2) AS vmean_verde,
               COUNT(densidad_muerta_g_m2) AS n_muerta,
               MIN(densidad_muerta_g_m2) AS vmin_muerta,
               MAX(densidad_muerta_g_m2) AS vmax_muerta,
               AVG(densidad_muerta_g_m2) AS vmean_muerta,
               COUNT(densidad_total_g_m2) AS n_total,
               MIN(densidad_total_g_m2) AS vmin_total,
               MAX(densidad_total_g_m2) AS vmax_total,
               AVG(densidad_total_g_m2) AS vmean_total
        FROM mapa_color m
        WHERE usuario_id = :uid
          AND finca = :finca
          AND fecha = :fecha
          AND (:pid IS NULL OR potrero_id = :pid){recorte_parcela}
          AND NOT EXISTS (SELECT 1 FROM zonas_exclusion z
            WHERE z.usuario_id = m.usuario_id AND z.potrero_id = m.potrero_id
              AND ST_Covers(z.geom, m.geom))
    """)
    with engine.connect() as conn:
        stats = conn.execute(stats_sql, {
            "uid": usuario_id_resuelto,
            "finca": finca_norm,
            "fecha": fecha,
            "pid": potrero_id,
            "gj": gj_text or "",
        }).fetchone()

    filtros = {
        "finca": finca_norm,
        "fecha": fecha.isoformat(),
        "bins": bins,
        "potrero_id": potrero_id,
        "parcela_id": parcela_id,
        "usuario_id": usuario_id_resuelto,
        "area_ha": round(area_m2 / 10000.0, 2),
    }
    per = {}
    for t in ("verde", "muerta", "total"):
        vmin = getattr(stats, f"vmin_{t}", None)
        vmax = getattr(stats, f"vmax_{t}", None)
        vmean = getattr(stats, f"vmean_{t}", None)
        per[t] = {
            "count": int(getattr(stats, f"n_{t}", 0) or 0),
            "vmin": float(vmin) if vmin is not None else None,
            "vmax": float(vmax) if vmax is not None else None,
            "vmean": float(vmean) if vmean is not None else None,
        }
    count = int(stats.n or 0)
    validos = {t: v for t, v in per.items() if v["vmin"] is not None and v["vmax"] is not None and v["count"] > 0}
    if count == 0 or area_m2 <= 0 or not validos:
        return {
            "filtros": filtros,
            "stats": {"count": 0},
            "edges": [],
            "series": {t: {"min": None, "max": None, "mean": None, "count": 0, "counts": [], "pcts": []} for t in ("verde", "muerta", "total")},
            "sin_datos": True,
        }

    # Bordes fijos por estancia: mínimo/máximo global de todas las fechas y
    # lotes (misma exclusión), para comparar histogramas entre sí.
    global_sql = text("""
        SELECT MIN(densidad_verde_g_m2) AS gmin_verde,
               MAX(densidad_verde_g_m2) AS gmax_verde,
               MIN(densidad_muerta_g_m2) AS gmin_muerta,
               MAX(densidad_muerta_g_m2) AS gmax_muerta,
               MIN(densidad_total_g_m2) AS gmin_total,
               MAX(densidad_total_g_m2) AS gmax_total
        FROM mapa_color m
        WHERE usuario_id = :uid
          AND finca = :finca
          AND NOT EXISTS (SELECT 1 FROM zonas_exclusion z
            WHERE z.usuario_id = m.usuario_id AND z.potrero_id = m.potrero_id
              AND ST_Covers(z.geom, m.geom))
    """)
    with engine.connect() as conn:
        grow = conn.execute(global_sql, {"uid": usuario_id_resuelto, "finca": finca_norm}).fetchone()
    gmin = min(float(v) for t in ("verde", "muerta", "total") if (v := getattr(grow, f"gmin_{t}", None)) is not None)
    gmax = max(float(v) for t in ("verde", "muerta", "total") if (v := getattr(grow, f"gmax_{t}", None)) is not None)
    factor = (area_m2 / count) / 1000.0

    def buckets_de(columna: str):
        q = text(f"""
            SELECT WIDTH_BUCKET({columna}, :vmin, :vmax, :bins) AS bucket, COUNT(*) AS c
            FROM mapa_color m
            WHERE usuario_id = :uid
              AND finca = :finca
              AND fecha = :fecha
              AND (:pid IS NULL OR potrero_id = :pid){recorte_parcela}
              AND {columna} IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM zonas_exclusion z
                WHERE z.usuario_id = m.usuario_id AND z.potrero_id = m.potrero_id
                  AND ST_Covers(z.geom, m.geom))
            GROUP BY bucket
        """)
        with engine.connect() as conn:
            return conn.execute(q, {
                "vmin": gmin, "vmax": gmax, "bins": bins,
                "uid": usuario_id_resuelto,
                "finca": finca_norm,
                "fecha": fecha,
                "pid": potrero_id,
                "gj": gj_text or "",
            }).fetchall()

    def plegar(filas):
        conteos = [0] * bins
        for r in filas:
            idx = int(r.bucket) - 1
            if 0 <= idx < bins:
                conteos[idx] = int(r.c)
            elif int(r.bucket) > bins:
                conteos[bins - 1] += int(r.c)
            elif int(r.bucket) < 1:
                conteos[0] += int(r.c)
        return conteos

    series = {}
    if gmax <= gmin:
        edges = [round(gmin * factor, 2), round(gmax * factor, 2)]
        for t in ("verde", "muerta", "total"):
            v = per[t]
            n_s = v["count"]
            series[t] = {
                "min": v["vmin"] * factor if v["vmin"] is not None else None,
                "max": v["vmax"] * factor if v["vmax"] is not None else None,
                "mean": v["vmean"] * factor if v["vmean"] is not None else None,
                "count": n_s,
                "counts": [n_s],
                "pcts": [100.0],
            }
    else:
        edges = [round((gmin + i * (gmax - gmin) / bins) * factor, 2) for i in range(bins + 1)]
        for t, columna in COL_DENSIDAD.items():
            v = per[t]
            n_s = v["count"]
            conteos = plegar(buckets_de(columna)) if n_s > 0 else [0] * bins
            series[t] = {
                "min": v["vmin"] * factor if v["vmin"] is not None else None,
                "max": v["vmax"] * factor if v["vmax"] is not None else None,
                "mean": v["vmean"] * factor if v["vmean"] is not None else None,
                "count": n_s,
                "counts": conteos,
                "pcts": [round(c / n_s * 100.0, 1) if n_s > 0 else 0.0 for c in conteos],
            }

    return {
        "filtros": filtros,
        "stats": {"count": count},
        "edges": edges,
        "series": series,
        "sin_datos": False,
    }
