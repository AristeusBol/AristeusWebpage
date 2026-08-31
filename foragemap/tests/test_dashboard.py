import datetime
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from jose import jwt

from api.main import app
from core.config import ALGORITHM, SECRET_KEY

client = TestClient(app)


def _mock_dashboard_engine(area, verde, muerta, total, count):
    mock_conn = MagicMock()
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    row = MagicMock(area_total_ha=area, masa_verde=verde, masa_muerta=muerta, masa_total=total, potreros_count=count)
    mock_conn.execute.return_value.fetchone.return_value = row
    return mock_engine, mock_conn


def test_dashboard_resumen_ok():
    eng, conn = _mock_dashboard_engine(152.3, 3200.5, 1800.0, 5000.5, 4)
    with patch("api.routers.dashboard.engine", eng):
        resp = client.get("/api/dashboard/resumen?finca=La%20Esperanza&fecha=2024-04-01&usuario_id=1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["filtros"] == {"finca": "La Esperanza", "fecha": "2024-04-01", "usuario_id": 1}
    assert data["metricas"]["area"] == {"total_ha": 152.3, "unidad": "ha"}
    assert data["metricas"]["masa_seca"] == {"verde_kg": 3200.5, "muerta_kg": 1800.0, "total_kg": 5000.5, "unidad": "kg"}
    assert data["cobertura"]["potreros_incluidos"] == 4
    assert data["sin_datos"] is False
    sql = str(conn.execute.call_args[0][0])
    assert "COALESCE(SUM(area_neta_ha)" in sql
    assert "COALESCE(SUM(masa_seca_verde)" in sql
    assert "COALESCE(SUM(masa_seca_muerta)" in sql
    assert "COALESCE(SUM(masa_seca_total)" in sql
    assert "FROM calculos_stock" in sql
    assert "mapa_color" not in sql.lower()
    assert "geom" not in sql.lower()
    params = conn.execute.call_args[0][1]
    assert params["uid"] == 1
    assert params["finca"] == "La Esperanza"
    assert params["fecha"] == datetime.date(2024, 4, 1)


def test_dashboard_sin_datos():
    eng, _ = _mock_dashboard_engine(0, 0, 0, 0, 0)
    with patch("api.routers.dashboard.engine", eng):
        resp = client.get("/api/dashboard/resumen?finca=Vacia&fecha=2024-04-01&usuario_id=1")
    assert resp.json()["sin_datos"] is True
    assert resp.json()["metricas"]["area"]["total_ha"] == 0.0
    assert resp.json()["cobertura"]["potreros_incluidos"] == 0


def test_dashboard_con_jwt():
    eng, _ = _mock_dashboard_engine(10, 1, 2, 3, 1)
    token = jwt.encode({"sub": "99"}, SECRET_KEY, algorithm=ALGORITHM)
    with patch("api.routers.dashboard.engine", eng):
        resp = client.get("/api/dashboard/resumen?finca=La%20Esperanza&fecha=2024-04-01", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["filtros"]["usuario_id"] == 99


def test_dashboard_sin_auth_401():
    resp = client.get("/api/dashboard/resumen?finca=F&fecha=2024-04-01")
    assert resp.status_code == 401


def test_dashboard_tipo_coalesce_no_null():
    mock_conn = MagicMock()
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    row = MagicMock(area_total_ha=0, masa_verde=0, masa_muerta=0, masa_total=0, potreros_count=0)
    mock_conn.execute.return_value.fetchone.return_value = row
    with patch("api.routers.dashboard.engine", mock_engine):
        resp = client.get("/api/dashboard/resumen?finca=F&fecha=2024-04-01&usuario_id=1")
    assert resp.json()["metricas"]["masa_seca"]["total_kg"] == 0.0


def test_dashboard_finca_trim():
    eng, _ = _mock_dashboard_engine(1, 1, 1, 1, 1)
    with patch("api.routers.dashboard.engine", eng):
        resp = client.get("/api/dashboard/resumen?finca=%20La%20Esperanza%20&fecha=2024-04-01&usuario_id=1")
    assert resp.json()["filtros"]["finca"] == "La Esperanza"


def test_dashboard_finca_vacia_400():
    resp = client.get("/api/dashboard/resumen?finca=%20%20%20&fecha=2024-04-01&usuario_id=1")
    assert resp.status_code == 400


def test_dashboard_fecha_invalida_422():
    resp = client.get("/api/dashboard/resumen?finca=F&fecha=no-fecha&usuario_id=1")
    assert resp.status_code == 422


def test_dashboard_sqli_parametrizado():
    eng, conn = _mock_dashboard_engine(0, 0, 0, 0, 0)
    with patch("api.routers.dashboard.engine", eng):
        client.get("/api/dashboard/resumen?finca=F'; DROP TABLE calculos_stock;--&fecha=2024-04-01&usuario_id=1")
    sql = str(conn.execute.call_args[0][0])
    assert "DROP TABLE" not in sql
    assert conn.execute.call_args[0][1]["finca"] == "F'; DROP TABLE calculos_stock;--"


def test_dashboard_query_solo_una_consulta():
    eng, conn = _mock_dashboard_engine(5, 5, 5, 5, 1)
    with patch("api.routers.dashboard.engine", eng):
        client.get("/api/dashboard/resumen?finca=F&fecha=2024-04-01&usuario_id=1")
    assert conn.execute.call_count == 1
