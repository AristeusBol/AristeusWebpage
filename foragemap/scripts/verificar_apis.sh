#!/usr/bin/env bash

set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
EMAIL="${EMAIL:-dpoloalcoba@gmail.com}"
PASSWORD="${PASSWORD:-123456}"
FINCA="${FINCA:-Finca Don Carlos}"
FECHA="${FECHA:-2026-08-31}"
TIPO="${TIPO:-verde}"

GREEN='\033[0;32m'; RED='\033[0;31m'; YEL='\033[0;33m'; NC='\033[0m'

pass=0; fail=0

ok()   { echo -e "${GREEN}[OK]${NC} $1"; pass=$((pass+1)); }
fail_(){ echo -e "${RED}[FAIL]${NC} $1"; fail=$((fail+1)); }
info() { echo -e "${YEL}[*]${NC} $1"; }

curl_status() {
  local url="$1"; shift
  curl -s -o /tmp/_body -w "%{http_code}" "$url" "$@" || echo "000"
}

extract_token() {
  python3 -c "import sys,json; d=json.load(open('/tmp/_body')); print(d.get('access_token',''))"
}

info "BASE_URL=$BASE_URL EMAIL=$EMAIL FINCA=$FINCA FECHA=$FECHA TIPO=$TIPO"
echo "------------------------------------------------------------"

info "1/7 GET /"
code=$(curl_status "$BASE_URL/")
if [[ "$code" == "200" ]] && grep -q '"status":"ok"' /tmp/_body; then ok "GET / 200"; else fail_ "GET / $code $(cat /tmp/_body | head -c 200)"; fi

info "2/7 GET /health (DB up?)"
code=$(curl_status "$BASE_URL/health")
if [[ "$code" == "200" ]] && grep -q '"db":"up"' /tmp/_body; then ok "GET /health db:up"; else fail_ "GET /health $code $(cat /tmp/_body | head -c 300)"; cat /tmp/_body; fi

info "3/7 GET /openapi.json"
code=$(curl_status "$BASE_URL/openapi.json")
if [[ "$code" == "200" ]] && grep -q '"openapi"' /tmp/_body; then ok "GET /openapi.json 200"; else fail_ "GET /openapi.json $code"; fi

info "4/7 POST /api/auth/login"
code=$(curl -s -o /tmp/_body -w "%{http_code}" -X POST "$BASE_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")
if [[ "$code" == "200" ]] && grep -q "access_token" /tmp/_body; then
  ok "POST /api/auth/login 200"
  TOKEN=$(extract_token)
  if [[ -z "$TOKEN" ]]; then fail_ "Token vacío"; else info "Token: ${TOKEN:0:20}..."; fi
else
  fail_ "POST /api/auth/login $code $(cat /tmp/_body | head -c 500)"
  echo "TIP: ¿Usuario seed aplicado? Revisa usuarios: PSQL SELECT * FROM usuarios; o usa -- registro si es primer arranque."
  TOKEN=""
fi

AUTH_HEADER=()
if [[ -n "${TOKEN:-}" ]]; then
  AUTH_HEADER=(-H "Authorization: Bearer $TOKEN")
  UID_PARAM=""
else
  info "Sin token, usando fallback ?usuario_id=1 (solo dev)"
  UID_PARAM="&usuario_id=1"
fi

info "5/7 GET /api/mapa/filtros"
url="$BASE_URL/api/mapa/filtros?usuario_id=1"
if [[ -n "${TOKEN:-}" ]]; then url="$BASE_URL/api/mapa/filtros"; fi
code=$(curl_status "$url" "${AUTH_HEADER[@]}")
if [[ "$code" == "200" ]] && grep -q '"fincas"' /tmp/_body; then
  ok "GET /api/mapa/filtros 200"
  python3 -c "import json; d=json.load(open('/tmp/_body')); print('  fincas:',d.get('fincas'), 'fechas:',d.get('fechas'), 'tipos:',d.get('tipos_densidad'))"
else
  fail_ "GET /api/mapa/filtros $code $(cat /tmp/_body | head -c 500)"
fi

