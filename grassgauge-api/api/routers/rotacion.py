from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from api.schemas import AsignacionUpdate, FinalizarTrayectoria, SemanaCreate
from core.db import engine
from core.seguridad import get_current_user_id
from repositorios import rotacion as repo_rot
from repositorios.rotacion import FILAS_SQL as _FILAS_SQL
from servicios.rotacion import (
    consolidar_dias as _consolidar_dias,
    construir_trayectoria,
    fila_asignacion as _fila,
    vigente_hoy as _vigente_hoy,
)

router = APIRouter(prefix="/api/rotacion", tags=["rotacion"])


def _borrar_trayectoria(conn, params: dict, clave: str = "inicio") -> int:
    """Borra las asignaciones y la marca de finalizada de una trayectoria."""
    filas = conn.execute(
        text(f"""
            DELETE FROM asignaciones
            WHERE usuario_id = :uid AND rodeo_id = :rid AND trayectoria_inicio = :{clave}
            RETURNING id
        """),
        params,
    ).fetchall()
    conn.execute(
        text(f"""
            DELETE FROM trayectorias_finalizadas
            WHERE usuario_id = :uid AND rodeo_id = :rid AND trayectoria_inicio = :{clave}
        """),
        params,
    )
    return len(filas)


@router.get("")
def listar_rotacion(uid: int = Depends(get_current_user_id)):
    """Historial completo + estado actual (pastoreo vigente hoy) + resumen."""
    hoy = date.today()
    with engine.connect() as conn:
        rows = conn.execute(text(_FILAS_SQL + " ORDER BY a.fecha_entrada DESC, a.id DESC"), {"uid": uid}).fetchall()
    asignaciones = [_fila(r) for r in rows]

    vigentes = [r for r in rows if _vigente_hoy(r, hoy)]
    estado_actual = [_fila(r) for r in vigentes]

    rodeos_activos: dict[int, dict] = {}
    for f in estado_actual:
        if f["rodeo_id"] not in rodeos_activos:
            rodeos_activos[f["rodeo_id"]] = f
    resumen = {
        "rodeos_pastoreando": len(rodeos_activos),
        "cabezas_pastoreando": sum(f["cabezas"] for f in rodeos_activos.values()),
        "consumo_diario_ms_kg": round(sum(f["consumo_diario_ms_kg"] or 0 for f in rodeos_activos.values()), 1),
        "parcelas_ocupadas": len(estado_actual),
        "parcelas_total": len({f["parcela_id"] for f in asignaciones}),
    }
    return {"asignaciones": asignaciones, "estado_actual": estado_actual, "resumen": resumen}


@router.get("/trayectoria")
def trayectoria_rotacion(uid: int = Depends(get_current_user_id)):
    """Trayectorias independientes por lote: cada trayectoria (ventana de
    hasta 7 días desde su inicio) en su propio bloque con sus etapas
    (cerradas → vigente → programadas). Las finalizadas se marcan para el
    historial (Rotaciones finalizadas)."""
    hoy = date.today()
    with engine.connect() as conn:
        rows = repo_rot.listar_asignaciones(conn, uid, " ORDER BY r.id ASC, a.fecha_entrada ASC, a.id ASC")
        lotes = repo_rot.listar_lotes(conn, uid)
        fin = repo_rot.listar_finalizadas(conn, uid)
    return construir_trayectoria(rows, lotes, fin, hoy)


