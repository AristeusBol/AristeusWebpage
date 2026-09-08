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


def test_mapa_histograma_geojson_excluyen_exclusion():
    """Histograma y GeoJSON no deben contar puntos dentro de exclusiones."""
    from tests.test_histograma import _mock_hist_engine
    eng, conn = _mock_hist_engine([10.0, 20.0])
    with patch("api.routers.mapa.engine", eng):
        client.get("/api/mapa/histograma?finca=F&fecha=2024-04-01&tipo_densidad=total&bins=5", headers=auth_headers(1))
    for call in conn.execute.call_args_list:
        sql = str(call[0][0])
        if "mapa_color" in sql:
            assert "zonas_exclusion" in sql
            assert "NOT EXISTS" in sql
    mock_conn = MagicMock()
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.return_value.fetchall.return_value = []
    with patch("api.routers.mapa.engine", mock_engine):
        client.get("/api/mapa/geojson?finca=F&fecha=2024-04-01&tipo_densidad=verde", headers=auth_headers(1))
    sql = str(mock_conn.execute.call_args[0][0])
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


def test_mapa_geojson_ok():
    mock_conn = MagicMock()
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.return_value.fetchall.return_value = [
        MagicMock(id=1, geom_json={"type": "Point", "coordinates": [-60, -30]}, valor=123.5),
        MagicMock(id=2, geom_json={"type": "Point", "coordinates": [-60.1, -30.1]}, valor=200),
    ]
    with patch("api.routers.mapa.engine", mock_engine):
        resp = client.get("/api/mapa/geojson?finca=La%20Esperanza&fecha=2024-04-01&tipo_densidad=muerta", headers=auth_headers(1))
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 2
    assert data["features"][0]["properties"]["valor"] == 123.5
    assert data["metadata"]["finca"] == "La Esperanza"
    assert data["metadata"]["tipo_densidad"] == "muerta"
    sql = str(mock_conn.execute.call_args[0][0])
    assert "ST_AsGeoJSON" in sql
    assert "densidad_muerta_g_m2" in sql


def test_mapa_geojson_limit_warning():
    mock_conn = MagicMock()
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    rows = [MagicMock(id=i, geom_json={"type": "Point", "coordinates": [0,0]}, valor=10) for i in range(5)]
    mock_conn.execute.return_value.fetchall.return_value = rows
    with patch("api.routers.mapa.engine", mock_engine):
        resp = client.get("/api/mapa/geojson?finca=F&fecha=2024-04-01&tipo_densidad=verde&limit=5", headers=auth_headers(1))
    assert resp.json()["metadata"]["warning"] is not None
    assert "preferir /tiles" in resp.json()["metadata"]["warning"]


def test_mapa_geojson_tipo_invalido():
    resp = client.get("/api/mapa/geojson?finca=F&fecha=2024-04-01&tipo_densidad=azul", headers=auth_headers(1))
    assert resp.status_code == 400


def test_mapa_geojson_solo_una_columna():
    """Verifica que solo se selecciona la columna pedida, no las 3, para reducir payload"""
    for tipo, col in [("verde","densidad_verde_g_m2"),("muerta","densidad_muerta_g_m2"),("total","densidad_total_g_m2")]:
        mock_conn = MagicMock()
        mock_engine = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        mock_conn.execute.return_value.fetchall.return_value = []
        with patch("api.routers.mapa.engine", mock_engine):
            client.get(f"/api/mapa/geojson?finca=F&fecha=2024-04-01&tipo_densidad={tipo}", headers=auth_headers(1))
        sql = str(mock_conn.execute.call_args[0][0])
        assert col in sql
        otras = [c for c in ["densidad_verde_g_m2","densidad_muerta_g_m2","densidad_total_g_m2"] if c != col]
        for o in otras:
            assert o not in sql
