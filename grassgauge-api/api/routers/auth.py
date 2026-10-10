from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import APIRouter, HTTPException
from jose import jwt
from sqlalchemy.exc import IntegrityError

from core.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from core.db import engine
from repositorios import usuarios
from api.schemas import UsuarioRegistro, UsuarioRespuesta, LoginRequest, LoginRespuesta

router = APIRouter(prefix="/api/auth", tags=["auth"])


def crear_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


@router.post("/registro", response_model=UsuarioRespuesta, status_code=201)
def registro(payload: UsuarioRegistro):
    """Registra un usuario. Devuelve {id, nombre, email}."""
    email = payload.email.strip().lower()
    if "@" not in email or "." not in email:
        raise HTTPException(status_code=400, detail="Email inválido")
    if len(email) > 100:
        raise HTTPException(status_code=400, detail="Email demasiado largo (máx. 100)")
    if len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="Contraseña debe tener al menos 6 caracteres")
    if len(payload.password.encode("utf-8")) > 72:
        raise HTTPException(status_code=400, detail="Contraseña demasiado larga (máx. 72 bytes)")

    nombre_extraido = email.split("@")[0].replace(".", " ").title()
    try:
        salt = bcrypt.gensalt()
        hash_seguro = bcrypt.hashpw(payload.password.encode("utf-8"), salt).decode("utf-8")
    except ValueError:
        raise HTTPException(status_code=400, detail="Contraseña inválida")
    try:
        with engine.begin() as conn:
            nuevo_id = usuarios.insertar_usuario(conn, nombre_extraido, email, hash_seguro)
    except IntegrityError:
        raise HTTPException(status_code=400, detail=f"Email ya registrado: {email}")
    return UsuarioRespuesta(id=nuevo_id, nombre=nombre_extraido, email=email)


@router.post("/login", response_model=LoginRespuesta)
def login(payload: LoginRequest):
    """Inicia sesión. Devuelve {access_token, id, nombre, email}."""
    email = payload.email.strip().lower()
    with engine.connect() as conn:
        resultado = usuarios.obtener_por_email(conn, email)
    if not resultado:
        raise HTTPException(status_code=401, detail="Email no existe")
    usuario_id, nombre, hash_guardado = resultado
    try:
        ok = bcrypt.checkpw(payload.password.encode("utf-8"), hash_guardado.encode("utf-8"))
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")
    if not ok:
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")

    access_token = crear_access_token(data={"sub": str(usuario_id)})
    return LoginRespuesta(
        access_token=access_token,
        token_type="bearer",
        id=usuario_id,
        nombre=nombre,
        email=email,
    )
