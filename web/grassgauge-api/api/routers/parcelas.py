import json
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from api.routers.potreros import _prorrateo
from api.schemas import ParcelaCreate, ParcelaUpdate
from core.db import engine
from core.seguridad import get_current_user_id
from repositorios import parcelas as repo

router = APIRouter(tags=["parcelas"])


def _feature_parcela(pa, finca, fecha_iso, calc=None, zonal=None):
    area = float(pa.area_ha) if pa.area_ha is not None else None
    if zonal is not None:
        pr = dict(zonal)
        if pr.get("area_ha") is None:
            pr["area_ha"] = area
    else:
        pr = _prorrateo(area, calc)
    return {
        "type": "Feature",
        "geometry": pa.geom_json,
        "properties": {
            "id": pa.id, "tipo": "parcela", "nombre": pa.nombre,
            "finca": finca, "potrero_id": pa.potrero_id, "estado": pa.estado,
            "fecha": fecha_iso, "area_ha": pr.get("area_ha", area), **pr,
        },
    }


def _zonal_row_to_dict(n, vmean, mmean, tmean, area_ha):
    n = int(n or 0)
    area_ha = float(area_ha) if area_ha is not None else None
    if n == 0 or area_ha is None or area_ha <= 0:
        return {
            "masa_verde_kg": None, "masa_muerta_kg": None, "masa_total_kg": None,
            "t_ha_verde": None, "t_ha_muerta": None, "t_ha_total": None,
            "tiene_calculo": False, "estimado_zonal": False,
            "n_puntos": n, "area_ha": area_ha,
        }
    if vmean is None or mmean is None or tmean is None:
        return {
            "masa_verde_kg": None, "masa_muerta_kg": None, "masa_total_kg": None,
            "t_ha_verde": None, "t_ha_muerta": None, "t_ha_total": None,
            "tiene_calculo": False, "estimado_zonal": False,
            "n_puntos": n, "area_ha": area_ha,
        }
    vmean = float(vmean)
    mmean = float(mmean)
    tmean = float(tmean)
    area_m2 = area_ha * 10000.0
    return {
        "masa_verde_kg": vmean * area_m2 / 1000.0,
        "masa_muerta_kg": mmean * area_m2 / 1000.0,
        "masa_total_kg": tmean * area_m2 / 1000.0,
        "t_ha_verde": vmean * 0.01,
        "t_ha_muerta": mmean * 0.01,
        "t_ha_total": tmean * 0.01,
        "densidad_promedio_verde_g_m2": vmean,
        "densidad_promedio_muerta_g_m2": mmean,
        "densidad_promedio_total_g_m2": tmean,
        "tiene_calculo": True, "estimado_zonal": True,
        "n_puntos": n, "area_ha": area_ha,
    }


def _zonales_finca(conn, uid, fecha_iso, rows):
    """Promedios zonales por parcela en una sola consulta (misma formula que potrero)."""
    if not fecha_iso or not rows:
        return {}
    pids = sorted({r.potrero_id for r in rows})
    res = conn.execute(
        text("""
            WITH pa AS (
                SELECT id, potrero_id, geom FROM parcelas
                WHERE usuario_id = :uid
                  AND potrero_id = ANY(:pids)
            ),
            area AS (
                SELECT pa.id AS pid,
                       ST_Area(COALESCE(
                           ST_Difference(pa.geom, u.u),
                           pa.geom
                       )::geography) / 10000.0 AS area_ha
                FROM pa
                LEFT JOIN LATERAL (
                    SELECT ST_Union(z.geom) AS u FROM zonas_exclusion z
                    WHERE z.usuario_id = :uid AND z.potrero_id = pa.potrero_id
                ) u ON true
            )
            SELECT pa.id AS pid,
                   COUNT(m.geom) AS n,
                   AVG(m.densidad_verde_g_m2) AS vmean,
                   AVG(m.densidad_muerta_g_m2) AS mmean,
                   AVG(m.densidad_total_g_m2) AS tmean,
                   MAX(area.area_ha) AS area_ha
            FROM pa
            JOIN area ON area.pid = pa.id
            LEFT JOIN mapa_color m
              ON m.usuario_id = :uid
             AND m.potrero_id = pa.potrero_id
             AND m.fecha = :fecha
             AND ST_Covers(pa.geom, m.geom)
             AND NOT EXISTS (
                 SELECT 1 FROM zonas_exclusion z
                 WHERE z.usuario_id = m.usuario_id AND z.potrero_id = m.potrero_id
                   AND ST_Covers(z.geom, m.geom)
             )
            GROUP BY pa.id
        """),
        {"uid": uid, "pids": pids, "fecha": fecha_iso},
    ).fetchall()
    out = {}
    for r in res:
        out[int(r.pid)] = _zonal_row_to_dict(r.n, r.vmean, r.mmean, r.tmean, r.area_ha)
    return out