@router.post("/semana", status_code=200)
def armar_semana(body: SemanaCreate, uid: int = Depends(get_current_user_id)):
    """Reescribe la trayectoria de un lote: ventana fija de hasta 7 días.

    dias[i] es la lista de parcelas del día inicio+i ([] = libre o bloqueado).
    Los días ya cubiertos por OTRA trayectoria del mismo lote no se pueden
    ocupar (no se repiten días): se rechaza con 409. Cada trayectoria queda
    identificada por trayectoria_inicio (= body.inicio); al editar,
    reemplazar_inicio señala el grupo anterior a borrar (null = nueva)."""
    fechas = [body.inicio + timedelta(days=i) for i in range(len(body.dias))]
    fin = fechas[-1]
    with engine.connect() as conn:
        rodeo = conn.execute(
            text("SELECT id, nombre FROM rodeos WHERE id = :rid AND usuario_id = :uid"),
            {"rid": body.rodeo_id, "uid": uid},
        ).fetchone()
        if not rodeo:
            raise HTTPException(status_code=404, detail=f"Rodeo {body.rodeo_id} no existe o no es tuyo")
        usadas: set[int] = {p for dia in body.dias for p in dia}
        nombres: dict[int, str] = {}
        for pid in usadas:
            parcela = conn.execute(
                text("SELECT id, nombre FROM parcelas WHERE id = :pid AND usuario_id = :uid"),
                {"pid": pid, "uid": uid},
            ).fetchone()
            if not parcela:
                raise HTTPException(status_code=404, detail=f"Parcela {pid} no existe o no es tuya")
            nombres[pid] = parcela.nombre
        # Mismo lote: días ya cubiertos por otras trayectorias (excepto la que
        # se está reemplazando: su grupo).
        excluir_grupo = "FALSE" if body.reemplazar_inicio is None else \
            "trayectoria_inicio = :reemplazo"
        cruzadas = conn.execute(
            text(f"""
                SELECT fecha_entrada, fecha_salida
                FROM asignaciones
                WHERE usuario_id = :uid AND rodeo_id = :rid
                  AND fecha_entrada <= :fin
                  AND (fecha_salida IS NULL OR fecha_salida >= :inicio)
                  AND NOT {excluir_grupo}
            """),
            {"uid": uid, "rid": body.rodeo_id, "reemplazo": body.reemplazar_inicio,
             "inicio": body.inicio, "fin": fin},
        ).fetchall()
        ocupados: set[date] = set()
        for f in cruzadas:
            lo = max(f.fecha_entrada, body.inicio)
            hi = min(f.fecha_salida or fin, fin)
            d = lo
            while d <= hi:
                ocupados.add(d)
                d += timedelta(days=1)
        for i, f in enumerate(fechas):
            if body.dias[i] and f in ocupados:
                raise HTTPException(
                    status_code=409,
                    detail="Se repiten días con otra trayectoria del lote. "
                           "Empezá el trayecto el día siguiente al que termina la anterior.",
                )
    try:
        with engine.begin() as conn:
            if usadas:
                ocupadas = conn.execute(
                    text("""
                        SELECT DISTINCT a.parcela_id
                        FROM asignaciones a
                        WHERE a.usuario_id = :uid AND a.rodeo_id != :rid
                          AND a.fecha_entrada <= :fin
                          AND (a.fecha_salida IS NULL OR a.fecha_salida >= :inicio)
                    """),
                    {"uid": uid, "rid": body.rodeo_id, "inicio": body.inicio, "fin": fin},
                ).fetchall()
                choques = [nombres[p.parcela_id] for p in ocupadas if p.parcela_id in usadas]
                if choques:
                    raise HTTPException(
                        status_code=409,
                        detail=f"Potreros ya usados por otro rodeo esa semana: {', '.join(sorted(choques))}",
                    )
            if body.reemplazar_inicio is not None:
                _borrar_trayectoria(
                    conn,
                    {"uid": uid, "rid": body.rodeo_id, "reemplazo": body.reemplazar_inicio},
                    "reemplazo",
                )
            pasos = _consolidar_dias(body.dias, body.inicio)
            for pid, entrada, salida in pasos:
                conn.execute(
                    text("""
                        INSERT INTO asignaciones (usuario_id, rodeo_id, parcela_id, fecha_entrada, fecha_salida, trayectoria_inicio)
                        VALUES (:uid, :rid, :pid, :entrada, :salida, :trayectoria)
                    """),
                    {"uid": uid, "rid": body.rodeo_id, "pid": pid,
                     "entrada": entrada, "salida": salida, "trayectoria": body.inicio},
                )
            # NOTA: guardar NO toca parcelas.estado. Solo el finalizar con
            # enviar_critico (pregunta explícita en la UI) marca a crítico.
    except HTTPException:
        raise
    except IntegrityError:
        raise HTTPException(status_code=409, detail="No se pudo guardar la semana (conflicto de datos).")
    return {
        "guardado": True,
        "inicio": body.inicio.isoformat(),
        "dias": [
            {
                "fecha": f.isoformat(),
                "parcelas": [
                    {"parcela_id": pid, "parcela": nombres.get(pid)}
                    for pid in body.dias[i]
                ],
            }
            for i, f in enumerate(fechas)
        ],
    }


