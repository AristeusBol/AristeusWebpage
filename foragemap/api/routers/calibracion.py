import os
import re
import uuid
from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from jose import jwt
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from core.config import ALGORITHM, SECRET_KEY
from core.db import engine
from core.seguridad import get_current_user_id
from repositorios import potreros as repo_potreros

router = APIRouter(tags=["calibracion"])

_REPO_ROOT = Path(__file__).resolve().parents[2]
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", _REPO_ROOT / "uploads"))
try:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    pass

MAX_BYTES = 25 * 1024 * 1024
# Cuotas anti-DoS de disco (configurables por env).
MAX_FOTOS_POR_POTRERO = int(os.environ.get("MAX_FOTOS_POR_POTRERO", "200"))
MAX_BYTES_POR_USUARIO = int(os.environ.get("MAX_BYTES_POR_USUARIO", str(500 * 1024 * 1024)))
_NOMBRE_ARCHIVO_RE = re.compile(r"^[0-9a-f]{32}\.(jpg|png|webp|heic|heif|tif)$")
_EXT_A_MIME = {
    ".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp",
    ".heic": "image/heic", ".heif": "image/heif", ".tif": "image/tiff",
}
MIME_A_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
    "image/heif": ".heif",
    "image/tiff": ".tif",
}
MARCAS_HEIC = {b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"hevm", b"hevs", b"mif1", b"msf1"}


def _detectar_mime(contenido: bytes) -> Optional[str]:
    if contenido.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if contenido.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if contenido.startswith(b"RIFF") and contenido[8:12] == b"WEBP":
        return "image/webp"
    if contenido.startswith(b"II*\x00") or contenido.startswith(b"MM\x00*"):
        return "image/tiff"
    if len(contenido) >= 12 and contenido[4:8] == b"ftyp" and contenido[8:12] in MARCAS_HEIC:
        return "image/heic"
    return None


def _uso_disco_usuario(uid: int) -> int:
    """Bytes totales en uploads/{uid}. 0 si no existe o ante error."""
    base = UPLOAD_DIR / str(uid)
    try:
        if not base.is_dir():
            return 0
        return sum(f.stat().st_size for f in base.iterdir() if f.is_file())
    except OSError:
        return 0


