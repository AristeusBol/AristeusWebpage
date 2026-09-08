from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from fastapi.responses import Response
from sqlalchemy import text

from core.db import engine
from core.seguridad import get_current_user_id

router = APIRouter(prefix="/api/mapa", tags=["mapa-vector-tiles"])

COL_DENSIDAD = {
    "verde": "densidad_verde_g_m2",
    "muerta": "densidad_muerta_g_m2",
    "total": "densidad_total_g_m2",
}
TIPOS_VALIDOS = set(COL_DENSIDAD.keys())


@router.get("/tiles/{z}/{x}/{y}.pbf")
def get_mapa_tile(
    z: int = Path(..., ge=0, le=22, description="Zoom"),
    x: int = Path(..., ge=0),
    y: int = Path(..., ge=0),
    finca: str = Query(..., description="Finca exacta, ej: La Esperanza"),
    fecha: date = Query(..., description="Fecha YYYY-MM-DD, ej: 2024-04-01"),
    tipo_densidad: str = Query(..., description="verde | muerta | total"),
    usuario_id_resuelto: int = Depends(get_current_user_id),
):
    """Tile vectorial MVT con densidad como superficie continua.

    Los puntos de `mapa_color` forman una grilla regular de ~10x10m, así que
    cada punto se expande a su celda cuadrada (ST_Expand 5.05m), recortada
    por el potrero (`potreros_base`) y por el tile. Al hacer zoom no quedan
    huecos entre puntos: es relleno. Props por celda: {id, valor}.
    Duplicados en la misma coordenada se resuelven con DISTINCT ON.
    Las `zonas_exclusion` se recortan: ni puntos con centro dentro ni
    geometría superpuesta generan relleno (hueco = satélite a la vista).
    """
    tipo = tipo_densidad.strip().lower()
    if tipo not in TIPOS_VALIDOS:
        raise HTTPException(status_code=400, detail=f"tipo_densidad inválido. Use: {list(TIPOS_VALIDOS)}")
    columna = COL_DENSIDAD[tipo]

    finca_norm = finca.strip()
    if not finca_norm:
        raise HTTPException(status_code=400, detail="finca requerida")

    # Buffer en metros (SRID 3857) alrededor del tile: las celdas del borde
    # necesitan cubrir hasta el borde exacto del tile; el recorte final
    # se hace contra el tile exacto + el polígono del potrero.
    buf_m = 20
    # Media celda + 5cm de solape para que no se vean líneas de rejilla.
    medio_lado_m = 5.05

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
            SELECT DISTINCT ON (mc.potrero_id, ST_X(mc.geom), ST_Y(mc.geom))
                mc.id AS id,
                mc.potrero_id AS potrero_id,
                {columna} AS valor,
                ST_Transform(mc.geom, 3857) AS g
            FROM mapa_color mc, env
            WHERE mc.usuario_id = :uid
              AND mc.finca = :finca
              AND mc.fecha = :fecha
              AND {columna} IS NOT NULL
              -- Prefiltro barato con índice GIST (idx_color_geom); el chequeo
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
            ORDER BY mc.potrero_id, ST_X(mc.geom), ST_Y(mc.geom), mc.id
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

    with engine.connect() as conn:
        row = conn.execute(sql, {
            "z": z, "x": x, "y": y,
            "buf": buf_m,
            "medio_lado": medio_lado_m,
            "uid": usuario_id_resuelto,
            "finca": finca_norm,
            "fecha": fecha,
        }).fetchone()
        mvt = row[0] if row and row[0] is not None else None

    if mvt is None:
        return Response(content=b"", media_type="application/x-protobuf")

    if isinstance(mvt, memoryview):
        mvt = mvt.tobytes()
    elif isinstance(mvt, str):
        mvt = mvt.encode()

    return Response(
        content=bytes(mvt),
        media_type="application/x-protobuf",
        headers={
            "Content-Disposition": "inline",
            "Cache-Control": "private, max-age=300",
        },
    )


