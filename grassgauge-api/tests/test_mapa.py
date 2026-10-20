import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from api.main import app
from api.routers import mapa as mapa_router
from tests.conftest import auth_headers
from core.config import ALGORITHM, SECRET_KEY

client = TestClient(app)


@pytest.fixture(autouse=True)
def _limpiar_caches_mapa():
    """El endpoint cachea en proceso (LRU de tiles y disponibilidad de
    celdas): sin limpiarlo, la respuesta de un test se filtra al siguiente."""
    mapa_router._lru.clear()
    mapa_router._disp.clear()
    mapa_router._calentado_hasta.clear()
    yield
    mapa_router._lru.clear()
    mapa_router._disp.clear()
    mapa_router._calentado_hasta.clear()


def _mock_mvt_engine(mvt_bytes):
    """Engine mockeado para el endpoint de tiles.

    `_renderizar_tile` consulta primero la caché compartida (leer_tile_cache)
    y recién después ejecuta el query del tile. El mock tiene que reportar
    miss de caché (None) para esa consulta y devolver los bytes del tile en
    el resto, si no el endpoint corta antes de llegar al SQL a verificar.
    """
    mock_conn = MagicMock()

    def _execute(stmt, *args, **kwargs):
        sql = str(stmt)
        res = MagicMock()
        if "mapa_tiles_cache" in sql and sql.upper().lstrip().startswith("SELECT"):
            res.fetchone.return_value = None  # miss de caché (fila ausente)
        else:
            res.fetchone.return_value = (mvt_bytes,)
        return res

    mock_conn.execute.side_effect = _execute
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    mock_engine.begin.return_value.__enter__.return_value = mock_conn
    return mock_engine, mock_conn


def _mock_mvt_engine_celdas(mvt_bytes, hay_celdas: bool):
    """Igual que _mock_mvt_engine pero decide la ruta rápida vs legacy.

    El endpoint pregunta primero si el grupo tiene celdas precalculadas
    (repositorios.celdas.celdas_disponibles); parcheando esa respuesta y
    mirando el SQL ejecutado se distingue qué camino tomó cada test.
    """
    eng, conn = _mock_mvt_engine(mvt_bytes)
    return eng, conn, patch("api.routers.mapa.repo_celdas.celdas_disponibles", return_value=hay_celdas)


def _sql_mvt(conn) -> str:
    """SQL de la llamada que construye el tile.

    No sirve conn.execute.call_args: el hilo de precalentado comparte el
    engine mockeado y su SELECT de ST_Extent puede ser la última llamada.
    """
    for call in conn.execute.call_args_list:
        sql = str(call[0][0])
        if "ST_AsMVT" in sql:
            return sql
    raise AssertionError("no se ejecutó ningún query de tile (ST_AsMVT)")


def _params_mvt(conn) -> dict:
    for call in conn.execute.call_args_list:
        if "ST_AsMVT" in str(call[0][0]):
            return call[0][1]
    raise AssertionError("no se ejecutó ningún query de tile (ST_AsMVT)")


def test_mapa_tile_ok():
    eng, conn, parche = _mock_mvt_engine_celdas(b"\x1a\x05densidad", hay_celdas=True)
    with patch("api.routers.mapa.engine", eng), parche:
        resp = client.get("/api/mapa/tiles/10/500/500.pbf?finca=La%20Esperanza&fecha=2024-04-01&tipo_densidad=verde", headers=auth_headers(1))
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/x-protobuf"
    assert resp.content == b"\x1a\x05densidad"
    assert resp.headers["Cache-Control"] == "public, max-age=3600"
    sql = _sql_mvt(conn)
    assert "ST_AsMVT" in sql
    assert "ST_AsMVTGeom" in sql
    assert "ST_TileEnvelope" in sql
    # Ruta rápida: lee las celdas precalculadas, no reconstruye geometría.
    assert "mapa_celdas" in sql
    assert "densidad_verde_g_m2" in sql
    params = _params_mvt(conn)
    assert params["z"] == 10 and params["x"] == 500 and params["y"] == 500
    assert params["finca"] == "La Esperanza"
    assert params["fecha"] == datetime.date(2024, 4, 1)


def test_mapa_tile_sin_celdas_usa_legacy():
    """Sin celdas precalculadas (grupo viejo) cae al query que las arma."""
    eng, conn, parche = _mock_mvt_engine_celdas(b"tile", hay_celdas=False)
    with patch("api.routers.mapa.engine", eng), parche:
        resp = client.get("/api/mapa/tiles/10/500/500.pbf?finca=Vieja&fecha=2024-04-01&tipo_densidad=total", headers=auth_headers(1))
    assert resp.status_code == 200
    sql = _sql_mvt(conn)
    assert "mapa_color" in sql
    assert "mapa_celdas" not in sql
    assert "potreros_base" in sql


def test_mapa_tile_recorta_exclusiones():
    """El query legacy (fallback) debe excluir puntos en exclusión y recortar."""
    eng, conn, parche = _mock_mvt_engine_celdas(b"tile", hay_celdas=False)
    with patch("api.routers.mapa.engine", eng), parche:
        resp = client.get("/api/mapa/tiles/10/500/500.pbf?finca=F&fecha=2024-04-01&tipo_densidad=total", headers=auth_headers(1))
    assert resp.status_code == 200
    sql = _sql_mvt(conn)
    assert "zonas_exclusion" in sql
    assert "NOT EXISTS" in sql
    assert "ST_Difference" in sql
    assert "ST_Covers" in sql


