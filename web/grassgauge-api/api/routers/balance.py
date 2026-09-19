from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text

from api.routers.parcelas import _zonales_finca
from api.routers.potreros import _prorrateo
from api.routers.rodeos import _consumo_diario
from core.db import engine
from core.seguridad import get_current_user_id
from repositorios import parcelas as repo_parcelas

router = APIRouter(prefix="/api/balance", tags=["balance"])

UMBRAL_URGENTE = 7.0
UMBRAL_ATENTO = 21.0
UTILIZACION_VALIDA = {40, 50, 60}
_RANK = {"urgente": 0, "atento": 1, "ok": 2, "sin_dato": 3, "libre": 4}


def _semaforo(ocupada: bool, tiene_calculo: bool, dias: Optional[float]) -> str:
    """Semáforo de días de pastoreo de una parcela."""
    if ocupada and tiene_calculo and dias is not None:
        if dias < UMBRAL_URGENTE:
            return "urgente"
        if dias <= UMBRAL_ATENTO:
            return "atento"
        return "ok"
    if ocupada:
        return "sin_dato"  # hay rodeo comiendo pero sin datos de oferta en la fecha
    return "libre"


def _ultima_fecha(conn, uid: int, finca: str):
    """Fecha más reciente con datos de forraje para la estancia.

    Prefiere calculos_stock (oferta cerrada); fallback a mapa_color
    (puntos sin calcular) para fincas recién cargadas."""
    row = conn.execute(
        text("""
            SELECT MAX(fecha) FROM calculos_stock
            WHERE usuario_id = :uid AND finca = :finca
        """),
        {"uid": uid, "finca": finca},
    ).fetchone()
    if row and row[0]:
        return row[0]
    row = conn.execute(
        text("""
            SELECT MAX(fecha) FROM mapa_color
            WHERE usuario_id = :uid AND finca = :finca
        """),
        {"uid": uid, "finca": finca},
    ).fetchone()
    return row[0] if row else None


