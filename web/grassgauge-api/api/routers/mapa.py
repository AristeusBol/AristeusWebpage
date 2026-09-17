from datetime import date
from typing import Optional
import json

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
    finca: str = Query(..., description="Estancia exacta, ej: La Esperanza"),
    fecha: date = Query(..., description="Fecha YYYY-MM-DD, ej: 2024-04-01"),
    tipo_densidad: str = Query(..., description="verde | muerta | total"),
    usuario_id_resuelto: int = Depends(get_current_user_id),
):
    """Tile vectorial MVT con densidad como superficie continua.

    Los puntos de `mapa_color` forman una grilla regular de ~10.4x10.4m. Cada
    punto se expande a su celda cuadrada (ST_Expand 8m, ~16x16m), recortada
    por el potrero (`potreros_base`) y por el tile. La celda supera el paso
    de grilla a propósito: la medición no siempre llega hasta el borde del
    lote y con celdas justas quedaban franjas sin rellenar. Como el relleno
    es sólido, el solape entre vecinas no se nota. Props: {id, valor}.
    Duplicados en la misma coordenada se resuelven con DISTINCT ON.
    Las `zonas_exclusion` se recortan: ni puntos con centro dentro ni
    geometría superpuesta generan relleno (hueco = satélite a la vista).
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

    # Buffer en metros (SRID 3857) alrededor del tile: las celdas del borde
    # necesitan cubrir hasta el borde exacto del tile; el recorte final
    # se hace contra el tile exacto + el polígono del potrero.
    buf_m = 20
    # Media celda de 8m (~16x16m sobre grilla de ~10.4m): cubre las franjas
    # de borde donde la medición no llega hasta el límite del lote. El
    # solape entre vecinas no se nota con relleno sólido. Se probó Voronoi
    # (cobertura exacta) pero era demasiado lento por tile y GEOS fallaba
    # con tolerance > 0 en esta grilla.
    medio_lado_m = 8

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
