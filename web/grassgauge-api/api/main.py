from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from core.config import CORS_ORIGINS
from api.routers import auth, balance, calibracion, dashboard, filtros, mapa, parcelas, potreros, rodeos, rotacion
from api.routers.calibracion import UPLOAD_DIR

app = FastAPI(
    title="GrassGauge API",
    description="Motor analítico espacial y forrajero: auth, filtros, mapa vectorial, dashboard y calibración",
    version="1.0.0",
)

_WILDCARD_CORS = len(CORS_ORIGINS) == 1 and CORS_ORIGINS[0] == "*"
# Comprime respuestas grandes (tiles MVT de 1MB+, GeoJSON): la red era
# gran parte de los ~25s por fecha. Solo actúa si el cliente manda
# Accept-Encoding: gzip (>= minimum_size bytes).
app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=6)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS if not _WILDCARD_CORS else ["*"],
    allow_credentials=not _WILDCARD_CORS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(filtros.router)
app.include_router(mapa.router)
app.include_router(dashboard.router)
app.include_router(potreros.router)
app.include_router(parcelas.router)
app.include_router(rodeos.router)
app.include_router(rotacion.router)
app.include_router(balance.router)
app.include_router(calibracion.router)

try:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    pass
if UPLOAD_DIR.exists():
    app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


@app.get("/", tags=["health"])
def health():
    """Estado del servicio."""
    return {"status": "ok", "service": "grassgauge-api", "version": "1.0.0"}


@app.get("/health", tags=["health"])
def health_check():
    """Estado del servicio y la base de datos."""
    from core.db import engine
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "db": "up"}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "db": f"down: {e}"},
        )
