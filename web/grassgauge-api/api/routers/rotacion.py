from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from api.routers.rodeos import _consumo_diario
from api.schemas import CATEGORIAS_RODEO, AsignacionCreate, AsignacionUpdate, FinalizarTrayectoria, SemanaCreate
from core.db import engine
from core.seguridad import get_current_user_id

router = APIRouter(prefix="/api/rotacion", tags=["rotacion"])

_FILAS_SQL = """
    SELECT a.id AS asignacion_id, a.fecha_entrada, a.fecha_salida, a.notas,
           a.trayectoria_inicio,
           r.id AS rodeo_id, r.nombre AS rodeo, r.categoria,
           r.cabezas, r.peso_prom_kg, r.consumo_pct,
           p.id AS parcela_id, p.nombre AS parcela, p.estado,
           pt.id AS potrero_id, pt.nombre AS potrero, pt.finca
    FROM asignaciones a
    JOIN rodeos r ON r.id = a.rodeo_id AND r.usuario_id = :uid
    JOIN parcelas p ON p.id = a.parcela_id AND p.usuario_id = :uid
    JOIN potreros_base pt ON pt.id = p.potrero_id AND pt.usuario_id = :uid
    WHERE a.usuario_id = :uid
"""


def _fila(r) -> dict:
    return {
        "id": r.asignacion_id,
        "rodeo_id": int(r.rodeo_id),
        "rodeo": r.rodeo,
        "categoria": r.categoria,
        "categoria_label": CATEGORIAS_RODEO.get(r.categoria, {}).get("label", r.categoria),
        "cabezas": int(r.cabezas),
        "peso_prom_kg": float(r.peso_prom_kg),
        "consumo_pct": float(r.consumo_pct),
        "consumo_diario_ms_kg": _consumo_diario(r.cabezas, r.peso_prom_kg, r.consumo_pct),
        "parcela_id": int(r.parcela_id),
        "parcela": r.parcela,
        "estado_parcela": r.estado,
        "potrero_id": int(r.potrero_id),
        "potrero": r.potrero,
        "finca": r.finca,
        "fecha_entrada": r.fecha_entrada.isoformat(),
        "fecha_salida": r.fecha_salida.isoformat() if r.fecha_salida else None,
        "notas": r.notas,
    }


def _vigente_hoy(row, hoy: date) -> bool:
    return row.fecha_entrada <= hoy and (row.fecha_salida is None or row.fecha_salida >= hoy)


