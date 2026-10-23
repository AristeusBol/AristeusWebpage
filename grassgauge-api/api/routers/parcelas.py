import json
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from api.schemas import ParcelaCreate, ParcelaUpdate
from core.db import engine
from core.seguridad import get_current_user_id
from dominio.stock import prorrateo as _prorrateo
from repositorios import parcelas as repo
from repositorios.parcelas import zonales_finca as _zonales_finca

router = APIRouter(tags=["parcelas"])


def _potrero_o_404(conn, potrero_id, uid):
    pot = repo.potrero_del_usuario(conn, potrero_id, uid)
    if not pot:
        raise HTTPException(status_code=404, detail=f"Potrero {potrero_id} no existe o no es tuyo")
    return pot


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


@router.get("/api/potreros/{potrero_id}/parcelas")
def listar_parcelas(
    potrero_id: int,
    fecha: Optional[date] = Query(None, description="Fecha YYYY-MM-DD para promedio zonal"),
    uid: int = Depends(get_current_user_id),
):
    """Parcelas de un potrero como FeatureCollection (promedio zonal si hay fecha)."""
    with engine.connect() as conn:
        pot = _potrero_o_404(conn, potrero_id, uid)
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
        pot = _potrero_o_404(conn, potrero_id, uid)
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
        pot = _potrero_o_404(conn, potrero_id, uid)
        chk = repo.validar_contenida(conn, gj, potrero_id, uid)
        if not chk or not chk.valida:
            raise HTTPException(status_code=400, detail="Geometría inválida (autointersección). Redibujá el polígono.")
        if float(chk.fuera_m2 or 0) > repo.FUERA_TOL_M2:
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
            if float(chk.fuera_m2 or 0) > repo.FUERA_TOL_M2:
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
