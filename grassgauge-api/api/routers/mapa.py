from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from core.seguridad import get_current_user_id
from servicios.histograma import generar_histograma
from servicios.mapa_tiles import (
    COL_DENSIDAD, TIPOS_VALIDOS, renderizar_tile, respuesta_mvt,
)
from servicios.mapa_warmup import precalentar_async

router = APIRouter(prefix="/api/mapa", tags=["mapa-vector-tiles"])


def _tipo_validado(tipo_densidad: str) -> tuple[str, str]:
    tipo = tipo_densidad.strip().lower()
    if tipo not in TIPOS_VALIDOS:
        raise HTTPException(status_code=400, detail=f"tipo_densidad inválido. Use: {list(TIPOS_VALIDOS)}")
    return tipo, COL_DENSIDAD[tipo]


def _finca_validada(finca: str) -> str:
    finca_norm = finca.strip()
    if not finca_norm:
        raise HTTPException(status_code=400, detail="estancia requerida")
    return finca_norm


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
    tipo, columna = _tipo_validado(tipo_densidad)

    # ST_TileEnvelope falla con 500 si x/y están fuera del rango del zoom.
    if x >= (1 << z) or y >= (1 << z):
        raise HTTPException(status_code=404, detail=f"Tile z={z} x={x} y={y} fuera de rango")

    finca_norm = _finca_validada(finca)
    mvt = renderizar_tile(usuario_id_resuelto, finca_norm, fecha, tipo, z, x, y, columna)
    # Precalentar el resto de la grilla de la finca en este zoom (thread
    # aparte, best-effort): hace que panear y volver sea casi instantáneo.
    precalentar_async(usuario_id_resuelto, finca_norm, fecha, tipo, z, (x, y), columna)
    return respuesta_mvt(mvt)


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
    tipo, columna = _tipo_validado(tipo_densidad)
    finca_norm = _finca_validada(finca)

    bbox = None
    if None not in (min_lon, min_lat, max_lon, max_lat):
        if min_lon >= max_lon or min_lat >= max_lat:
            raise HTTPException(status_code=400, detail="bbox inválido (min debe ser menor que max)")
        bbox = (min_lon, min_lat, max_lon, max_lat)

    precalentar_async(usuario_id_resuelto, finca_norm, fecha, tipo, z, None,
                      columna, bbox=bbox)
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
    return generar_histograma(
        finca=finca, fecha=fecha, bins=bins,
        potrero_id=potrero_id, parcela_id=parcela_id,
        usuario_id_resuelto=usuario_id_resuelto,
    )
