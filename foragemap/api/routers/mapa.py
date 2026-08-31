from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.responses import Response
from sqlalchemy import text

from core.db import engine
from core.seguridad import resolver_usuario_id, security

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
    usuario_id: Optional[int] = Query(None, description="Solo dev/test sin token"),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    usuario_id_resuelto = resolver_usuario_id(credentials, usuario_id)

    tipo = tipo_densidad.strip().lower()
    if tipo not in TIPOS_VALIDOS:
        raise HTTPException(status_code=400, detail=f"tipo_densidad inválido. Use: {list(TIPOS_VALIDOS)}")
    columna = COL_DENSIDAD[tipo]

    finca_norm = finca.strip()
    if not finca_norm:
        raise HTTPException(status_code=400, detail="finca requerida")


    sql = text(f"""
        SELECT ST_AsMVT(mvt_q, 'densidad', 4096, 'geom') AS mvt
        FROM (
            SELECT
                ST_AsMVTGeom(
                    ST_Transform(geom, 3857),
                    ST_TileEnvelope(:z, :x, :y),
                    4096, 64, true
                ) AS geom,
                id,
                {columna} AS valor
            FROM mapa_color
            WHERE usuario_id = :uid
              AND finca = :finca
              AND fecha = :fecha
              AND {columna} IS NOT NULL
              AND ST_Intersects(
                    ST_Transform(geom, 3857),
                    ST_TileEnvelope(:z, :x, :y)
                  )
        ) AS mvt_q
    """)

    with engine.connect() as conn:
        row = conn.execute(sql, {
            "z": z, "x": x, "y": y,
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
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "public, max-age=86400",
        },
    )


@router.get("/geojson")
def get_mapa_geojson(
    finca: str = Query(..., description="Finca"),
    fecha: date = Query(..., description="YYYY-MM-DD"),
    tipo_densidad: str = Query(..., description="verde | muerta | total"),
    limit: int = Query(5000, ge=1, le=20000, description="Límite seguridad para no colapsar red"),
    usuario_id: Optional[int] = Query(None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    usuario_id_resuelto = resolver_usuario_id(credentials, usuario_id)
    tipo = tipo_densidad.strip().lower()
    if tipo not in TIPOS_VALIDOS:
        raise HTTPException(status_code=400, detail=f"tipo_densidad inválido. Use: {list(TIPOS_VALIDOS)}")
    columna = COL_DENSIDAD[tipo]
    finca_norm = finca.strip()
    if not finca_norm:
        raise HTTPException(status_code=400, detail="finca requerida")


    sql = text(f"""
        SELECT id, ST_AsGeoJSON(geom)::json AS geom_json, {columna} AS valor
        FROM mapa_color
        WHERE usuario_id = :uid
          AND finca = :finca
          AND fecha = :fecha
          AND {columna} IS NOT NULL
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
