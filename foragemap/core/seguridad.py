from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt

from core.config import ALGORITHM, SECRET_KEY

# instancia compartida para todos los routers
security = HTTPBearer(auto_error=False)


def resolver_usuario_id(
    credentials: Optional[HTTPAuthorizationCredentials],
    usuario_id_query: Optional[int],
) -> int:
    # prioridad al token JWT, fallback a query solo para desarrollo
    if credentials:
        try:
            payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
            sub = payload.get("sub")
            if sub is None:
                raise HTTPException(status_code=401, detail="Token inválido: sin sub")
            return int(sub)
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expirado")
        except Exception:
            raise HTTPException(status_code=401, detail="Token inválido")
    if usuario_id_query is not None:
        return usuario_id_query
    raise HTTPException(status_code=401, detail="No autenticado: enviar Bearer token o ?usuario_id=")


def get_current_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> int:
    return resolver_usuario_id(credentials, None)
