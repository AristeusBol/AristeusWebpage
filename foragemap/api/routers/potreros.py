import json
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from api.schemas import PotreroCreate, PotreroUpdate
from core.db import engine
from core.seguridad import get_current_user_id
from repositorios import parcelas as repo_parcelas

router = APIRouter(prefix="/api/potreros", tags=["potreros"])


def _t_ha(masa_kg, area_ha) -> Optional[float]:
    try:
        if masa_kg is None or area_ha is None or float(area_ha) <= 0:
            return None
        return float(masa_kg) / 1000.0 / float(area_ha)
    except (TypeError, ValueError):
        return None


def _prorrateo(area_parcela_ha, calc):
    """Prorratea el cálculo del potrero padre a una parcela por área.

    Retorna dict con masas/t_ha + flag estimado_por_prorrateo.
    """
    if calc is None:
        return {
            "masa_verde_kg": None, "masa_muerta_kg": None, "masa_total_kg": None,
            "t_ha_verde": None, "t_ha_muerta": None, "t_ha_total": None,
            "tiene_calculo": False, "estimado_por_prorrateo": False,
        }
    try:
        area_neta = float(calc.area_neta_ha) if calc.area_neta_ha is not None else 0
    except (TypeError, ValueError):
        area_neta = 0
    if not area_neta or area_neta <= 0 or not area_parcela_ha or area_parcela_ha <= 0:
        return {
            "masa_verde_kg": None, "masa_muerta_kg": None, "masa_total_kg": None,
            "t_ha_verde": _t_ha(calc.masa_seca_verde, calc.area_neta_ha),
            "t_ha_muerta": _t_ha(calc.masa_seca_muerta, calc.area_neta_ha),
            "t_ha_total": _t_ha(calc.masa_seca_total, calc.area_neta_ha),
            "tiene_calculo": calc.masa_seca_total is not None,
            "estimado_por_prorrateo": False,
        }
    ratio = float(area_parcela_ha) / float(area_neta)
    verde = float(calc.masa_seca_verde) * ratio if calc.masa_seca_verde is not None else None
    muerta = float(calc.masa_seca_muerta) * ratio if calc.masa_seca_muerta is not None else None
    total = float(calc.masa_seca_total) * ratio if calc.masa_seca_total is not None else None
    return {
        "masa_verde_kg": verde, "masa_muerta_kg": muerta, "masa_total_kg": total,
        "t_ha_verde": _t_ha(calc.masa_seca_verde, calc.area_neta_ha),
        "t_ha_muerta": _t_ha(calc.masa_seca_muerta, calc.area_neta_ha),
        "t_ha_total": _t_ha(calc.masa_seca_total, calc.area_neta_ha),
        "tiene_calculo": total is not None,
        "estimado_por_prorrateo": total is not None,
    }


@router.get("/geojson")
def get_potreros_geojson(
    finca: str = Query(..., description="Finca exacta, ej: Finca Don Carlos"),
    fecha: Optional[date] = Query(None, description="Fecha YYYY-MM-DD del cálculo en calculos_stock (opcional en gestión)"),
    usuario_id_resuelto: int = Depends(get_current_user_id),
):
    """Potreros con su cálculo como GeoJSON. Devuelve FeatureCollection.

    `fecha` opcional: sin fecha devuelve solo áreas brutas (útil para gestión/dibujo
    antes de que existan cálculos).
    """
    finca_norm = finca.strip()
    if not finca_norm:
        raise HTTPException(status_code=400, detail="finca requerida")

    # Sin fecha: no joinear calculos_stock (evita fan-out: un feature por
    # potrero con solo área bruta). Con fecha: join por igualdad exacta.
    if fecha is None:
        sql = text("""
            SELECT p.id, p.nombre, p.finca,
                   ST_AsGeoJSON(p.geom)::json AS geom_json,
                   ST_Area(p.geom::geography) / 10000.0 AS area_bruta_ha,
                   NULL::numeric AS area_neta_ha, NULL::numeric AS masa_seca_verde,
                   NULL::numeric AS masa_seca_muerta, NULL::numeric AS masa_seca_total
            FROM potreros_base p
            WHERE p.usuario_id = :uid
              AND p.finca = :finca
            ORDER BY p.nombre ASC
        """)
        params = {"uid": usuario_id_resuelto, "finca": finca_norm}
    else:
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
        params = {"uid": usuario_id_resuelto, "finca": finca_norm, "fecha": fecha}
    with engine.connect() as conn:
        rows = conn.execute(sql, params).fetchall()

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
                "fecha": fecha.isoformat() if fecha else None,
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
            "fecha": fecha.isoformat() if fecha else None,
            "count": len(features),
            "con_calculo": sum(1 for f in features if f["properties"]["tiene_calculo"]),
        },
    }