@router.get("/histograma")
def get_mapa_histograma(
    finca: str = Query(..., description="Finca"),
    fecha: date = Query(..., description="YYYY-MM-DD"),
    tipo_densidad: str = Query("total", description="verde | muerta | total"),
    bins: int = Query(20, ge=5, le=50, description="Cantidad de intervalos"),
    usuario_id_resuelto: int = Depends(get_current_user_id),
):
    """Distribución de peso por punto. Devuelve {stats, intervalos}."""
    tipo = tipo_densidad.strip().lower()
    if tipo not in TIPOS_VALIDOS:
        raise HTTPException(status_code=400, detail=f"tipo_densidad inválido. Use: {list(TIPOS_VALIDOS)}")
    columna = COL_DENSIDAD[tipo]
    finca_norm = finca.strip()
    if not finca_norm:
        raise HTTPException(status_code=400, detail="finca requerida")

    area_sql = text("""
        SELECT COALESCE(SUM(ST_Area(geom::geography)), 0) AS area_m2
        FROM potreros_base
        WHERE usuario_id = :uid AND finca = :finca
    """)
    with engine.connect() as conn:
        area_row = conn.execute(area_sql, {"uid": usuario_id_resuelto, "finca": finca_norm}).fetchone()
    area_m2 = float(area_row[0]) if area_row and area_row[0] else 0.0

    stats_sql = text(f"""
        SELECT COUNT(*) AS n,
               MIN({columna}) AS vmin,
               MAX({columna}) AS vmax,
               AVG({columna}) AS vmean
        FROM mapa_color m
        WHERE usuario_id = :uid
          AND finca = :finca
          AND fecha = :fecha
          AND {columna} IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM zonas_exclusion z
            WHERE z.usuario_id = m.usuario_id AND z.potrero_id = m.potrero_id
              AND ST_Covers(z.geom, m.geom))
    """)
    with engine.connect() as conn:
        stats = conn.execute(stats_sql, {
            "uid": usuario_id_resuelto,
            "finca": finca_norm,
            "fecha": fecha,
        }).fetchone()

    filtros = {
        "finca": finca_norm,
        "fecha": fecha.isoformat(),
        "tipo_densidad": tipo,
        "bins": bins,
        "usuario_id": usuario_id_resuelto,
        "area_ha": round(area_m2 / 10000.0, 2),
    }
    count = int(stats.n or 0)
    if count == 0 or area_m2 <= 0 or stats.vmin is None or stats.vmax is None:
        return {
            "filtros": filtros,
            "stats": {"count": 0, "min": None, "max": None, "mean": None, "unidad": "kg"},
            "intervalos": [],
            "sin_datos": True,
        }

    factor = (area_m2 / count) / 1000.0
    vmin = float(stats.vmin)
    vmax = float(stats.vmax)
    mean = float(stats.vmean) if stats.vmean is not None else None
    if vmax <= vmin:
        return {
            "filtros": filtros,
            "stats": {"count": count, "min": vmin * factor, "max": vmax * factor,
                      "mean": mean * factor if mean is not None else None, "unidad": "kg"},
            "intervalos": [
                {"lim_inf": round(vmin * factor, 2), "lim_sup": round(vmax * factor, 2),
                 "count": count, "pct": 100.0}
            ],
            "sin_datos": False,
        }

    bins_sql = text(f"""
        SELECT WIDTH_BUCKET({columna}, :vmin, :vmax, :bins) AS bucket, COUNT(*) AS c
        FROM mapa_color m
        WHERE usuario_id = :uid
          AND finca = :finca
          AND fecha = :fecha
          AND {columna} IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM zonas_exclusion z
            WHERE z.usuario_id = m.usuario_id AND z.potrero_id = m.potrero_id
              AND ST_Covers(z.geom, m.geom))
        GROUP BY bucket
    """)
    with engine.connect() as conn:
        bucket_rows = conn.execute(bins_sql, {
            "vmin": vmin, "vmax": vmax, "bins": bins,
            "uid": usuario_id_resuelto,
            "finca": finca_norm,
            "fecha": fecha,
        }).fetchall()

    conteos = [0] * bins
    for r in bucket_rows:
        idx = int(r.bucket) - 1
        if 0 <= idx < bins:
            conteos[idx] = int(r.c)
        elif int(r.bucket) > bins:
            conteos[bins - 1] += int(r.c)
        elif int(r.bucket) < 1:
            conteos[0] += int(r.c)

    ancho = (vmax - vmin) / bins
    intervalos = [
        {
            "lim_inf": round((vmin + i * ancho) * factor, 2),
            "lim_sup": round((vmin + (i + 1) * ancho) * factor, 2),
            "count": conteos[i],
            "pct": round(conteos[i] / count * 100.0, 1),
        }
        for i in range(bins)
    ]

    return {
        "filtros": filtros,
        "stats": {"count": count, "min": vmin * factor, "max": vmax * factor,
                  "mean": mean * factor if mean is not None else None, "unidad": "kg"},
        "intervalos": intervalos,
        "sin_datos": False,
    }


@router.get("/geojson")
def get_mapa_geojson(
    finca: str = Query(..., description="Finca"),
    fecha: date = Query(..., description="YYYY-MM-DD"),
    tipo_densidad: str = Query(..., description="verde | muerta | total"),
    limit: int = Query(1000, ge=1, le=5000, description="Límite seguridad para no colapsar red"),
    usuario_id_resuelto: int = Depends(get_current_user_id),
):
    """Puntos como GeoJSON (debug/export). Devuelve FeatureCollection acotado."""
    tipo = tipo_densidad.strip().lower()
    if tipo not in TIPOS_VALIDOS:
        raise HTTPException(status_code=400, detail=f"tipo_densidad inválido. Use: {list(TIPOS_VALIDOS)}")
    columna = COL_DENSIDAD[tipo]
    finca_norm = finca.strip()
    if not finca_norm:
        raise HTTPException(status_code=400, detail="finca requerida")

    sql = text(f"""
        SELECT id, ST_AsGeoJSON(geom)::json AS geom_json, {columna} AS valor
        FROM mapa_color m
        WHERE usuario_id = :uid
          AND finca = :finca
          AND fecha = :fecha
          AND {columna} IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM zonas_exclusion z
            WHERE z.usuario_id = m.usuario_id AND z.potrero_id = m.potrero_id
              AND ST_Covers(z.geom, m.geom))
        LIMIT :lim
    """)
    with engine.connect() as conn:
        rows = conn.execute(sql, {
            "uid": usuario_id_resuelto,
            "finca": finca_norm,
            "fecha": fecha,
            "lim": limit,
        }).fetchall()

    features = [
        {
            "type": "Feature",
            "geometry": r.geom_json,
            "properties": {"id": r.id, "valor": float(r.valor) if r.valor is not None else None},
        }
        for r in rows
    ]
    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "finca": finca_norm,
            "fecha": fecha.isoformat(),
            "tipo_densidad": tipo,
            "count": len(features),
            "limit": limit,
            "warning": "Para visualización preferir /tiles/{z}/{x}/{y}.pbf" if len(features) >= limit else None,
        },
    }
