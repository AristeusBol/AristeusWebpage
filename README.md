
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

## Rendimiento del mapa de masa seca (celdas precalculadas)

El mapa de densidad sirve tiles MVT desde `mapa_celdas`: celdas de ~16x16m
ya recortadas por potrero y menos zonas de exclusión, generadas **una vez
por ingesta** (el hook de `ingestar_csv.py` lo hace solo; ~50-150ms por tile
en vez de ~2-7s construyéndolas por tile). Los MVT renderizados se cachean
en `mapa_tiles_cache` (compartida entre workers) + un LRU por worker.

El frontend llama **`POST /api/mapa/precalentar`** al abrir el mapa y al
dejar de moverlo (`moveend`, con debounce), pasando el bbox y zoom visibles:
el backend renderiza esa grilla en segundo plano, así cuando el navegador
pide los tiles ya están (o están siendo) cacheados. Es best-effort e
idempotente (TTL + dedupe), y el endpoint responde sin bloquear (~20ms).

- La API crea esas dos tablas y sus índices sola al arrancar (idempotente);
  en installs nuevos también están en `infra/init_db/003_mapa_celdas.sql`.
  El índice `idx_celdas_grupo_geom` es un GIST compuesto sobre
  `(usuario_id, finca, fecha, geom)` (requiere `btree_gist`): resuelve grupo
  + filtro espacial en un solo Index Cond.
- Backfill manual / regenerar tras tocar la BD:

```bash
cd grassgauge-api
python motor_analitico/precalcular_celdas.py                    # todos los grupos
python motor_analitico/precalcular_celdas.py --fecha 2026-09-14 # una fecha
```

- Si un (finca, fecha) queda sin celdas (p. ej. fallo al regenerar), el
  endpoint cae solo al cálculo on-the-fly: más lento pero correcto.
- Tras re-ingerir datos la caché de tiles se invalida sola para los grupos
  tocados; en el navegador, Ctrl+Shift+R si querés ignorar la del cliente.
- Si dos workers piden el mismo tile frío a la vez, un advisory lock de PG
  hace que uno calcule y el otro espere y lea el resultado (antes lo hacían
  los dos: era el pico de ~1.4s del z13 grande).

Medido sobre Aristeus (12 fechas x ~209k puntos, 65 potreros), pidiendo los
tiles de a 6 como el navegador:

| Viewport | Antes | Primera vista | Repetida |
| --- | --- | --- | --- |
| z13, 12 tiles | 9.1s | ~1.1s | ~0.04s |
| z14, 24 tiles | 5.7s | ~1.0s | ~0.07s |

Con el precalentado proactivo la primera vista del z14 baja a **~0.17s**
(desde ~0.64s sin avisar el viewport) y el pico por tile de ~0.5s a ~0.13s.