@router.get("")
def get_balance(
    finca: str = Query(..., description="Estancia exacta, ej: Finca Don Carlos"),
    fecha: Optional[date] = Query(None, description="Fecha YYYY-MM-DD de la oferta de forraje"),
    utilizacion: int = Query(50, description="% de forraje aprovechable (40, 50 o 60)"),
    uid: int = Depends(get_current_user_id),
):
    """Balance por parcela: oferta (kg MS en la fecha) vs consumo actual de los rodeos.

    días de pastoreo = masa_seca_total × utilización% ÷ consumo_diario_actual.
    Parcela sin rodeo vigente = 'libre' (reserva). Sin datos de oferta en la
    fecha → fallback prorrateo del potrero.
    """
    finca_norm = (finca or "").strip()
    if not finca_norm:
        raise HTTPException(status_code=400, detail="estancia requerida")
    if utilizacion not in UTILIZACION_VALIDA:
        raise HTTPException(status_code=400, detail="utilización inválida (40, 50 o 60)")
    fecha_iso = fecha.isoformat() if fecha else None
    hoy = date.today()

    with engine.connect() as conn:
        if fecha_iso is None:
            ultima = _ultima_fecha(conn, uid, finca_norm)
            fecha_iso = ultima.isoformat() if ultima else None
        parcelas = repo_parcelas.listar_parcelas_finca(conn, uid, finca_norm)
        potrero_ids = sorted({int(r.potrero_id) for r in parcelas})
        if not parcelas:
            return {
                "fecha": fecha_iso, "finca": finca_norm,
                "utilizacion_pct": utilizacion,
                "resumen": {
                    "parcelas_total": 0, "consumo_diario_total_kg": 0.0,
                    "oferta_total_kg": 0.0, "parcelas_pastoreo": 0, "dias_promedio": None,
                },
                "parcelas": [],
            }

        potreros = conn.execute(
            text("SELECT id, nombre FROM potreros_base WHERE usuario_id=:uid AND id = ANY(:pids)"),
            {"uid": uid, "pids": potrero_ids},
        ).fetchall()
        potreros_nombre = {int(r.id): r.nombre for r in potreros}

        zonales = _zonales_finca(conn, uid, fecha_iso, parcelas)

        calcs = {}
        if fecha_iso:
            rows = conn.execute(
                text("""
                    SELECT potrero_id, area_neta_ha, masa_seca_verde, masa_seca_muerta, masa_seca_total
                    FROM calculos_stock
                    WHERE usuario_id=:uid AND fecha=:fecha AND potrero_id = ANY(:pids)
                """),
                {"uid": uid, "fecha": fecha_iso, "pids": potrero_ids},
            ).fetchall()
            calcs = {int(r.potrero_id): r for r in rows}

        asign = conn.execute(
            text("""
                SELECT p.id AS parcela_id, r.id AS rodeo_id, r.nombre AS rodeo,
                       r.cabezas, r.peso_prom_kg, r.consumo_pct
                FROM asignaciones a
                JOIN rodeos r ON r.id = a.rodeo_id AND r.usuario_id = a.usuario_id
                JOIN parcelas p ON p.id = a.parcela_id AND p.usuario_id = a.usuario_id
                JOIN potreros_base pt ON pt.id = p.potrero_id AND pt.usuario_id = p.usuario_id
                WHERE a.usuario_id = :uid
                  AND pt.finca = :finca
                  AND a.fecha_entrada <= :hoy
                  AND (a.fecha_salida IS NULL OR a.fecha_salida >= :hoy)
            """),
            {"uid": uid, "finca": finca_norm, "hoy": hoy},
        ).fetchall()

    demanda: dict[int, float] = {}
    items: dict[int, list] = {}
    for a in asign:
        pid = int(a.parcela_id)
        consumo = _consumo_diario(a.cabezas, a.peso_prom_kg, a.consumo_pct) or 0.0
        demanda[pid] = demanda.get(pid, 0.0) + consumo
        items.setdefault(pid, []).append({
            "rodeo_id": int(a.rodeo_id),
            "rodeo": a.rodeo,
            "cabezas": int(a.cabezas),
            "consumo_diario_kg": round(consumo, 1),
        })

    salida = []
    for r in parcelas:
        pid = int(r.id)
        z = zonales.get(pid)
        if z is not None and int(z.get("n_puntos") or 0) > 0:
            masa_total = z.get("masa_total_kg")
            t_ha = z.get("t_ha_total")
            tiene_calculo = bool(z.get("tiene_calculo"))
            estimado = False
            zonal = True
        else:
            pr = _prorrateo(float(r.area_ha) if r.area_ha is not None else None, calcs.get(int(r.potrero_id)))
            masa_total = pr.get("masa_total_kg")
            t_ha = pr.get("t_ha_total")
            tiene_calculo = bool(pr.get("tiene_calculo", False))
            estimado = bool(pr.get("estimado_por_prorrateo", False))

        consumo = demanda.get(pid, 0.0)
        ocupada = consumo > 0
        dias = None
        if ocupada and masa_total is not None and masa_total > 0:
            dias = masa_total * utilizacion / 100.0 / consumo

        salida.append({
            "parcela_id": pid,
            "parcela": r.nombre,
            "potrero_id": int(r.potrero_id),
            "potrero": potreros_nombre.get(int(r.potrero_id)),
            "finca": r.finca,
            "estado": r.estado,
            "area_ha": round(float(r.area_ha), 2) if r.area_ha is not None else None,
            "masa_total_kg": round(masa_total, 1) if masa_total is not None else None,
            "t_ha_total": round(t_ha, 2) if t_ha is not None else None,
            "tiene_calculo": tiene_calculo,
            "estimado_por_prorrateo": estimado,
            "consumo_diario_kg": round(consumo, 1) if consumo else None,
            "ocupada": ocupada,
            "rodeos": items.get(pid, []),
            "dias_pastoreo": round(dias, 1) if dias is not None else None,
            "semaforo": _semaforo(ocupada, tiene_calculo, dias),
        })

    salida.sort(key=lambda p: (
        _RANK.get(p["semaforo"], 9),
        p["dias_pastoreo"] is None,
        p["dias_pastoreo"] or 0,
        p["parcela"].lower(),
    ))

    con_dias = [p for p in salida if p["dias_pastoreo"] is not None]
    resumen = {
        "parcelas_total": len(salida),
        "consumo_diario_total_kg": round(sum(p["consumo_diario_kg"] or 0 for p in salida), 1),
        "oferta_total_kg": round(sum(p["masa_total_kg"] or 0 for p in salida), 1),
        "parcelas_pastoreo": sum(1 for p in salida if p["ocupada"]),
        "dias_promedio": round(sum(p["dias_pastoreo"] for p in con_dias) / len(con_dias), 1) if con_dias else None,
    }
    return {
        "fecha": fecha_iso,
        "finca": finca_norm,
        "utilizacion_pct": utilizacion,
        "resumen": resumen,
        "parcelas": salida,
    }