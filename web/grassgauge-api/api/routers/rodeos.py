from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from api.schemas import CATEGORIAS_RODEO, RodeoCreate, RodeoUpdate
from core.db import engine
from core.seguridad import get_current_user_id

router = APIRouter(prefix="/api/rodeos", tags=["rodeos"])


def _consumo_diario(cabezas, peso_prom_kg, consumo_pct) -> Optional[float]:
    """kg MS/día que consume el rodeo: cabezas × peso × %/100."""
    try:
        if cabezas is None or peso_prom_kg is None or consumo_pct is None:
            return None
        return round(int(cabezas) * float(peso_prom_kg) * float(consumo_pct) / 100.0, 1)
    except (TypeError, ValueError):
        return None


def _fila(r) -> dict:
    return {
        "id": r.id,
        "nombre": r.nombre,
        "categoria": r.categoria,
        "categoria_label": CATEGORIAS_RODEO.get(r.categoria, {}).get("label", r.categoria),
        "cabezas": int(r.cabezas),
        "peso_prom_kg": float(r.peso_prom_kg),
        "consumo_pct": float(r.consumo_pct),
        "notas": r.notas,
        "color": r.color,
        "consumo_diario_ms_kg": _consumo_diario(r.cabezas, r.peso_prom_kg, r.consumo_pct),
    }


_CAMPOS = "id, nombre, categoria, cabezas, peso_prom_kg, consumo_pct, notas, color"


@router.get("")
def listar_rodeos(uid: int = Depends(get_current_user_id)):
    """Rodeos propios con consumo diario calculado (base del balance forrajero)."""
    with engine.connect() as conn:
        rows = conn.execute(
            text(f"""
                SELECT {_CAMPOS}
                FROM rodeos WHERE usuario_id = :uid ORDER BY nombre ASC
            """),
            {"uid": uid},
        ).fetchall()
    rodeos = [_fila(r) for r in rows]
    return {
        "rodeos": rodeos,
        "total_cabezas": sum(r["cabezas"] for r in rodeos),
        "total_consumo_diario_ms_kg": round(sum(r["consumo_diario_ms_kg"] or 0 for r in rodeos), 1),
    }


@router.post("", status_code=201)
def crear_rodeo(body: RodeoCreate, uid: int = Depends(get_current_user_id)):
    """Crea un rodeo. Sin consumo_pct se usa el sugerido de la categoría."""
    consumo = body.consumo_pct if body.consumo_pct is not None else CATEGORIAS_RODEO[body.categoria]["consumo"]
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text(f"""
                    INSERT INTO rodeos (usuario_id, nombre, categoria, cabezas, peso_prom_kg,
                                        consumo_pct, notas, color)
                    VALUES (:uid, :nombre, :cat, :cab, :peso, :cons, :notas, :color)
                    RETURNING {_CAMPOS}
                """),
                {
                    "uid": uid, "nombre": body.nombre, "cat": body.categoria,
                    "cab": body.cabezas, "peso": body.peso_prom_kg,
                    "cons": consumo, "notas": body.notas,
                    "color": body.color,
                },
            ).fetchone()
    except IntegrityError:
        raise HTTPException(status_code=409, detail=f"Ya existe un rodeo '{body.nombre}' con ese nombre o color")
    return _fila(row)


@router.patch("/{rodeo_id}")
def actualizar_rodeo(
    rodeo_id: int,
    body: RodeoUpdate,
    uid: int = Depends(get_current_user_id),
):
    """Actualiza un rodeo propio. Al cambiar de categoría sin consumo explícito,
    se aplica el sugerido de la nueva categoría."""
    with engine.connect() as conn:
        actual = conn.execute(
            text("SELECT id, categoria, consumo_pct FROM rodeos WHERE id = :rid AND usuario_id = :uid"),
            {"rid": rodeo_id, "uid": uid},
        ).fetchone()
    if not actual:
        raise HTTPException(status_code=404, detail=f"Rodeo {rodeo_id} no existe o no es tuyo")
    sets = []
    params: dict = {"rid": rodeo_id, "uid": uid}
    if body.nombre is not None:
        sets.append("nombre = :nombre")
        params["nombre"] = body.nombre
    if body.categoria is not None:
        sets.append("categoria = :categoria")
        params["categoria"] = body.categoria
    if body.cabezas is not None:
        sets.append("cabezas = :cabezas")
        params["cabezas"] = body.cabezas
    if body.peso_prom_kg is not None:
        sets.append("peso_prom_kg = :peso")
        params["peso"] = body.peso_prom_kg
    consumo = body.consumo_pct
    if consumo is None and body.categoria is not None and body.categoria != actual.categoria:
        consumo = CATEGORIAS_RODEO[body.categoria]["consumo"]
    if consumo is not None:
        sets.append("consumo_pct = :consumo")
        params["consumo"] = consumo
    if body.notas is not None:
        sets.append("notas = :notas")
        params["notas"] = body.notas
    if body.color is not None:
        sets.append("color = :color")
        params["color"] = body.color
    if not sets:
        raise HTTPException(status_code=400, detail="Nada para actualizar")
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text(f"""
                    UPDATE rodeos SET {", ".join(sets)}
                    WHERE id = :rid AND usuario_id = :uid
                    RETURNING {_CAMPOS}
                """),
                params,
            ).fetchone()
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Ya existe un rodeo con ese nombre o color")
    return _fila(row)


@router.delete("/{rodeo_id}")
def eliminar_rodeo(rodeo_id: int, uid: int = Depends(get_current_user_id)):
    """Elimina un rodeo propio."""
    with engine.begin() as conn:
        row = conn.execute(
            text("DELETE FROM rodeos WHERE id = :rid AND usuario_id = :uid RETURNING id"),
            {"rid": rodeo_id, "uid": uid},
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Rodeo {rodeo_id} no existe o no es tuyo")
    return {"id": rodeo_id, "eliminado": True}