def _consolidar_dias(dias, inicio: date):
    """Convierte los 7 días (cada uno con su lista de parcelas) en tramos continuos.

    Cada día puede tener varias parcelas: se comen en ese orden dentro del día.
    Una misma parcela en días seguidos (sin otra en medio) se fusiona en un solo
    stay [entrada, salida]. Devuelve lista de (parcela_id, fecha_entrada, fecha_salida).
    """
    pasos: list[tuple[int, date, date]] = []
    for i, dia in enumerate(dias):
        for pid in dia:
            if pasos and pasos[-1][0] == pid:
                ultimo_fin = (pasos[-1][2] - inicio).days
                if i == ultimo_fin + 1:
                    pasos[-1] = (pid, pasos[-1][1], inicio + timedelta(days=i))
                elif i == ultimo_fin:
                    continue  # misma parcela repetida el mismo día → ignorar
                else:
                    pasos.append((pid, inicio + timedelta(days=i), inicio + timedelta(days=i)))
            else:
                pasos.append((pid, inicio + timedelta(days=i), inicio + timedelta(days=i)))
    return pasos


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
        rows = conn.execute(
            text(_FILAS_SQL + " ORDER BY r.id ASC, a.fecha_entrada ASC, a.id ASC"),
            {"uid": uid},
        ).fetchall()
    with engine.connect() as conn:
        lotes = conn.execute(
            text("""
                SELECT id, nombre, color, cabezas, peso_prom_kg, consumo_pct
                FROM rodeos WHERE usuario_id = :uid
                ORDER BY nombre ASC
            """),
            {"uid": uid},
        ).fetchall()
    with engine.connect() as conn:
        fin = conn.execute(
            text("""
                SELECT rodeo_id, trayectoria_inicio, finalizada_en
                FROM trayectorias_finalizadas WHERE usuario_id = :uid
            """),
            {"uid": uid},
        ).fetchall()
    marcadas: dict[tuple[int, date], object] = {
        (int(f.rodeo_id), f.trayectoria_inicio): f.finalizada_en for f in fin
    }
    por_rodeo: dict[int, list] = {}
    for r in rows:
        por_rodeo.setdefault(int(r.rodeo_id), []).append(r)

    trayectoria = []
    for lote in lotes:
        by_grupo: dict[date | None, list] = {}
        for r in por_rodeo.get(int(lote.id), []):
            entrada = r.fecha_entrada
            salida = r.fecha_salida
            if salida is not None and salida < hoy:
                estado_etapa = "cerrada"
            elif entrada <= hoy and (salida is None or salida >= hoy):
                estado_etapa = "vigente"
            else:
                estado_etapa = "programada"
            fila = _fila(r)
            fila["trayectoria_inicio"] = r.trayectoria_inicio
            fila["estado_etapa"] = estado_etapa
            fila["dias_planificados"] = (salida - entrada).days + 1 if salida else None
            fila["dias_transcurridos"] = (hoy - entrada).days + 1 if entrada <= hoy else None
            by_grupo.setdefault(r.trayectoria_inicio, []).append(fila)

        trayectorias: list[dict] = []
        for inicio, etapas in by_grupo.items():
            trayectorias.append(_trayectoria_bloque(inicio, etapas))
        # Filas legadas sin grupo (migración no aplicada): se agrupan igual.
        if None in by_grupo:
            legado = [e for e in trayectorias if e["inicio"] is None]
            trayectorias = [e for e in trayectorias if e["inicio"] is not None]
            trayectorias.extend(_agrupar_legado(legado[0]["etapas"]))
        for t in trayectorias:
            t["finalizada"] = False
            t["finalizada_en"] = None
            if t["inicio"] is not None:
                marca = marcadas.get((int(lote.id), date.fromisoformat(t["inicio"])))
                if marca is not None:
                    t["finalizada"] = True
                    t["finalizada_en"] = marca.isoformat()
        trayectorias.sort(key=lambda t: t["inicio"], reverse=True)
        trayectoria.append({
            "rodeo_id": int(lote.id),
            "rodeo": lote.nombre,
            "color": lote.color,
            "cabezas": int(lote.cabezas),
            "peso_prom_kg": float(lote.peso_prom_kg),
            "consumo_pct": float(lote.consumo_pct),
            "consumo_diario_ms_kg": _consumo_diario(lote.cabezas, lote.peso_prom_kg, lote.consumo_pct),
            "trayectorias": trayectorias,
        })
    return {"trayectoria": trayectoria}


def _trayectoria_bloque(inicio: date | None, etapas: list) -> dict:
    """Bloque de una trayectoria: ventana de 7 días desde su inicio + etapas."""
    return {
        "inicio": inicio.isoformat() if inicio else None,
        "dias": [(inicio + timedelta(days=i)).isoformat() for i in range(7)] if inicio else None,
        "etapas": etapas,
    }


