
# GrassGauge

App de ganadería de precisión: mapa interactivo de biomasa y gestión de pastoreo.

## Estructura

| Carpeta | Qué es |
|---|---|
| `grassgauge-api/` | Backend FastAPI + PostGIS (auth, mapa vectorial, rotación, balance) |
| `grassgauge-web/` | Frontend React + Vite + MapLibre (mapa, series, rotación, calibración) |
| `infra/` | Docker Compose + scripts SQL de inicialización de la base |

## Poner a correr todo (dev)

```bash
# 1. Entorno (copiar ejemplos la primera vez)
cd grassgauge-api && cp .env.example .env && cd ..
cd grassgauge-web  && cp .env.example .env && cd ..

# 2. Base de datos + API (Docker)
docker compose -f infra/docker-compose.yml up -d --build

# 3. Frontend
cd grassgauge-web
npm install
npm run dev
```

- Web: http://localhost:5173 (proxy `/api` y `/uploads` → API).
- API: http://localhost:8000 — docs en http://localhost:8000/docs
- BD PostGIS: `localhost:5433` (inicializada automáticamente al primer arranque).
- Usuario de prueba: `dpoloalcoba@gmail.com` / `123456`

## Cómo levantar cada parte por separado

```bash
# Solo DB
docker compose -f infra/docker-compose.yml up -d db

# Solo API (local, requiere Python 3.11 y pip install -e .)
cd grassgauge-api
uvicorn api.main:app --reload

# Solo web (requiere API corriendo en :8000)
cd grassgauge-web
npm run dev
```

## Variables de entorno

`grassgauge-api/.env`

| Var | Default | Uso |
|---|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `admin_grassgauge` / `password_local_123` / `grassgauge` | Conexión a la BD (dentro de Docker el host es `db`, puerto 5432) |
| `POSTGRES_HOST` / `POSTGRES_PORT` | `localhost` / `5433` | Solo uso local sin Docker |
| `CORS_ORIGINS` | `*` | Orígenes permitidos (coma-separados) |

`grassgauge-web/.env`

| Var | Uso |
|---|---|
| `VITE_API_URL` | URL de la API. Vacío en dev (usa proxy); completo en producción |

## Nota sobre los datos

El mapa y los dashboards leen de `calculos_stock`. Si abrís la web y no hay estancias,
hay que cargar los CSV y calcular el stock:

```bash
cd grassgauge-api
python motor_analitico/ingestar_csv.py --tabla potreros_base   --archivo datos/potreros_base.csv
python motor_analitico/ingestar_csv.py --tabla zonas_exclusion --archivo datos/zonas_exclusion.csv
python motor_analitico/ingestar_csv.py --tabla mapa_color     --archivo datos/mapa_color.csv
python motor_analitico/calcular_kilos_reales.py --potrero 1 --guardar   # repetir por potrero
```
