# ForageMap

Motor analítico espacial y forrajero para ganadería de precisión. Ingesta de CSV a PostGIS (validación all-or-nothing) y cálculo de stock forrajero con persistencia en `calculos_stock`. API FastAPI + PostGIS + Vector Tiles (MVT).

> **Stack:** FastAPI · SQLAlchemy · PostGIS 15-3.4 · GeoPandas/Shapely · psycopg2 · bcrypt · python-jose (JWT HS256) · Docker

## Setup

### 1. Variables de entorno

```bash
cp .env.example .env
# .env.example trae:
# POSTGRES_USER=admin_forage
# POSTGRES_PASSWORD=password_local_123
# POSTGRES_DB=foragemap
# POSTGRES_HOST=localhost      # dentro de Docker Compose usa "db"
# POSTGRES_PORT=5433           # host:5433 -> container:5432
# CORS_ORIGINS=*               # coma-separado, ej: http://localhost:3000,http://localhost:5173
# Opcionales (con defaults en core/config.py:24 e infraestructura/docker-compose.yml:32):
# SECRET_KEY=dev-secret-key-change-in-production-please
# ALGORITHM=HS256
# ACCESS_TOKEN_EXPIRE_MINUTES=60
```

### 2. Levantar infraestructura (PostGIS + API)

```bash
# primera vez (con build):
docker compose -f infraestructura/docker-compose.yml up -d --build

# siguientes arranques:
docker compose -f infraestructura/docker-compose.yml up -d

# logs / estado:
docker compose -f infraestructura/docker-compose.yml logs --tail 50
docker compose -f infraestructura/docker-compose.yml ps
curl http://localhost:8000/health  # {"status":"ok","db":"up"}
curl http://localhost:8000/        # {"status":"ok","service":"foragemap-auth","version":"1.0.0"}
```

La BD se inicializa automáticamente con `infraestructura/init_db/98_esquema.sql` (PostGIS + tablas + índices GIST) y `99_seed_usuario.sql` (usuario seed `dpoloalcoba@gmail.com` / `123456`, id=1, para que los CSV con `usuario_id=1` tengan FK válida).

## Esquema BD (PostGIS)

`infraestructura/init_db/98_esquema.sql:1`

- `usuarios(id, nombre, email UNIQUE, password_hash)` — auth bcrypt
- `potreros_base(id, usuario_id FK CASCADE, nombre, finca, geom Polygon 4326)`
- `mapa_color(id, usuario_id FK, potrero_id FK, finca, fecha DATE, densidad_verde_g_m2, densidad_muerta_g_m2, densidad_total_g_m2, origen, geom Point 4326)` — índices `(usuario_id, finca, fecha)` y GIST `geom`
- `zonas_exclusion(id, usuario_id FK, potrero_id FK, finca, nombre, tipo, geom Polygon 4326)`
- `calculos_stock(id, usuario_id FK, potrero_id FK, finca, fecha, area_neta_ha, masa_seca_verde, masa_seca_muerta, masa_seca_total, UNIQUE(usuario_id, potrero_id, fecha))` — índice `(usuario_id, finca, fecha)` para dashboard/filtros
- `fotos_calibracion(id, usuario_id FK, potrero_id FK, finca, fecha DATE, geom Point 4326, foto_path, mime)` — titularidad compuesta `(usuario_id, potrero_id)` en todas las tablas hijas

Migraciones en BDs existentes: `.venv/bin/python scripts/migrar.py` (aplica `init_db/1*.sql` pendientes).

Unidades: densidad en **g/m²** (no g/ha), área por `ST_Area(geom::geography)` en **m²** → ha (`/10000`), masa en **kg** (`g/m² * m² / 1000`). Ver `motor_analitico/negocio.py:6`.

## Datos — Carga resumida

> Requerido antes de usar `/api/mapa/filtros` y `/api/dashboard/resumen` (leen `calculos_stock`).

| Tabla | Columnas (sin `id`) |
|-------|---------------------|
| `potreros_base` | `usuario_id, nombre, finca, wkt` |
| `zonas_exclusion` | `usuario_id, potrero_id, finca, nombre, tipo, wkt` |
| `mapa_color` | `usuario_id, potrero_id, finca, fecha, latitud, longitud, densidad_verde_g_m2, densidad_muerta_g_m2, densidad_total_g_m2, origen` *o* `wkt` en lugar de lat/long |

```bash
python motor_analitico/ingestar_csv.py --tabla potreros_base --archivo datos/potreros_base.csv
python motor_analitico/ingestar_csv.py --tabla zonas_exclusion --archivo datos/zonas_exclusion.csv
python motor_analitico/ingestar_csv.py --tabla mapa_color --archivo datos/mapa_color.csv  # --encoding latin-1 si viene de Excel
python motor_analitico/calcular_kilos_reales.py --potrero 1 --guardar  # pobla calculos_stock (repetir por potrero)
```
Validación `all-or-nothing`: si hay columnas faltantes, celdas vacías, WKT inválido o titularidad distinta (`mapa_color.usuario_id` vs `potreros_base.usuario_id`), no se inserta nada. Ver `motor_analitico/negocio.py:9` para unidades `g/m² → kg`.