@router.get("/api/potreros/{potrero_id}/parcelas")
def listar_parcelas(
    potrero_id: int,
    fecha: Optional[date] = Query(None, description="Fecha YYYY-MM-DD para promedio zonal"),
    uid: int = Depends(get_current_user_id),
):
    """Parcelas de un potrero como FeatureCollection (promedio zonal si hay fecha)."""
    with engine.connect() as conn:
        pot = repo.potrero_del_usuario(conn, potrero_id, uid)
        if not pot:
            raise HTTPException(status_code=404, detail=f"Potrero {potrero_id} no existe o no es tuyo")
        rows = repo.listar_parcelas_potrero(conn, potrero_id, uid)
        fecha_iso = fecha.isoformat() if fecha else None
        zonales = _zonales_finca(conn, uid, fecha_iso, rows)
    feats = [_feature_parcela(r, pot.finca, fecha_iso, zonal=zonales.get(r.id)) for r in rows]
    return {
        "type": "FeatureCollection", "features": feats,
        "metadata": {
            "potrero_id": potrero_id, "potrero": pot.nombre, "finca": pot.finca,
            "fecha": fecha_iso,
            "count": len(feats),
            "con_calculo": sum(1 for f in feats if f["properties"]["tiene_calculo"]),
            "nota": "promedio zonal de la parcela" if fecha else None,
        },
    }


@router.get("/api/parcelas/geojson")
def parcelas_finca_geojson(
    finca: str = Query(..., description="Estancia exacta"),
    fecha: Optional[date] = Query(None, description="Fecha YYYY-MM-DD para prorrateo"),
    uid: int = Depends(get_current_user_id),
):
    """Todas las parcelas de una estancia (una sola llamada para el mapa de gestión)."""
    finca_norm = (finca or "").strip()
    if not finca_norm:
        raise HTTPException(status_code=400, detail="estancia requerida")
    fecha_iso = fecha.isoformat() if fecha else None
    with engine.connect() as conn:
        rows = repo.listar_parcelas_finca(conn, uid, finca_norm)
        zonales = _zonales_finca(conn, uid, fecha_iso, rows)
    feats = [_feature_parcela(r, r.finca, fecha_iso, zonal=zonales.get(r.id)) for r in rows]
    return {
        "type": "FeatureCollection", "features": feats,
        "metadata": {
            "finca": finca_norm, "fecha": fecha_iso, "count": len(feats),
            "con_calculo": sum(1 for f in feats if f["properties"]["tiene_calculo"]),
        },
    }