@router.get("/fincas")
def listar_fincas_con_potreros(
    uid: int = Depends(get_current_user_id),
):
    """Fincas que tienen potreros (existen en potreros_base), aunque no tengan cálculos."""
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT DISTINCT finca FROM potreros_base
                WHERE usuario_id = :uid ORDER BY finca ASC
            """),
            {"uid": uid},
        ).fetchall()
    return {"fincas": [r.finca for r in rows]}


@router.post("", status_code=201)
def crear_potrero(
    body: PotreroCreate,
    uid: int = Depends(get_current_user_id),
):
    """Crea un potrero dibujado desde la interfaz. Devuelve {id, area_ha}."""
    gj = json.dumps(body.geom)
    # Validación + inserción en UNA sola transacción: si la geometría es
    # inválida o el área es insuficiente, se hace rollback y no queda
    # ningún residuo visible para otras transacciones.
    try:
        with engine.begin() as conn:
            chk_prev = conn.execute(
                text("""
                    SELECT ST_IsValid(ST_SetSRID(ST_GeomFromGeoJSON(:gj), 4326)) AS valida,
                           ST_Area(ST_SetSRID(ST_GeomFromGeoJSON(:gj), 4326)::geography) / 10000.0 AS area_ha
                """),
                {"gj": gj},
            ).fetchone()
            if not chk_prev or not chk_prev.valida:
                raise HTTPException(status_code=400, detail="Geometría inválida (autointersección). Redibujá el polígono.")
            if float(chk_prev.area_ha or 0) < 0.01:
                raise HTTPException(status_code=400, detail="Área mínima 0.01 ha. Dibujá un polígono más grande.")
            row = conn.execute(
                text("""
                    INSERT INTO potreros_base (usuario_id, nombre, finca, geom)
                    VALUES (:uid, :nombre, :finca,
                            ST_SetSRID(ST_GeomFromGeoJSON(:gj), 4326))
                    RETURNING id, ST_Area(geom::geography) / 10000.0 AS area_ha
                """),
                {"uid": uid, "nombre": body.nombre, "finca": body.finca, "gj": gj},
            ).fetchone()
    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail=f"Ya existe un potrero '{body.nombre}' en '{body.finca}'",
        )
    return {
        "id": row.id, "nombre": body.nombre, "finca": body.finca,
        "area_ha": float(row.area_ha),
    }


@router.patch("/{potrero_id}")
def actualizar_potrero(
    potrero_id: int,
    body: PotreroUpdate,
    uid: int = Depends(get_current_user_id),
):
    """Renombra / redibuja la geometría de un potrero propio.

    La `finca` es inmutable: cambiarla rompería el invariante
    `hija.finca == potreros_base.finca` que validan ingesta, tiles y
    dashboard. Para mover un lote, crear uno nuevo en la otra finca.
    """
    with engine.connect() as conn:
        existe = conn.execute(
            text("SELECT id, finca FROM potreros_base WHERE id=:pid AND usuario_id=:uid"),
            {"pid": potrero_id, "uid": uid},
        ).fetchone()
    if not existe:
        raise HTTPException(status_code=404, detail=f"Potrero {potrero_id} no existe o no es tuyo")
    if body.finca is not None and body.finca.strip() != (existe.finca or "").strip():
        raise HTTPException(
            status_code=400,
            detail="La finca no se puede cambiar (rompe titularidad de mapa/cálculos/exclusiones/fotos). Creá un potrero nuevo en la otra finca.",
        )
    sets = []
    params: dict = {"pid": potrero_id, "uid": uid}
    if body.nombre is not None:
        sets.append("nombre = :nombre")
        params["nombre"] = body.nombre
    if body.geom is not None:
        # Validar candidata ANTES de tocar la fila: validez, área mínima y
        # que ninguna parcela hija quede fuera del nuevo borde. Todo o nada.
        gj_cand = json.dumps(body.geom)
        with engine.connect() as conn:
            chk = conn.execute(
                text("""
                    SELECT ST_IsValid(ST_SetSRID(ST_GeomFromGeoJSON(:gj), 4326)) AS valida,
                           ST_Area(ST_SetSRID(ST_GeomFromGeoJSON(:gj), 4326)::geography)/10000.0 AS area_ha,
                           (SELECT COUNT(*) FROM parcelas
                             WHERE usuario_id=:uid AND potrero_id=:pid
                               AND NOT ST_Within(geom, ST_SetSRID(ST_GeomFromGeoJSON(:gj), 4326))) AS n_fuera
                """),
                {"gj": gj_cand, "pid": potrero_id, "uid": uid},
            ).fetchone()
        if not chk or not chk.valida:
            raise HTTPException(status_code=400, detail="Geometría inválida (autointersección)")
        if float(chk.area_ha or 0) < 0.01:
            raise HTTPException(status_code=400, detail="Área mínima 0.01 ha. Dibujá un polígono más grande.")
        if chk.n_fuera and int(chk.n_fuera or 0) > 0:
            raise HTTPException(
                status_code=400,
                detail=f"El nuevo borde deja {int(chk.n_fuera)} parcela(s) fuera. Ajustá las parcelas primero.",
            )
        sets.append("geom = ST_SetSRID(ST_GeomFromGeoJSON(:gj), 4326)")
        params["gj"] = gj_cand
    if not sets:
        raise HTTPException(status_code=400, detail="Nada para actualizar")
    try:
        with engine.begin() as conn:
            conn.execute(
                text(f"UPDATE potreros_base SET {', '.join(sets)} WHERE id=:pid AND usuario_id=:uid"),
                params,
            )
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Ya existe un potrero con ese nombre en la finca")
    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT id, nombre, finca, ST_Area(geom::geography)/10000.0 AS area_ha
                FROM potreros_base WHERE id=:pid AND usuario_id=:uid
            """),
            {"pid": potrero_id, "uid": uid},
        ).fetchone()
    return {"id": row.id, "nombre": row.nombre, "finca": row.finca, "area_ha": float(row.area_ha)}