## API — `api/main.py:7`

### Levantar

```bash
# Docker (recomendado): ya incluida en docker-compose
docker compose -f infraestructura/docker-compose.yml up -d --build  # http://localhost:8000

# Local sin Docker:
uvicorn api.main:app --reload  # http://localhost:8000/docs
```

Docs: `GET /docs` (Swagger), `GET /redoc`, `GET /openapi.json`.

### Autenticación

JWT HS256 (`SECRET_KEY`/`ALGORITHM` en `core/config.py:24`). Flujo:

1. `POST /api/auth/registro` → crea usuario (bcrypt) y guarda en `usuarios`.
2. `POST /api/auth/login` → verifica bcrypt + `jwt.encode({"sub": str(usuario_id)})` → `access_token`.
3. Rutas protegidas: `Authorization: Bearer <token>`. Sin token → `401`; token de usuario eliminado → `401`.

### Endpoints

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| `GET` | `/` | no | `{"status":"ok","service":"foragemap-auth","version":"1.0.0"}` |
| `GET` | `/health` | no | `{"status":"ok","db":"up"}` o `{"db":"down: ..."}` (chequea `SELECT 1`) |
| `POST` | `/api/auth/registro` | no | Body `{email, password}` (≥6 chars, email ≤100) → `201 {id, nombre, email}`. `400` si duplicado/inválido/largo |
| `POST` | `/api/auth/login` | no | Body `{email, password}` → `{access_token, token_type:"bearer", id, nombre, email}`. `401` si no existe o password mal |
| `GET` | `/api/mapa/filtros` | sí | Cascada filtros. Query `?finca=...` opcional. Resp `{fincas:[], fechas:[], tipos_densidad:["verde","muerta","total"], filtros_aplicados:{finca}}`. Usa `calculos_stock` (liviano) |
| `GET` | `/api/dashboard/resumen` | sí | `?finca=...&fecha=YYYY-MM-DD` requeridos. Agrega `SUM(area_neta_ha), SUM(masa_seca_*)` sobre `calculos_stock`. Resp `{filtros, metricas:{area:{total_ha}, masa_seca:{verde_kg, muerta_kg, total_kg}}, cobertura:{potreros_incluidos}, sin_datos}` |
| `GET` | `/api/mapa/geojson` | sí | `?finca=...&fecha=...&tipo_densidad=verde|muerta|total&limit=1000` (1..5000). FeatureCollection limitado (debug/export). `warning` si `count==limit` → preferir MVT |
| `GET` | `/api/mapa/tiles/{z}/{x}/{y}.pbf` | sí | Vector Tile MVT protobuf (`application/x-protobuf`). Query `?finca=...&fecha=...&tipo_densidad=...`. Clip `ST_AsMVTGeom(ST_TileEnvelope(z,x,y),4096)` + índice `GIST` |
| `GET` | `/api/mapa/histograma` | sí | `?finca=...&fecha=...&tipo_densidad=...&bins=20` (5..50). Distribución de peso por punto (kg): `{stats:{count,min,max,mean,unidad}, intervalos:[{lim_inf,lim_sup,count,pct}]}` |
| `GET` | `/api/dashboard/serie` | sí | `?finca=...[&potrero_id=...]` → `{filtros, puntos:[{fecha,area_ha,verde_kg,muerta_kg,total_kg,t_ha,potreros}]}`. `404` si el lote no es tuyo |
| `GET` | `/api/potreros` | sí | Lista `{potreros:[{id,nombre,finca}]}` del usuario |
| `GET` | `/api/potreros/{id}` | sí | Lote + exclusiones como GeoJSON. `404` si no existe o no es tuyo |
| `GET` | `/api/potreros/geojson` | sí | `?finca=...&fecha=...` → potreros con cálculo (`area_ha`, `masa_*_kg`, `t_ha_*`, `tiene_calculo`) |
| `POST` | `/api/calibracion/fotos` | sí | Multipart `{potrero_id,latitud,longitud,fecha,foto}` (imagen ≤25MB dentro del lote) → `201 {id,url}` |
| `GET` | `/api/calibracion/fotos` | sí | `?potrero_id=...` → galería `{count,fotos:[{id,url,fecha,latitud,longitud}]}`. Archivos en `/uploads` |

**Auth en protegidos:** `curl -H "Authorization: Bearer $TOKEN" ...`

**`tipo_densidad` es whitelist:** `verde→densidad_verde_g_m2`, `muerta→densidad_muerta_g_m2`, `total→densidad_total_g_m2` — cualquier otro → `400`.
