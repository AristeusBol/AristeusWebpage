from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt
from sqlalchemy import text

from core.config import ALGORITHM, SECRET_KEY
from core.db import engine

security = HTTPBearer(auto_error=False)

MAX_EMAIL_LENGTH = 100
MIN_PASSWORD_LENGTH = 6


def email_valido(email: str) -> bool:
    return "@" in email and "." in email


def derivar_nombre(email: str) -> str:
    return email.split("@")[0].replace(".", " ").title()


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verificar_password(password: str, hash_guardado: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hash_guardado.encode("utf-8"))


def get_current_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> int:
    if credentials is None:
        raise HTTPException(status_code=401, detail="No autenticado: enviá Bearer token")
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido")
    sub = payload.get("sub")
    if sub is None:
        raise HTTPException(status_code=401, detail="Token inválido: sin sub")
    try:
        uid = int(sub)
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Token inválido: sin sub")
    with engine.connect() as conn:
        existe = conn.execute(text("SELECT 1 FROM usuarios WHERE id = :uid"), {"uid": uid}).fetchone()
    if not existe:
        raise HTTPException(status_code=401, detail="Usuario inexistente")
    return uid