@router.delete("/{potrero_id}")
def eliminar_potrero(
    potrero_id: int,
    uid: int = Depends(get_current_user_id),
):
    """Elimina un potrero propio (cascada a parcelas por FK) + archivos huérfanos."""
    from api.routers.calibracion import UPLOAD_DIR

    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT p.nombre,
                       (SELECT COUNT(*) FROM parcelas WHERE usuario_id=:uid AND potrero_id=:pid) AS n_parc,
                       (SELECT COUNT(*) FROM calculos_stock WHERE usuario_id=:uid AND potrero_id=:pid) AS n_calc
                FROM potreros_base p WHERE p.id=:pid AND p.usuario_id=:uid
            """),
            {"pid": potrero_id, "uid": uid},
        ).fetchone()
        fotos = conn.execute(
            text("SELECT foto_path FROM fotos_calibracion WHERE usuario_id=:uid AND potrero_id=:pid"),
            {"pid": potrero_id, "uid": uid},
        ).fetchall() if row else []
    if not row:
        raise HTTPException(status_code=404, detail=f"Potrero {potrero_id} no existe o no es tuyo")
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM potreros_base WHERE id=:pid AND usuario_id=:uid"),
            {"pid": potrero_id, "uid": uid},
        )
    # Limpieza de disco: las filas se fueron por CASCADE, los bytes no.
    fotos_borradas = 0
    for f in fotos:
        try:
            rel = (f.foto_path or "")
            # Solo paths propios con forma uid/archivo (anti path-traversal).
            base = (UPLOAD_DIR / str(uid)).resolve()
            cand = (UPLOAD_DIR / rel).resolve()
            if cand.parent == base and cand.is_file():
                cand.unlink()
                fotos_borradas += 1
        except OSError:
            continue
        except ValueError:
            continue
    return {
        "id": potrero_id, "eliminado": True,
        "parcelas_eliminadas": int(row.n_parc or 0),
        "calculos_eliminados": int(row.n_calc or 0),
        "fotos_eliminadas": fotos_borradas,
    }


@router.get("/{potrero_id}/detalle")
def detalle_potrero_gestion(
    potrero_id: int,
    fecha: Optional[date] = Query(None, description="Fecha YYYY-MM-DD para prorrateo forrajero"),
    uid: int = Depends(get_current_user_id),
):
    """Detalle para Gestión: potrero + parcelas (con prorrateo*) + exclusiones.

    El prorrateo estima cada parcela como `t/ha del potrero × área parcela`.
    """
    with engine.connect() as conn:
        if fecha is None:
            pot = conn.execute(
                text("""
                    SELECT p.id, p.nombre, p.finca,
                           ST_AsGeoJSON(p.geom)::json AS geom_json,
                           ST_Area(p.geom::geography)/10000.0 AS area_bruta_ha,
                           NULL::numeric AS area_neta_ha, NULL::numeric AS masa_seca_verde,
                           NULL::numeric AS masa_seca_muerta, NULL::numeric AS masa_seca_total
                    FROM potreros_base p
                    WHERE p.id=:pid AND p.usuario_id=:uid
                """),
                {"pid": potrero_id, "uid": uid},
            ).fetchone()
        else:
            pot = conn.execute(
                text("""
                    SELECT p.id, p.nombre, p.finca,
                           ST_AsGeoJSON(p.geom)::json AS geom_json,
                           ST_Area(p.geom::geography)/10000.0 AS area_bruta_ha,
                           c.area_neta_ha, c.masa_seca_verde, c.masa_seca_muerta, c.masa_seca_total
                    FROM potreros_base p
                    LEFT JOIN calculos_stock c ON c.potrero_id=p.id AND c.usuario_id=p.usuario_id
                           AND c.fecha=:fecha
                    WHERE p.id=:pid AND p.usuario_id=:uid
                """),
                {"pid": potrero_id, "uid": uid, "fecha": fecha},
            ).fetchone()
        if not pot:
            raise HTTPException(status_code=404, detail=f"Potrero {potrero_id} no existe o no es tuyo")
        calc = None
        if fecha is not None:
            calc = repo_parcelas.calculo_potrero(conn, potrero_id, uid, fecha.isoformat())
        parcelas = repo_parcelas.listar_parcelas_potrero(conn, potrero_id, uid)
        exclusiones = conn.execute(
            text("""
                SELECT id, nombre, tipo, ST_AsGeoJSON(geom)::json AS geom_json,
                       ST_Area(geom::geography)/10000.0 AS area_ha
                FROM zonas_exclusion WHERE potrero_id=:pid AND usuario_id=:uid
            """),
            {"pid": potrero_id, "uid": uid},
        ).fetchall()

    area_neta = float(pot.area_neta_ha) if pot.area_neta_ha is not None else None
    verde = float(pot.masa_seca_verde) if pot.masa_seca_verde is not None else None
    muerta = float(pot.masa_seca_muerta) if pot.masa_seca_muerta is not None else None
    total = float(pot.masa_seca_total) if pot.masa_seca_total is not None else None

    feats = [{
        "type": "Feature", "geometry": pot.geom_json,
        "properties": {
            "id": pot.id, "tipo": "potrero_base", "nombre": pot.nombre, "finca": pot.finca,
            "fecha": fecha.isoformat() if fecha else None,
            "area_bruta_ha": float(pot.area_bruta_ha) if pot.area_bruta_ha is not None else None,
            "area_neta_ha": area_neta, "masa_verde_kg": verde, "masa_muerta_kg": muerta,
            "masa_total_kg": total, "t_ha_verde": _t_ha(verde, area_neta),
            "t_ha_muerta": _t_ha(muerta, area_neta), "t_ha_total": _t_ha(total, area_neta),
            "tiene_calculo": total is not None, "estimado_por_prorrateo": False,
        },
    }]
    for pa in parcelas:
        area_pa = float(pa.area_ha) if pa.area_ha is not None else None
        pr = _prorrateo(area_pa, calc)
        feats.append({
            "type": "Feature", "geometry": pa.geom_json,
            "properties": {
                "id": pa.id, "tipo": "parcela", "nombre": pa.nombre, "finca": pot.finca,
                "potrero_id": pa.potrero_id, "estado": pa.estado,
                "fecha": fecha.isoformat() if fecha else None,
                "area_ha": area_pa, **pr,
            },
        })
    for ex in exclusiones:
        feats.append({
            "type": "Feature", "geometry": ex.geom_json,
            "properties": {
                "id": ex.id, "tipo": "exclusion", "nombre": ex.nombre,
                "subtipo": ex.tipo, "finca": pot.finca,
                "area_ha": float(ex.area_ha) if ex.area_ha is not None else None,
            },
        })
    return {
        "type": "FeatureCollection", "features": feats,
        "metadata": {
            "potrero_id": pot.id, "potrero": pot.nombre, "finca": pot.finca,
            "fecha": fecha.isoformat() if fecha else None,
            "parcelas": len(parcelas), "exclusiones": len(exclusiones),
            "nota": "* masas de parcela estimadas por prorrateo del potrero" if fecha else None,
        },
    }
