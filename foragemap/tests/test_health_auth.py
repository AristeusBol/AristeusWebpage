from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_health_root():
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_health_db_up():
    mock_conn = MagicMock()
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    with patch("core.db.engine", mock_engine):
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_openapi_expone_endpoints():
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json()["paths"]
    assert "/api/mapa/filtros" in paths
    assert "/api/mapa/tiles/{z}/{x}/{y}.pbf" in paths
    assert "/api/mapa/geojson" in paths
    assert "/api/dashboard/resumen" in paths
    assert "/api/auth/registro" in paths
    assert "/api/auth/login" in paths
