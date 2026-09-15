# GrassGauge Web

Frontend React + Vite + TypeScript + MapLibre GL JS para el backend GrassGauge
(FastAPI + PostGIS + MVT).

## Dev

```bash
cd web/grassgauge-web
cp .env.example .env   # opcional; vacío = usa proxy /api -> localhost:8000
npm install
npm run dev            # http://localhost:5173
```

Backend esperado en `http://localhost:8000`:
`docker compose -f ../infra/docker-compose.yml up -d --build`.

Login seed: `dpoloalcoba@gmail.com` / `123456`.

## Env

| Var | Uso |
|-----|-----|
| `VITE_API_URL` | Base API. Vacío en dev (proxy vite). En prod: URL pública API, ej. `https://api.tudominio.com`. |

## Rutas

- `/login`, `/registro` (públicas)
- `/mapa` (protegida, token `localStorage grassgauge_token`): filtros cascada
  `GET /api/mapa/filtros(?finca=)` → dashboard `GET /api/dashboard/resumen?finca&fecha`
  → mapa MVT `GET /api/mapa/tiles/{z}/{x}/{y}.pbf` (auth vía `transformRequest`) +
  link GeoJSON debug.

## Build / Docker

```bash
npm run build
# o imagen nginx (SPA):
docker build --build-arg VITE_API_URL=https://tu-api -t grassgauge-web .
docker run -p 8080:80 grassgauge-web
```

## Notas

- Si filtros viene vacío, falta `calculos_stock`: correr ingesta CSV + `calcular_kilos_reales.py --guardar`.
- Tiles vacíos (`200 b""`) son normales fuera de la finca/fecha.
