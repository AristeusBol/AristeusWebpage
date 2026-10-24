"""Precalentado en segundo plano de la grilla de tiles del mapa."""

from datetime import date
import math
import threading
import time
from typing import Optional

from sqlalchemy import text

from core.db import engine
from servicios.mapa_tiles import renderizar_tile

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


def precalentar_async(uid: int, finca: str, fecha: date, tipo: str, z: int,
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
                        renderizar_tile(uid, finca, fecha, tipo, z, tx_, ty_, columna)
                    except Exception:
                        pass  # best-effort: lo pedirá el navegador si hace falta
                    time.sleep(_CALIENTE_PAUSA_S)
        finally:
            with _calentando_lock:
                _calentando.discard(clave)
                _calentado_hasta[clave] = time.time() + _CALIENTE_TTL_S

    threading.Thread(target=tarea, daemon=True, name=f"warmup-tiles-{finca}").start()
