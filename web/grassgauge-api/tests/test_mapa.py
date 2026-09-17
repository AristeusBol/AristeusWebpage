import datetime
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from jose import jwt

from api.main import app
from tests.conftest import auth_headers
from core.config import ALGORITHM, SECRET_KEY

client = TestClient(app)


def _mock_mvt_engine(mvt_bytes):
    mock_conn = MagicMock()
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.return_value.fetchone.return_value = (mvt_bytes,)
    return mock_engine, mock_conn


def test_mapa_tile_ok():
    eng, conn = _mock_mvt_engine(b"\x1a\x05densidad")
    with patch("api.routers.mapa.engine", eng):
        resp = client.get("/api/mapa/tiles/10/500/500.pbf?finca=La%20Esperanza&fecha=2024-04-01&tipo_densidad=verde", headers=auth_headers(1))
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/x-protobuf"
    assert resp.content == b"\x1a\x05densidad"
    assert resp.headers["Cache-Control"] == "private, max-age=300"
    sql = str(conn.execute.call_args[0][0])
    assert "ST_AsMVT" in sql
    assert "ST_AsMVTGeom" in sql
    assert "ST_TileEnvelope" in sql
    assert "densidad_verde_g_m2" in sql
    params = conn.execute.call_args[0][1]
    assert params["z"] == 10 and params["x"] == 500 and params["y"] == 500
    assert params["finca"] == "La Esperanza"
    assert params["fecha"] == datetime.date(2024, 4, 1)


def test_mapa_tile_recorta_exclusiones():
    """El tile debe excluir puntos en exclusión y recortar geometría (hueco)."""
    eng, conn = _mock_mvt_engine(b"tile")
    with patch("api.routers.mapa.engine", eng):
        resp = client.get("/api/mapa/tiles/10/500/500.pbf?finca=F&fecha=2024-04-01&tipo_densidad=total", headers=auth_headers(1))
    assert resp.status_code == 200
    sql = str(conn.execute.call_args[0][0])
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
        eng, conn = _mock_mvt_engine(b"tile")
        with patch("api.routers.mapa.engine", eng):
            resp = client.get(f"/api/mapa/tiles/5/1/1.pbf?finca=F&fecha=2024-04-01&tipo_densidad={tipo}", headers=auth_headers(1))
        assert resp.status_code == 200
        assert columna in str(conn.execute.call_args[0][0])


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
    sql = str(conn.execute.call_args[0][0])
    assert "DROP TABLE" not in sql
    assert conn.execute.call_args[0][1]["finca"] == "F'; DROP TABLE--"

