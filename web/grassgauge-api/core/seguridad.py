from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt
from sqlalchemy import text

from core.config import ALGORITHM, SECRET_KEY
from core.db import engine

security = HTTPBearer(auto_error=False)


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