@router.patch("/{asignacion_id}")
def actualizar_asignacion(
    asignacion_id: int,
    body: AsignacionUpdate,
    uid: int = Depends(get_current_user_id),
):
    """Cierra un pastoreo (fecha_salida) o edita notas."""
    with engine.connect() as conn:
        actual = conn.execute(
            text("SELECT id, fecha_entrada FROM asignaciones WHERE id = :aid AND usuario_id = :uid"),
            {"aid": asignacion_id, "uid": uid},
        ).fetchone()
        if not actual:
            raise HTTPException(status_code=404, detail=f"Asignación {asignacion_id} no existe o no es tuya")
        if body.fecha_salida is not None and body.fecha_salida < actual.fecha_entrada:
            raise HTTPException(status_code=400, detail="fecha_salida no puede ser anterior a fecha_entrada")
    sets, params = [], {"aid": asignacion_id, "uid": uid}
    if body.fecha_salida is not None:
        sets.append("fecha_salida = :salida")
        params["salida"] = body.fecha_salida
    if body.notas is not None:
        sets.append("notas = :notas")
        params["notas"] = body.notas
    if not sets:
        raise HTTPException(status_code=400, detail="Nada para actualizar")
    with engine.begin() as conn:
        conn.execute(text(f"UPDATE asignaciones SET {', '.join(sets)} WHERE id = :aid AND usuario_id = :uid"), params)
    with engine.connect() as conn:
        fila = conn.execute(
            text(_FILAS_SQL + " AND a.id = :aid"),
            {"uid": uid, "aid": asignacion_id},
        ).fetchone()
    return _fila(fila)


@router.delete("/trayectoria/{rodeo_id}/{inicio}")
def eliminar_trayectoria(rodeo_id: int, inicio: date, uid: int = Depends(get_current_user_id)):
    """Borra una trayectoria completa de un lote (ventana de 7 días desde inicio)."""
    with engine.begin() as conn:
        borradas = _borrar_trayectoria(conn, {"uid": uid, "rid": rodeo_id, "inicio": inicio})
    return {"inicio": inicio.isoformat(), "eliminado": True, "asignaciones": borradas}


@router.post("/trayectoria/{rodeo_id}/{inicio}/finalizar")
def finalizar_trayectoria(rodeo_id: int, inicio: date,
                          body: FinalizarTrayectoria | None = None,
                          uid: int = Depends(get_current_user_id)):
    """Marca una trayectoria como finalizada (pasa al historial del lote).
    Si `body.enviar_critico`, las parcelas de ese camino pasan a estado 'critico'."""
    with engine.connect() as conn:
        vive = conn.execute(
            text("""
                SELECT 1 FROM asignaciones
                WHERE usuario_id = :uid AND rodeo_id = :rid AND trayectoria_inicio = :inicio
                LIMIT 1
            """),
            {"uid": uid, "rid": rodeo_id, "inicio": inicio},
        ).fetchone()
    if not vive:
        raise HTTPException(status_code=404, detail="La trayectoria no existe o no es tuya")
    con_critico = bool(body is not None and body.enviar_critico)
    n_critico = 0
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO trayectorias_finalizadas (usuario_id, rodeo_id, trayectoria_inicio, finalizada_en)
                VALUES (:uid, :rid, :inicio, now())
                ON CONFLICT (usuario_id, rodeo_id, trayectoria_inicio) DO NOTHING
            """),
            {"uid": uid, "rid": rodeo_id, "inicio": inicio},
        )
        if con_critico:
            criticas = conn.execute(
                text("""
                    UPDATE parcelas SET estado = 'critico'
                    WHERE usuario_id = :uid AND id IN (
                        SELECT DISTINCT parcela_id FROM asignaciones
                        WHERE usuario_id = :uid AND rodeo_id = :rid AND trayectoria_inicio = :inicio
                    )
                    RETURNING id
                """),
                {"uid": uid, "rid": rodeo_id, "inicio": inicio},
            ).fetchall()
            n_critico = len(criticas)
    return {"inicio": inicio.isoformat(), "finalizada": True, "parcelas_a_critico": n_critico}