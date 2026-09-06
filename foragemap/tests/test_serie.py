import datetime
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from jose import jwt

from api.main import app
from tests.conftest import auth_headers
from core.config import ALGORITHM, SECRET_KEY

client = TestClient(app)


def _mock_engine(rows):
    mock_conn = MagicMock()
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.return_value.fetchall.return_value = rows
    return mock_engine, mock_conn


def _row(fecha, area, verde, muerta, total, n):
    return MagicMock(fecha=fecha, area=area, verde=verde, muerta=muerta, total=total, n=n)


def test_serie_ok_orden_y_tha():
    rows = [
        _row(datetime.date(2026, 4, 15), 180.0, 200000.0, 150000.0, 350000.0, 9),
        _row(datetime.date(2026, 8, 31), 185.2, 225793.0, 169972.0, 395765.0, 9),
    ]
    eng, conn = _mock_engine(rows)
    with patch("api.routers.dashboard.engine", eng):
        resp = client.get("/api/dashboard/serie?finca=Finca%20Don%20Carlos", headers=auth_headers(1))
    assert resp.status_code == 200
    data = resp.json()
    assert data["filtros"] == {"finca": "Finca Don Carlos", "potrero_id": None, "usuario_id": 1}
    assert len(data["puntos"]) == 2
    assert data["puntos"][0]["fecha"] == "2026-04-15"
    assert abs(data["puntos"][0]["t_ha"] - 1.9444) < 0.001
    assert data["puntos"][1]["potreros"] == 9
    sql = str(conn.execute.call_args[0][0])
    assert "GROUP BY fecha" in sql
    assert "ORDER BY fecha ASC" in sql
    assert "FROM calculos_stock" in sql
    assert "potrero_id" not in sql


def test_serie_por_potrero():
    eng, conn = _mock_engine([_row(datetime.date(2026, 8, 31), 25.0, 30000.0, 20000.0, 50000.0, 1)])
    with patch("api.routers.dashboard.engine", eng):
        resp = client.get("/api/dashboard/serie?finca=F&potrero_id=5", headers=auth_headers(1))
    assert resp.status_code == 200
    assert resp.json()["filtros"]["potrero_id"] == 5
    assert resp.json()["puntos"][0]["t_ha"] == 2.0
    sql = str(conn.execute.call_args[0][0])
    assert "AND potrero_id = :pid" in sql
    assert conn.execute.call_args[0][1]["pid"] == 5


def test_serie_potrero_ajeno_404():
    mock_conn = MagicMock()
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.return_value.fetchone.return_value = None
    with patch("api.routers.dashboard.engine", mock_engine):
        resp = client.get("/api/dashboard/serie?finca=F&potrero_id=999", headers=auth_headers(1))
    assert resp.status_code == 404


def test_serie_vacia():
    eng, _ = _mock_engine([])
    with patch("api.routers.dashboard.engine", eng):
        resp = client.get("/api/dashboard/serie?finca=Vacia", headers=auth_headers(1))
    assert resp.status_code == 200
    assert resp.json()["puntos"] == []


def test_serie_area_cero_tha_none():
    eng, _ = _mock_engine([_row(datetime.date(2026, 8, 31), 0, 0, 0, 0, 0)])
    with patch("api.routers.dashboard.engine", eng):
        resp = client.get("/api/dashboard/serie?finca=F", headers=auth_headers(1))
    assert resp.json()["puntos"][0]["t_ha"] is None


def test_serie_con_jwt():
    eng, _ = _mock_engine([])
    token = jwt.encode({"sub": "42"}, SECRET_KEY, algorithm=ALGORITHM)
    with patch("api.routers.dashboard.engine", eng):
        resp = client.get(
            "/api/dashboard/serie?finca=F",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    assert resp.json()["filtros"]["usuario_id"] == 42


def test_serie_sin_auth_401():
    resp = client.get("/api/dashboard/serie?finca=F")
    assert resp.status_code == 401


def test_serie_finca_vacia_400():
    resp = client.get("/api/dashboard/serie?finca=%20%20", headers=auth_headers(1))
    assert resp.status_code == 400


def test_serie_una_sola_query():
    eng, conn = _mock_engine([])
    with patch("api.routers.dashboard.engine", eng):
        client.get("/api/dashboard/serie?finca=F", headers=auth_headers(1))
    assert conn.execute.call_count == 1
