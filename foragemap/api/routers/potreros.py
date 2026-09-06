from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text

from core.db import engine
from core.seguridad import get_current_user_id
from repositorios import potreros as repo_potreros

router = APIRouter(prefix="/api/potreros", tags=["potreros"])


def _t_ha(masa_kg, area_ha) -> Optional[float]:
    try:
        if masa_kg is None or area_ha is None or float(area_ha) <= 0:
            return None
        return float(masa_kg) / 1000.0 / float(area_ha)
    except (TypeError, ValueError):
        return None


@router.get("")
def listar_mis_potreros(
    uid: int = Depends(get_current_user_id),
):
    """Lista liviana de potreros del usuario para el selector de calibración."""
    with engine.connect() as conn:
        rows = repo_potreros.listar_potreros(conn, uid)
    return {
        "potreros": [{"id": r.id, "nombre": r.nombre, "finca": r.finca} for r in rows],
    }


@router.get("/geojson")
def get_potreros_geojson(
    finca: str = Query(..., description="Finca exacta, ej: Finca Don Carlos"),
    fecha: date = Query(..., description="Fecha YYYY-MM-DD del cálculo en calculos_stock"),
    usuario_id_resuelto: int = Depends(get_current_user_id),
):
    """Potreros con su cálculo como GeoJSON. Devuelve FeatureCollection."""
    finca_norm = finca.strip()
    if not finca_norm:
        raise HTTPException(status_code=400, detail="finca requerida")

    sql = text("""
        SELECT p.id, p.nombre, p.finca,
               ST_AsGeoJSON(p.geom)::json AS geom_json,
               ST_Area(p.geom::geography) / 10000.0 AS area_bruta_ha,
               c.area_neta_ha, c.masa_seca_verde, c.masa_seca_muerta, c.masa_seca_total
        FROM potreros_base p
        LEFT JOIN calculos_stock c
          ON c.potrero_id = p.id
         AND c.usuario_id = p.usuario_id
         AND c.fecha = :fecha
        WHERE p.usuario_id = :uid
          AND p.finca = :finca
        ORDER BY p.nombre ASC
    """)
    with engine.connect() as conn:
        rows = conn.execute(sql, {
            "uid": usuario_id_resuelto,
            "finca": finca_norm,
            "fecha": fecha,
        }).fetchall()

    features = []
    for r in rows:
        area_neta = float(r.area_neta_ha) if r.area_neta_ha is not None else None
        verde = float(r.masa_seca_verde) if r.masa_seca_verde is not None else None
        muerta = float(r.masa_seca_muerta) if r.masa_seca_muerta is not None else None
        total = float(r.masa_seca_total) if r.masa_seca_total is not None else None
        features.append({
            "type": "Feature",
            "geometry": r.geom_json,
            "properties": {
                "id": r.id,
                "nombre": r.nombre,
                "finca": r.finca,
                "fecha": fecha.isoformat(),
                "area_bruta_ha": float(r.area_bruta_ha) if r.area_bruta_ha is not None else None,
                "area_neta_ha": area_neta,
                "masa_verde_kg": verde,
                "masa_muerta_kg": muerta,
                "masa_total_kg": total,
                "t_ha_verde": _t_ha(verde, area_neta),
                "t_ha_muerta": _t_ha(muerta, area_neta),
                "t_ha_total": _t_ha(total, area_neta),
                "tiene_calculo": total is not None,
            },
        })

    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "finca": finca_norm,
            "fecha": fecha.isoformat(),
            "count": len(features),
            "con_calculo": sum(1 for f in features if f["properties"]["tiene_calculo"]),
        },
    }


@router.get("/{potrero_id}")
def detalle_potrero(
    potrero_id: int,
    uid: int = Depends(get_current_user_id),
):
    """Potrero + exclusiones como GeoJSON para el mapa de marcado de punto."""
    with engine.connect() as conn:
        fc = repo_potreros.potrero_y_exclusiones_geojson(conn, potrero_id, uid)
    if fc is None:
        raise HTTPException(status_code=404, detail=f"Potrero {potrero_id} no existe o no es tuyo")
    return fc
