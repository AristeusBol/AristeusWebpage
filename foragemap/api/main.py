from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import CORS_ORIGINS
from api.routers import auth, dashboard, filtros, mapa

app = FastAPI(
    title="ForageMap API - Auth",
    description="API mínima: registro y login (solo correo y contraseña)",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(filtros.router)
app.include_router(mapa.router)
app.include_router(dashboard.router)


@app.get("/", tags=["health"])
def health():
    return {"status": "ok", "service": "foragemap-auth", "version": "1.0.0"}


@app.get("/health", tags=["health"])
def health_check():
    from core.db import engine
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db = "up"
    except Exception as e:
        db = f"down: {e}"
    return {"status": "ok", "db": db}