info "6/7 GET /api/dashboard/resumen"
enc_finca=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$FINCA'))")
url="$BASE_URL/api/dashboard/resumen?finca=$enc_finca&fecha=$FECHA$UID_PARAM"
if [[ -n "${TOKEN:-}" ]]; then url="$BASE_URL/api/dashboard/resumen?finca=$enc_finca&fecha=$FECHA"; fi
code=$(curl_status "$url" "${AUTH_HEADER[@]}")
if [[ "$code" == "200" ]] && grep -q '"metricas"' /tmp/_body; then
  ok "GET /api/dashboard/resumen 200"
  python3 -c "
import json
d=json.load(open('/tmp/_body'))
m=d.get('metricas',{})
print('  filtros:',d.get('filtros'))
print('  area ha:',m.get('area',{}).get('total_ha'))
print('  masa total kg:',m.get('masa_seca',{}).get('total_kg'))
print('  potreros:',d.get('cobertura',{}).get('potreros_incluidos'), 'sin_datos:',d.get('sin_datos'))
"
else
  fail_ "GET /api/dashboard/resumen $code $(cat /tmp/_body | head -c 700)"
fi

info "7/7 GET /api/mapa/geojson"
url="$BASE_URL/api/mapa/geojson?finca=$enc_finca&fecha=$FECHA&tipo_densidad=$TIPO$UID_PARAM"
if [[ -n "${TOKEN:-}" ]]; then url="$BASE_URL/api/mapa/geojson?finca=$enc_finca&fecha=$FECHA&tipo_densidad=$TIPO"; fi
code=$(curl_status "$url" "${AUTH_HEADER[@]}")
if [[ "$code" == "200" ]] && grep -q '"FeatureCollection"' /tmp/_body; then
  ok "GET /api/mapa/geojson 200"
  python3 -c "
import json
d=json.load(open('/tmp/_body'))
print('  features:',len(d.get('features',[])))
if d.get('features'): print('  ejemplo:',d['features'][0])
print('  metadata:',d.get('metadata'))
"
else
  fail_ "GET /api/mapa/geojson $code $(cat /tmp/_body | head -c 700)"
fi

info "8/7 GET /api/mapa/tiles/{z}/{x}/{y}.pbf (MVT)"
url="$BASE_URL/api/mapa/tiles/10/500/500.pbf?finca=$enc_finca&fecha=$FECHA&tipo_densidad=$TIPO$UID_PARAM"
if [[ -n "${TOKEN:-}" ]]; then url="$BASE_URL/api/mapa/tiles/10/500/500.pbf?finca=$enc_finca&fecha=$FECHA&tipo_densidad=$TIPO"; fi
code=$(curl -s -o /tmp/_tile.pbf -w "%{http_code}" "$url" "${AUTH_HEADER[@]}" -H "Accept: application/x-protobuf")
ct=$(curl -s -D - -o /dev/null "$url" "${AUTH_HEADER[@]}" | grep -i "^content-type" || true)
size=$(wc -c < /tmp/_tile.pbf 2>/dev/null || echo 0)
if [[ "$code" == "200" ]]; then
  ok "GET /api/mapa/tiles 200 (size=${size}B $ct)"
else
  fail_ "GET /api/mapa/tiles $code size=${size} $(head -c 200 /tmp/_tile.pbf | od -c | head -1)"
fi

info "9/9 GET /api/mapa/filtros sin auth → debe 401"
code=$(curl_status "$BASE_URL/api/mapa/filtros")
if [[ "$code" == "401" ]]; then ok "401 sin auth (protegido)"; else fail_ "Esperaba 401 sin auth, got $code"; fi

echo "------------------------------------------------------------"
echo -e "Resumen: ${GREEN}$pass OK${NC} / ${RED}$fail FAIL${NC}"
if [[ $fail -eq 0 ]]; then
  echo -e "${GREEN}Backend OK — todas las APIs responden.${NC}"
  echo "TIP: Swagger UI en $BASE_URL/docs con el token para pruebas visuales."
  exit 0
else
  echo -e "${RED}Hay fallos — revisa logs arriba.${NC}"
  echo "Diagnóstico rápido:"
  echo "  curl $BASE_URL/health"
  echo "  docker compose -f infraestructura/docker-compose.yml logs --tail 50"
  exit 1
fi
