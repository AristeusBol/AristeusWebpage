import datetime
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from jose import jwt

from api.main import app
from tests.conftest import auth_headers
from api.routers.potreros import _t_ha
from core.config import ALGORITHM, SECRET_KEY

client = TestClient(app)


def test_t_ha_unidades():
    assert abs(_t_ha(24150, 12.34) - 1.957) < 0.001
    assert _t_ha(None, 10) is None
    assert _t_ha(100, 0) is None
    assert _t_ha(100, None) is None


def _mock_engine(rows):
    mock_conn = MagicMock()
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.return_value.fetchall.return_value = rows
    return mock_engine, mock_conn


def _row(**kw):
    base = dict(
        id=1, nombre="Lote a1", finca="Finca Don Carlos",
        geom_json={"type": "Polygon", "coordinates": []},
        area_bruta_ha=20.0, area_neta_ha=18.5,
        masa_seca_verde=20000.0, masa_seca_muerta=15000.0, masa_seca_total=35000.0,
    )
    base.update(kw)
    return MagicMock(**base)


def test_potreros_geojson_ok():
    eng, conn = _mock_engine([_row(), _row(id=2, nombre="Lote a2")])
    with patch("api.routers.potreros.engine", eng):
        resp = client.get("/api/potreros/geojson?finca=Finca%20Don%20Carlos&fecha=2026-08-31", headers=auth_headers(1))
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 2
    props = data["features"][0]["properties"]
    assert props["nombre"] == "Lote a1"
    assert props["tiene_calculo"] is True
    assert abs(props["t_ha_total"] - 1.8919) < 0.001
    assert data["metadata"]["con_calculo"] == 2
    sql = str(conn.execute.call_args[0][0])
    assert "FROM potreros_base p" in sql
    assert "LEFT JOIN calculos_stock c" in sql
    assert "ST_AsGeoJSON" in sql


def test_potreros_sin_calculo():
    eng, _ = _mock_engine([_row(area_neta_ha=None, masa_seca_verde=None, masa_seca_muerta=None, masa_seca_total=None)])
    with patch("api.routers.potreros.engine", eng):
        resp = client.get("/api/potreros/geojson?finca=F&fecha=2026-08-31", headers=auth_headers(1))
    props = resp.json()["features"][0]["properties"]
    assert props["tiene_calculo"] is False
    assert props["t_ha_total"] is None
    assert resp.json()["metadata"]["con_calculo"] == 0


def test_potreros_con_jwt():
    eng, _ = _mock_engine([])
    token = jwt.encode({"sub": "7"}, SECRET_KEY, algorithm=ALGORITHM)
    with patch("api.routers.potreros.engine", eng):
        resp = client.get(
            "/api/potreros/geojson?finca=F&fecha=2026-08-31",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    params = eng.connect.return_value.__enter__.return_value.execute.call_args[0][1]
    assert params["uid"] == 7


def test_potreros_sin_auth_401():
    resp = client.get("/api/potreros/geojson?finca=F&fecha=2026-08-31")
    assert resp.status_code == 401


def test_potreros_lista_sin_auth_401():
    resp = client.get("/api/potreros")
    assert resp.status_code == 401


def test_potreros_lista_ok():
    eng, conn = _mock_engine(rows=[
        MagicMock(id=1, nombre="Lote a1", finca="Finca Don Carlos"),
        MagicMock(id=2, nombre="Lote a2", finca="Finca Don Carlos"),
    ])
    with patch("api.routers.potreros.engine", eng):
        resp = client.get("/api/potreros", headers=auth_headers(1))
    assert resp.status_code == 200
    data = resp.json()
    assert data["potreros"][0]["nombre"] == "Lote a1"
    assert len(data["potreros"]) == 2


def test_potrero_detalle_404():
    eng = MagicMock()
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = None
    eng.connect.return_value.__enter__.return_value = mock_conn
    with patch("api.routers.potreros.engine", eng):
        with patch("api.routers.potreros.repo_potreros.potrero_y_exclusiones_geojson", return_value=None):
            resp = client.get("/api/potreros/999", headers=auth_headers(1))
    assert resp.status_code == 404


def test_potrero_detalle_ok():
    fc = {"type": "FeatureCollection", "features": []}
    eng = MagicMock()
    eng.connect.return_value.__enter__.return_value = MagicMock()
    with patch("api.routers.potreros.engine", eng):
        with patch("api.routers.potreros.repo_potreros.potrero_y_exclusiones_geojson", return_value=fc):
            resp = client.get("/api/potreros/1", headers=auth_headers(1))
    assert resp.status_code == 200
    assert resp.json() == fc


def test_potreros_finca_vacia_400():
    resp = client.get("/api/potreros/geojson?finca=%20%20&fecha=2026-08-31", headers=auth_headers(1))
    assert resp.status_code == 400


def test_potreros_fecha_invalida_422():
    resp = client.get("/api/potreros/geojson?finca=F&fecha=no-fecha", headers=auth_headers(1))
    assert resp.status_code == 422


def test_potreros_sqli_parametrizado():
    eng, conn = _mock_engine([])
    with patch("api.routers.potreros.engine", eng):
        client.get("/api/potreros/geojson?finca=F'; DROP TABLE potreros_base;--&fecha=2026-08-31", headers=auth_headers(1))
    sql = str(conn.execute.call_args[0][0])
    assert "DROP TABLE" not in sql
    assert conn.execute.call_args[0][1]["finca"] == "F'; DROP TABLE potreros_base;--"
