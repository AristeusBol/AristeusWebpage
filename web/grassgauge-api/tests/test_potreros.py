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


def test_actualizar_potrero_ignora_finca():
    """La finca la gestiona el operador: PATCH con finca no la cambia."""
    from api.schemas import PotreroUpdate

    body = PotreroUpdate(nombre="Nuevo", finca="Otra")  # type: ignore[call-arg]
    assert body.nombre == "Nuevo"
    assert not hasattr(body, "finca") or getattr(body, "finca", None) is None


GEOM_OK = {"type": "Polygon", "coordinates": [[[-57.6, -34.9], [-57.59, -34.9], [-57.59, -34.89], [-57.6, -34.89], [-57.6, -34.9]]]}


def _mock_crear(valida=True, area=5.0, insert_id=9, area_insert=5.0, insert_error=None):
    conn_v = MagicMock()
    conn_v.execute.return_value.fetchone.return_value = MagicMock(valida=valida, area_ha=area)
    conn_b = MagicMock()
    if insert_error is not None:
        conn_b.execute.side_effect = insert_error
    else:
        conn_b.execute.return_value.fetchone.return_value = MagicMock(id=insert_id, area_ha=area_insert)
    eng = MagicMock()
    eng.connect.return_value.__enter__.return_value = conn_v
    eng.begin.return_value.__enter__.return_value = conn_b
    return eng, conn_v, conn_b


def test_crear_potrero_ok_valida_antes_de_insertar():
    eng, conn_v, conn_b = _mock_crear()
    with patch("api.routers.potreros.engine", eng):
        resp = client.post(
            "/api/potreros",
            json={"nombre": "Lote N", "finca": "F", "geom": GEOM_OK},
            headers=auth_headers(1),
        )
    assert resp.status_code == 201
    assert resp.json()["id"] == 9
    # La validación corre contra la candidata, sin tocar la tabla todavía.
    sql_val = str(conn_v.execute.call_args[0][0])
    assert "ST_IsValid" in sql_val
    assert "potreros_base WHERE" not in sql_val
    assert conn_b.execute.call_count == 1  # solo el INSERT, sin DELETE posterior


def test_crear_potrero_geometria_invalida_400_sin_insert():
    eng, conn_v, conn_b = _mock_crear(valida=False)
    with patch("api.routers.potreros.engine", eng):
        resp = client.post(
            "/api/potreros",
            json={"nombre": "Lote N", "finca": "F", "geom": GEOM_OK},
            headers=auth_headers(1),
        )
    assert resp.status_code == 400
    conn_b.execute.assert_not_called()


def test_crear_potrero_area_minima_400_sin_insert():
    eng, conn_v, conn_b = _mock_crear(area=0.001)
    with patch("api.routers.potreros.engine", eng):
        resp = client.post(
            "/api/potreros",
            json={"nombre": "Lote N", "finca": "F", "geom": GEOM_OK},
            headers=auth_headers(1),
        )
    assert resp.status_code == 400
    assert "0.01" in resp.json()["detail"]
    conn_b.execute.assert_not_called()


def test_crear_potrero_duplicado_409():
    from sqlalchemy.exc import IntegrityError

    eng, conn_v, conn_b = _mock_crear(insert_error=IntegrityError("INSERT", {}, Exception("dup")))
    with patch("api.routers.potreros.engine", eng):
        resp = client.post(
            "/api/potreros",
            json={"nombre": "Lote a1", "finca": "F", "geom": GEOM_OK},
            headers=auth_headers(1),
        )
    assert resp.status_code == 409