def test_mapa_histograma_excluye_exclusion():
    """Histograma no debe contar puntos dentro de exclusiones."""
    from tests.test_histograma import _mock_hist_engine
    eng, conn = _mock_hist_engine([10.0, 20.0], dueno=None)
    with patch("api.routers.mapa.engine", eng):
        client.get("/api/mapa/histograma?finca=F&fecha=2024-04-01&bins=5", headers=auth_headers(1))
    for call in conn.execute.call_args_list:
        sql = str(call[0][0])
        if "mapa_color" in sql:
            assert "zonas_exclusion" in sql
            assert "NOT EXISTS" in sql


def test_mapa_tile_tipos_densidad_whitelist():
    for tipo, columna in [("verde", "densidad_verde_g_m2"), ("muerta", "densidad_muerta_g_m2"), ("total", "densidad_total_g_m2")]:
        eng, conn, parche = _mock_mvt_engine_celdas(b"tile", hay_celdas=True)
        with patch("api.routers.mapa.engine", eng), parche:
            resp = client.get(f"/api/mapa/tiles/5/1/1.pbf?finca=F&fecha=2024-04-01&tipo_densidad={tipo}", headers=auth_headers(1))
        assert resp.status_code == 200
        assert columna in _sql_mvt(conn)


def test_mapa_tile_tipo_invalido_400():
    resp = client.get("/api/mapa/tiles/5/1/1.pbf?finca=F&fecha=2024-04-01&tipo_densidad=invalido", headers=auth_headers(1))
    assert resp.status_code == 400
    assert "tipo_densidad" in resp.json()["detail"]


def test_mapa_tile_vacio_200_empty():
    eng, _ = _mock_mvt_engine(None)
    with patch("api.routers.mapa.engine", eng):
        resp = client.get("/api/mapa/tiles/10/1/1.pbf?finca=Vacia&fecha=2024-04-01&tipo_densidad=total", headers=auth_headers(1))
    assert resp.status_code == 200
    assert resp.content == b""
    assert resp.headers["content-type"] == "application/x-protobuf"


def test_mapa_tile_memoryview():
    eng, _ = _mock_mvt_engine(memoryview(b"tile-mem"))
    with patch("api.routers.mapa.engine", eng):
        resp = client.get("/api/mapa/tiles/8/10/10.pbf?finca=F&fecha=2024-04-01&tipo_densidad=verde", headers=auth_headers(1))
    assert resp.content == b"tile-mem"


def test_mapa_tile_con_jwt():
    eng, _ = _mock_mvt_engine(b"tile")
    token = jwt.encode({"sub": "99"}, SECRET_KEY, algorithm=ALGORITHM)
    with patch("api.routers.mapa.engine", eng):
        resp = client.get("/api/mapa/tiles/8/10/10.pbf?finca=F&fecha=2024-04-01&tipo_densidad=verde", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


def test_mapa_tile_sin_auth_401():
    resp = client.get("/api/mapa/tiles/8/10/10.pbf?finca=F&fecha=2024-04-01&tipo_densidad=verde")
    assert resp.status_code == 401


def test_mapa_tile_sqli_protegido():
    eng, conn = _mock_mvt_engine(b"tile")
    with patch("api.routers.mapa.engine", eng):
        client.get("/api/mapa/tiles/8/10/10.pbf?finca=F'; DROP TABLE--&fecha=2024-04-01&tipo_densidad=verde", headers=auth_headers(1))
    sql = _sql_mvt(conn)
    assert "DROP TABLE" not in sql
    assert _params_mvt(conn)["finca"] == "F'; DROP TABLE--"


# --- Precalentado proactivo -------------------------------------------------

def test_precalentar_programa_y_no_bloquea():
    """El endpoint responde ya y deja el render para el thread de fondo."""
    with patch("api.routers.mapa._precalentar_async") as pre:
        resp = client.post(
            "/api/mapa/precalentar?finca=Aristeus&fecha=2026-09-14&tipo_densidad=total&z=14"
            "&min_lon=-61.10&min_lat=-16.02&max_lon=-60.98&max_lat=-15.94",
            headers=auth_headers(1),
        )
    assert resp.status_code == 200
    assert resp.json()["estado"] == "programado"
    pre.assert_called_once()
    # el bbox viaja tal cual al warm-up (acota la grilla al viewport)
    assert pre.call_args.kwargs["bbox"] == (-61.10, -16.02, -60.98, -15.94)


def test_precalentar_bbox_invalido_400():
    resp = client.post(
        "/api/mapa/precalentar?finca=F&fecha=2024-04-01&z=14"
        "&min_lon=-60.98&min_lat=-16.02&max_lon=-61.10&max_lat=-15.94",
        headers=auth_headers(1),
    )
    assert resp.status_code == 400
    assert "bbox" in resp.json()["detail"]


def test_precalentar_tipo_invalido_400():
    resp = client.post(
        "/api/mapa/precalentar?finca=F&fecha=2024-04-01&tipo_densidad=xx&z=14",
        headers=auth_headers(1),
    )
    assert resp.status_code == 400


def test_precalentar_requiere_auth_401():
    resp = client.post("/api/mapa/precalentar?finca=F&fecha=2024-04-01&z=14")
    assert resp.status_code == 401

