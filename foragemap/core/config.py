import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

PG_USER = os.environ.get("POSTGRES_USER", "admin_forage")
PG_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "password_local_123")
PG_DB = os.environ.get("POSTGRES_DB", "foragemap")
PG_HOST = os.environ.get("POSTGRES_HOST", "localhost")
PG_PORT = os.environ.get("POSTGRES_PORT", "5433")

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    f"postgresql://{PG_USER}:{quote_plus(PG_PASSWORD)}@{PG_HOST}:{PG_PORT}/{PG_DB}",
)

DATOS_DIR = Path(__file__).resolve().parents[1] / "datos"

CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()]

ENV = os.environ.get("ENV", os.environ.get("APP_ENV", "dev")).lower()

_DEFAULT_SECRET = "dev-secret-key-change-in-production-please"
SECRET_KEY = os.environ.get("SECRET_KEY") or _DEFAULT_SECRET
if ENV == "production":
    if not SECRET_KEY or SECRET_KEY == _DEFAULT_SECRET or len(SECRET_KEY) < 32:
        raise RuntimeError(
            "SECRET_KEY insegura: definí SECRET_KEY de al menos 32 caracteres para ENV=production"
        )
ALGORITHM = os.environ.get("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))