@router.get("/api/exclusiones/geojson")
def exclusiones_finca_geojson(
    finca: str = Query(..., description="Estancia exacta"),
    uid: int = Depends(get_current_user_id),
):
    """Zonas de exclusión de una estancia (para dibujarlas en el mapa de gestión)."""
    finca_norm = (finca or "").strip()
    if not finca_norm:
        raise HTTPException(status_code=400, detail="estancia requerida")
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT id, potrero_id, nombre, tipo, finca,
                       ST_AsGeoJSON(geom)::json AS geom_json,
                       ST_Area(geom::geography) / 10000.0 AS area_ha
                FROM zonas_exclusion
                WHERE usuario_id = :uid AND finca = :finca
                ORDER BY nombre ASC
            """),
            {"uid": uid, "finca": finca_norm},
        ).fetchall()
    features = [
        {
            "type": "Feature",
            "geometry": r.geom_json,
            "properties": {
                "id": r.id, "tipo": "exclusion", "nombre": r.nombre,
                "subtipo": r.tipo, "finca": r.finca, "potrero_id": r.potrero_id,
                "area_ha": float(r.area_ha) if r.area_ha is not None else None,
            },
        }
        for r in rows
    ]
    return {
        "type": "FeatureCollection", "features": features,
        "metadata": {"finca": finca_norm, "count": len(features)},
    }


@router.get("/api/parcelas/sugerir-nombre")
def sugerir_nombre(
    potrero_id: int = Query(...),
    uid: int = Depends(get_current_user_id),
):
    """Sugiere '<Potrero>_N' libre (primer hueco desde 1)."""
    with engine.connect() as conn:
        pot = repo.potrero_del_usuario(conn, potrero_id, uid)
        if not pot:
            raise HTTPException(status_code=404, detail=f"Potrero {potrero_id} no existe o no es tuyo")
        nombre = repo.siguiente_nombre_parcela(conn, potrero_id, uid, pot.nombre)
    return {"potrero_id": potrero_id, "nombre_sugerido": nombre}


@router.post("/api/potreros/{potrero_id}/parcelas", status_code=201)
def crear_parcela(
    potrero_id: int,
    body: ParcelaCreate,
    uid: int = Depends(get_current_user_id),
):
    """Crea una parcela dibujada dentro del potrero (nombre auto, recorte de exclusiones)."""
    gj = repo.geom_geojson_text(body.geom)
    with engine.connect() as conn:
        pot = repo.potrero_del_usuario(conn, potrero_id, uid)
        if not pot:
            raise HTTPException(status_code=404, detail=f"Potrero {potrero_id} no existe o no es tuyo")
        chk = repo.validar_contenida(conn, gj, potrero_id, uid)
        if not chk or not chk.valida:
            raise HTTPException(status_code=400, detail="Geometría inválida (autointersección). Redibujá el polígono.")
        if not chk.dentro:
            raise HTTPException(status_code=400, detail="La parcela debe estar dentro del potrero (se permite compartir borde).")
        rec = repo.geometria_recortada(conn, gj, potrero_id, uid)
        gj_final = json.dumps(rec.geom_json) if rec and rec.geom_json else gj
        area_final = float(rec.area_ha or 0) if rec else float(chk.area_ha or 0)
        if area_final < 0.01:
            raise HTTPException(status_code=400, detail="Muy poco: la parcela útil es menor a 0.01 ha (casi todo es exclusión). Dibujá más grande.")
        if repo.hay_solape(conn, gj_final, potrero_id, uid):
            raise HTTPException(status_code=409, detail="La parcela se solapa con otra parcela del potrero. Pegá el borde a la vecina.")
        nombre = (body.nombre or "").strip() or repo.siguiente_nombre_parcela(conn, potrero_id, uid, pot.nombre)
    try:
        with engine.begin() as conn:
            row = repo.insertar_parcela(conn, uid, potrero_id, nombre, body.estado, gj_final)
    except IntegrityError:
        # Carrera por el mismo nombre auto: reintentar con el siguiente hueco.
        with engine.connect() as conn2:
            nombre = repo.siguiente_nombre_parcela(conn2, potrero_id, uid, pot.nombre)
        try:
            with engine.begin() as conn:
                row = repo.insertar_parcela(conn, uid, potrero_id, nombre, body.estado, gj_final)
        except IntegrityError:
            raise HTTPException(
                status_code=409, detail=f"Ya existe una parcela '{nombre}' en este potrero")
    return {
        "id": row.id, "potrero_id": potrero_id, "nombre": nombre,
        "estado": body.estado, "area_ha": float(row.area_ha),
    }


@router.get("/api/parcelas/{parcela_id}")
def detalle_parcela(
    parcela_id: int,
    fecha: Optional[date] = Query(None, description="Fecha YYYY-MM-DD para prorrateo"),
    uid: int = Depends(get_current_user_id),
):
    """Detalle de una parcela con promedio zonal real (misma fórmula que potrero)."""
    with engine.connect() as conn:
        pa = repo.obtener_parcela(conn, parcela_id, uid)
        if not pa:
            raise HTTPException(status_code=404, detail=f"Parcela {parcela_id} no existe o no es tuya")
        pot = repo.potrero_del_usuario(conn, pa.potrero_id, uid)
        fecha_iso = fecha.isoformat() if fecha else None
        pr = repo.stock_zonal_parcela(conn, parcela_id, uid, fecha_iso)
    return {
        "id": pa.id, "nombre": pa.nombre, "estado": pa.estado,
        "potrero_id": pa.potrero_id, "potrero": pot.nombre if pot else None,
        "finca": pot.finca if pot else None,
        "fecha": fecha_iso,
        "area_ha": pr.get("area_ha"), "geom": pa.geom_json, **pr,
    }


@router.patch("/api/parcelas/{parcela_id}")
def actualizar_parcela(
    parcela_id: int,
    body: ParcelaUpdate,
    uid: int = Depends(get_current_user_id),
):
    """Cambia estado / redibuja una parcela (el nombre es automático, no editable)."""
    with engine.connect() as conn:
        pa = repo.obtener_parcela(conn, parcela_id, uid)
        if not pa:
            raise HTTPException(status_code=404, detail=f"Parcela {parcela_id} no existe o no es tuya")
    if body.nombre is not None and body.nombre.strip() and body.nombre.strip() != pa.nombre:
        raise HTTPException(status_code=400, detail="El nombre es automático (Potrero_N) y no se puede renombrar.")
    gj_final = None
    if body.geom is not None:
        gj = repo.geom_geojson_text(body.geom)
        with engine.connect() as conn:
            chk = repo.validar_contenida(conn, gj, pa.potrero_id, uid)
            if not chk or not chk.valida:
                raise HTTPException(status_code=400, detail="Geometría inválida (autointersección)")
            if not chk.dentro:
                raise HTTPException(status_code=400, detail="La parcela debe estar dentro del potrero")
            rec = repo.geometria_recortada(conn, gj, pa.potrero_id, uid)
            gj_final = json.dumps(rec.geom_json) if rec and rec.geom_json else gj
            if float(rec.area_ha or 0) < 0.01:
                raise HTTPException(status_code=400, detail="Muy poco: la parcela útil es menor a 0.01 ha. Dibujá más grande.")
            if repo.hay_solape(conn, gj_final, pa.potrero_id, uid, excluir_id=parcela_id):
                raise HTTPException(status_code=409, detail="La nueva forma se solapa con otra parcela")
    sets, params = [], {"id": parcela_id, "uid": uid}
    if body.estado is not None:
        sets.append("estado = :estado")
        params["estado"] = body.estado
    if gj_final is not None:
        sets.append("geom = ST_SetSRID(ST_GeomFromGeoJSON(:gj), 4326)")
        params["gj"] = gj_final
    if not sets:
        raise HTTPException(status_code=400, detail="Nada para actualizar")
    try:
        with engine.begin() as conn:
            conn.execute(
                text(f"UPDATE parcelas SET {', '.join(sets)} WHERE id=:id AND usuario_id=:uid"),
                params,
            )
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Ya existe una parcela con ese nombre en el potrero")
    with engine.connect() as conn:
        pa2 = repo.obtener_parcela(conn, parcela_id, uid)
    return {
        "id": pa2.id, "potrero_id": pa2.potrero_id, "nombre": pa2.nombre,
        "estado": pa2.estado, "area_ha": float(pa2.area_ha),
    }


@router.delete("/api/parcelas/{parcela_id}")
def eliminar_parcela(
    parcela_id: int,
    uid: int = Depends(get_current_user_id),
):
    with engine.connect() as conn:
        pa = repo.obtener_parcela(conn, parcela_id, uid)
        if not pa:
            raise HTTPException(status_code=404, detail=f"Parcela {parcela_id} no existe o no es tuya")
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM parcelas WHERE id=:id AND usuario_id=:uid"),
            {"id": parcela_id, "uid": uid},
        )
    return {"id": parcela_id, "eliminado": True}