def _resolver_uid_archivo(request: Request) -> int:
    """Auth para <img>: Bearer header o ?token= (query, para tags sin headers)."""
    auth = request.headers.get("authorization", "")
    token = None
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
    elif request.query_params.get("token"):
        token = request.query_params.get("token")
    if not token:
        raise HTTPException(status_code=401, detail="No autenticado: enviá Bearer token")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido")
    try:
        uid = int(payload.get("sub"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Token inválido: sin sub")
    with engine.connect() as conn:
        existe = conn.execute(text("SELECT 1 FROM usuarios WHERE id = :uid"), {"uid": uid}).fetchone()
    if not existe:
        raise HTTPException(status_code=401, detail="Usuario inexistente")
    return uid


@router.get("/uploads/{uid_path}/{nombre}")
def servir_foto_privada(uid_path: int, nombre: str, request: Request):
    """Sirve una foto solo a su dueño (reemplaza el StaticFiles público).

    Acepta `Authorization: Bearer` o `?token=` para que <img> funcione.
    """
    uid = _resolver_uid_archivo(request)
    if uid != uid_path:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    if not _NOMBRE_ARCHIVO_RE.match(nombre):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    destino = UPLOAD_DIR / str(uid_path) / nombre
    try:
        resuelto = destino.resolve()
        if resuelto.parent != (UPLOAD_DIR / str(uid_path)).resolve():
            raise HTTPException(status_code=404, detail="Archivo no encontrado")
    except OSError:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    if not resuelto.is_file():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    # Titularidad a nivel de fila: el path debe existir en DB para ese usuario.
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT 1 FROM fotos_calibracion WHERE usuario_id=:uid AND foto_path=:p"),
            {"uid": uid, "p": f"{uid_path}/{nombre}"},
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return FileResponse(
        path=str(resuelto),
        media_type=_EXT_A_MIME.get(resuelto.suffix.lower(), "application/octet-stream"),
        headers={"Cache-Control": "private, max-age=300"},
    )


@router.get("/api/potreros")
def listar_mis_potreros(
    uid: int = Depends(get_current_user_id),
):
    """Lista liviana de potreros del usuario para el selector de calibración."""
    with engine.connect() as conn:
        rows = repo_potreros.listar_potreros(conn, uid)
    return {
        "potreros": [{"id": r.id, "nombre": r.nombre, "finca": r.finca} for r in rows],
    }


@router.get("/api/potreros/{potrero_id}")
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


@router.post("/api/calibracion/fotos", status_code=201)
async def subir_foto_calibracion(
    potrero_id: int = Form(...),
    latitud: float = Form(...),
    longitud: float = Form(...),
    fecha: date = Form(...),
    foto: UploadFile = File(...),
    uid: int = Depends(get_current_user_id),
):
    """Sube una foto de calibración. Devuelve {id, url}."""
    if not (-90 <= latitud <= 90 and -180 <= longitud <= 180):
        raise HTTPException(status_code=400, detail="Coordenadas fuera de rango")

    with engine.connect() as conn:
        res = conn.execute(
            text("""
                SELECT nombre, finca,
                       ST_Covers(geom, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)) AS dentro
                FROM potreros_base
                WHERE id = :pid AND usuario_id = :uid
            """),
            {"pid": potrero_id, "uid": uid, "lat": latitud, "lon": longitud},
        ).fetchone()
        if res is None:
            raise HTTPException(status_code=404, detail=f"Potrero {potrero_id} no existe o no es tuyo")
        if not res.dentro:
            raise HTTPException(
                status_code=400,
                detail="El punto cae fuera del potrero. Marcá un punto dentro del polígono.",
            )
        finca_nombre = res.finca
        potrero_nombre = res.nombre

    contenido = bytearray()
    while True:
        chunk = await foto.read(1024 * 1024)
        if not chunk:
            break
        contenido.extend(chunk)
        if len(contenido) > MAX_BYTES:
            raise HTTPException(status_code=400, detail="Archivo supera 25MB")
    contenido = bytes(contenido)
    if len(contenido) == 0:
        raise HTTPException(status_code=400, detail="Archivo vacío")
    mime = _detectar_mime(contenido)
    if mime is None:
        raise HTTPException(status_code=400, detail="El archivo no es una imagen válida (jpg/png/webp/heic/tif)")

    # Cuotas: cantidad por potrero y bytes totales por usuario (anti-DoS disco).
    with engine.connect() as conn:
        n_fotos = conn.execute(
            text("SELECT COUNT(*) AS n FROM fotos_calibracion WHERE usuario_id=:uid AND potrero_id=:pid"),
            {"uid": uid, "pid": potrero_id},
        ).fetchone()
    if n_fotos and int(n_fotos.n or 0) >= MAX_FOTOS_POR_POTRERO:
        raise HTTPException(status_code=409, detail=f"Límite de {MAX_FOTOS_POR_POTRERO} fotos por potrero alcanzado")
    if _uso_disco_usuario(uid) + len(contenido) > MAX_BYTES_POR_USUARIO:
        raise HTTPException(status_code=413, detail="Cuota de almacenamiento excedida")

    nombre_archivo = f"{uuid.uuid4().hex}{MIME_A_EXT[mime]}"
    destino = UPLOAD_DIR / str(uid) / nombre_archivo
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(contenido)
    foto_path = f"{uid}/{nombre_archivo}"

    try:
        with engine.begin() as conn:
            ins = conn.execute(
                text("""
                    INSERT INTO fotos_calibracion (usuario_id, potrero_id, finca, fecha, geom, foto_path, mime)
                    VALUES (:uid, :pid, :finca, :fecha,
                            ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), :path, :mime)
                    RETURNING id, created_at
                """),
                {
                    "uid": uid, "pid": potrero_id, "finca": finca_nombre, "fecha": fecha,
                    "lat": latitud, "lon": longitud, "path": foto_path, "mime": mime,
                },
            ).fetchone()
    except IntegrityError:
        try:
            destino.unlink(missing_ok=True)
        except OSError:
            pass
        raise HTTPException(status_code=404, detail="El potrero ya no existe o los datos cambiaron. Reintentá.")

    return {
        "id": ins.id,
        "url": f"/uploads/{foto_path}",
        "usuario_id": uid,
        "potrero_id": potrero_id,
        "potrero": potrero_nombre,
        "finca": finca_nombre,
        "fecha": fecha.isoformat(),
        "latitud": latitud,
        "longitud": longitud,
        "created_at": ins.created_at.isoformat() if hasattr(ins.created_at, "isoformat") else str(ins.created_at),
    }


@router.get("/api/calibracion/fotos")
def listar_fotos(
    potrero_id: int = Query(..., description="Potrero a listar"),
    uid: int = Depends(get_current_user_id),
):
    """Fotos de calibración del usuario para un potrero (galería)."""
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT id, fecha, ST_Y(geom) AS lat, ST_X(geom) AS lon,
                       foto_path, mime, created_at
                FROM fotos_calibracion
                WHERE usuario_id = :uid AND potrero_id = :pid
                ORDER BY created_at DESC
            """),
            {"uid": uid, "pid": potrero_id},
        ).fetchall()
    return {
        "potrero_id": potrero_id,
        "count": len(rows),
        "fotos": [
            {
                "id": r.id,
                "url": f"/uploads/{r.foto_path}",
                "fecha": r.fecha.isoformat() if hasattr(r.fecha, "isoformat") else str(r.fecha),
                "latitud": float(r.lat),
                "longitud": float(r.lon),
                "mime": r.mime,
                "created_at": r.created_at.isoformat() if hasattr(r.created_at, "isoformat") else str(r.created_at),
            }
            for r in rows
        ],
    }