def _agrupar_legado(etapas: list[dict]) -> list[dict]:
    """Agrupa filas sin trayectoria_inicio en corridas independientes (misma
    heurística que la migración): nueva cuando hay hueco o cierre en domingo."""
    etapas = sorted(etapas, key=lambda e: (e["fecha_entrada"], e["id"]))
    corridas: list[list[dict]] = []
    prev_salida: date | None = None
    primer = True
    for e in etapas:
        entrada = date.fromisoformat(e["fecha_entrada"])
        salida = date.fromisoformat(e["fecha_salida"]) if e["fecha_salida"] else None
        nueva = primer or (
            prev_salida is not None
            and (prev_salida < entrada - timedelta(days=1) or prev_salida.weekday() == 6)
        )
        if nueva:
            corridas.append([e])
        else:
            corridas[-1].append(e)
        primer = False
        prev_salida = salida
    return [_trayectoria_bloque(date.fromisoformat(cor[0]["fecha_entrada"]), cor) for cor in corridas]


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
        # se está reemplazando: su grupo + filas legadas sin grupo y en su ventana).
        excluir_grupo = "FALSE" if body.reemplazar_inicio is None else """
            (trayectoria_inicio = :reemplazo
             OR (trayectoria_inicio IS NULL
                 AND fecha_entrada <= :fin AND (fecha_salida IS NULL OR fecha_salida >= :inicio)))"""
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
                conn.execute(
                    text("""
                        DELETE FROM asignaciones
                        WHERE usuario_id = :uid AND rodeo_id = :rid
                          AND (trayectoria_inicio = :reemplazo
                               OR (trayectoria_inicio IS NULL
                                   AND fecha_entrada <= :fin
                                   AND (fecha_salida IS NULL OR fecha_salida >= :inicio)))
                    """),
                    {"uid": uid, "rid": body.rodeo_id, "reemplazo": body.reemplazar_inicio,
                     "inicio": body.inicio, "fin": fin},
                )
                conn.execute(
                    text("""
                        DELETE FROM trayectorias_finalizadas
                        WHERE usuario_id = :uid AND rodeo_id = :rid AND trayectoria_inicio = :reemplazo
                    """),
                    {"uid": uid, "rid": body.rodeo_id, "reemplazo": body.reemplazar_inicio},
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
            for parcela_id in {p for p, _, _ in pasos}:
                conn.execute(
                    text("""
                        UPDATE parcelas
                        SET estado = 'critico'
                        WHERE id = :pid AND usuario_id = :uid
                    """),
                    {"pid": parcela_id, "uid": uid},
                )
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


@router.post("", status_code=201)
def crear_asignacion(body: AsignacionCreate, uid: int = Depends(get_current_user_id)):
    with engine.connect() as conn:
        rodeo = conn.execute(
            text("SELECT id FROM rodeos WHERE id = :rid AND usuario_id = :uid"),
            {"rid": body.rodeo_id, "uid": uid},
        ).fetchone()
        if not rodeo:
            raise HTTPException(status_code=404, detail=f"Rodeo {body.rodeo_id} no existe o no es tuyo")
        parcela = conn.execute(
            text("SELECT id FROM parcelas WHERE id = :pid AND usuario_id = :uid"),
            {"pid": body.parcela_id, "uid": uid},
        ).fetchone()
        if not parcela:
            raise HTTPException(status_code=404, detail=f"Parcela {body.parcela_id} no existe o no es tuya")
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text("""
                    INSERT INTO asignaciones (usuario_id, rodeo_id, parcela_id, fecha_entrada, fecha_salida, notas, trayectoria_inicio)
                    VALUES (:uid, :rid, :pid, :entrada, :salida, :notas, :trayectoria)
                    RETURNING id
                """),
                {
                    "uid": uid, "rid": body.rodeo_id, "pid": body.parcela_id,
                    "entrada": body.fecha_entrada, "salida": body.fecha_salida,
                    "notas": body.notas, "trayectoria": body.fecha_entrada,
                },
            ).fetchone()
    except IntegrityError:
        raise HTTPException(status_code=409, detail="No se pudo crear la asignación (conflicto de datos).")
    with engine.connect() as conn:
        creada = conn.execute(
            text(_FILAS_SQL + " AND a.id = :aid"),
            {"uid": uid, "aid": row.id},
        ).fetchone()
    return _fila(creada)


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


@router.delete("/{asignacion_id}")
def eliminar_asignacion(asignacion_id: int, uid: int = Depends(get_current_user_id)):
    with engine.begin() as conn:
        row = conn.execute(
            text("DELETE FROM asignaciones WHERE id = :aid AND usuario_id = :uid RETURNING id"),
            {"aid": asignacion_id, "uid": uid},
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Asignación {asignacion_id} no existe o no es tuya")
    return {"id": asignacion_id, "eliminado": True}


@router.delete("/trayectoria/{rodeo_id}/{inicio}")
def eliminar_trayectoria(rodeo_id: int, inicio: date, uid: int = Depends(get_current_user_id)):
    """Borra una trayectoria completa de un lote (ventana de 7 días desde inicio)."""
    fin = inicio + timedelta(days=6)
    with engine.begin() as conn:
        filas = conn.execute(
            text("""
                DELETE FROM asignaciones
                WHERE usuario_id = :uid AND rodeo_id = :rid
                  AND (trayectoria_inicio = :inicio
                       OR (trayectoria_inicio IS NULL
                           AND fecha_entrada <= :fin
                           AND (fecha_salida IS NULL OR fecha_salida >= :inicio)))
                RETURNING id
            """),
            {"uid": uid, "rid": rodeo_id, "inicio": inicio, "fin": fin},
        ).fetchall()
        conn.execute(
            text("""
                DELETE FROM trayectorias_finalizadas
                WHERE usuario_id = :uid AND rodeo_id = :rid AND trayectoria_inicio = :inicio
            """),
            {"uid": uid, "rid": rodeo_id, "inicio": inicio},
        )
    return {"inicio": inicio.isoformat(), "eliminado": True, "asignaciones": len(filas)}


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