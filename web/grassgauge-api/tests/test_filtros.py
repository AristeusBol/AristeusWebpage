import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from api.main import app
from tests.conftest import auth_headers
from core.config import ALGORITHM, SECRET_KEY

client = TestClient(app)


def _mock_engine(fincas_rows, fechas_rows):
    mock_conn = MagicMock()
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.side_effect = [
        MagicMock(fetchall=lambda: fincas_rows),
        MagicMock(fetchall=lambda: fechas_rows),
    ]
    return mock_engine, mock_conn


def test_filtros_sin_finca_dev_usuario_id():
    eng, conn = _mock_engine(
        [("El Puesto",), ("La Esperanza",)],
        [(datetime.date(2024, 4, 1),), (datetime.date(2024, 3, 15),)],
    )
    with patch("api.routers.filtros.engine", eng):
        resp = client.get("/api/mapa/filtros", headers=auth_headers(1))
    assert resp.status_code == 200
    data = resp.json()
    assert data["fincas"] == ["El Puesto", "La Esperanza"]
    assert data["fechas"] == ["2024-04-01", "2024-03-15"]
    assert data["tipos_densidad"] == ["verde", "muerta", "total"]
    assert data["filtros_aplicados"]["finca"] is None
    sql_fechas = str(conn.execute.call_args_list[1][0][0])
    assert "FROM calculos_stock" in sql_fechas
    assert "AND finca" not in sql_fechas


def test_filtros_con_finca_cascada():
    eng, conn = _mock_engine(
        [("El Puesto",), ("La Esperanza",)],
        [(datetime.date(2024, 4, 1),)],
    )
    with patch("api.routers.filtros.engine", eng):
        resp = client.get("/api/mapa/filtros?finca=El%20Puesto", headers=auth_headers(1))
    assert resp.status_code == 200
    assert resp.json()["fechas"] == ["2024-04-01"]
    assert resp.json()["filtros_aplicados"]["finca"] == "El Puesto"
    sql_fechas = str(conn.execute.call_args_list[1][0][0])
    params = conn.execute.call_args_list[1][0][1]
    assert "AND finca = :finca" in sql_fechas
    assert params["finca"] == "El Puesto"
    assert params["uid"] == 1


def test_filtros_solo_calculos_stock_no_geometrias():
    """Garantiza que no se toca mapa_color/potreros_base para fechas"""
    eng, conn = _mock_engine([], [])
    with patch("api.routers.filtros.engine", eng):
        client.get("/api/mapa/filtros", headers=auth_headers(99))
    for call in conn.execute.call_args_list:
        sql = str(call[0][0]).lower()
        assert "mapa_color" not in sql
        assert "potreros_base" not in sql
        assert "geom" not in sql


def test_filtros_con_jwt():
    eng, _ = _mock_engine([("Finca JWT",)], [(datetime.date(2024, 5, 1),)])
    token = jwt.encode({"sub": "77"}, SECRET_KEY, algorithm=ALGORITHM)
    with patch("api.routers.filtros.engine", eng):
        resp = client.get("/api/mapa/filtros", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["fincas"] == ["Finca JWT"]


def test_filtros_sin_auth_401():
    resp = client.get("/api/mapa/filtros")
    assert resp.status_code == 401
    assert "No autenticado" in resp.json()["detail"]


def test_filtros_jwt_expirado_401():
    token = jwt.encode({"sub": "1"}, SECRET_KEY, algorithm=ALGORITHM)
    with patch("api.routers.filtros.engine", MagicMock()):
        resp = client.get("/api/mapa/filtros", headers={"Authorization": "Bearer invalido"})
    assert resp.status_code == 401


def test_filtros_tipos_densidad_estatico():
    eng, _ = _mock_engine([], [])
    with patch("api.routers.filtros.engine", eng):
        resp = client.get("/api/mapa/filtros", headers=auth_headers(1))
    assert set(resp.json()["tipos_densidad"]) == {"verde", "muerta", "total"}


def test_filtros_trim_finca():
    eng, _ = _mock_engine([], [])
    with patch("api.routers.filtros.engine", eng):
        resp = client.get("/api/mapa/filtros?finca=%20%20", headers=auth_headers(1))
    assert resp.json()["filtros_aplicados"]["finca"] is None
