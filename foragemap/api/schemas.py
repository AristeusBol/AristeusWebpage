from typing import Optional
from pydantic import BaseModel


class UsuarioRegistro(BaseModel):
    email: str
    password: str


class UsuarioRespuesta(BaseModel):
    id: int
    nombre: str
    email: str


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginRespuesta(BaseModel):
    access_token: str
    token_type: str = "bearer"
    id: int
    nombre: str
    email: str


class TokenData(BaseModel):
    sub: Optional[str] = None
