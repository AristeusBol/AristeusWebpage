from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api.main import app
from api.routers.potreros import _prorrateo
from tests.conftest import auth_headers

client = TestClient(app)

POLI = {
    "type": "Polygon",
    "coordinates": [[[-61.0, -16.0], [-61.0, -15.9], [-60.9, -15.9], [-60.9, -16.0], [-61.0, -16.0]]],
}


def _mock_conn_fetchone(return_value):
    mock_conn = MagicMock()
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    mock_engine.begin.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.return_value.fetchone.return_value = return_value
    mock_conn.execute.return_value.fetchall.return_value = []
    return mock_engine, mock_conn


def test_prorrateo_unidades():
    calc = MagicMock(area_neta_ha=10.0, masa_seca_verde=20000.0,
                     masa_seca_muerta=10000.0, masa_seca_total=30000.0)
    pr = _prorrateo(5.0, calc)
    assert pr["tiene_calculo"] is True
    assert pr["estimado_por_prorrateo"] is True
    assert abs(pr["t_ha_total"] - 3.0) < 0.001  # 30000kg/1000/10ha
    assert abs(pr["masa_total_kg"] - 15000.0) < 0.01  # mitad del área
    assert abs(pr["masa_verde_kg"] - 10000.0) < 0.01


def test_prorrateo_sin_calculo():
    pr = _prorrateo(5.0, None)
    assert pr["tiene_calculo"] is False
    assert pr["masa_total_kg"] is None


def test_crear_potrero_geom_invalida_422():
    mala = {"type": "Polygon", "coordinates": [[[0, 0], [1, 1]]]}
    resp = client.post("/api/potreros", json={"nombre": "P1", "finca": "F", "geom": mala},
                       headers=auth_headers(1))
    assert resp.status_code == 422


def test_crear_parcela_estado_invalido_422():
    resp = client.post("/api/potreros/1/parcelas",
                       json={"nombre": "A", "estado": "orbital", "geom": POLI},
                       headers=auth_headers(1))
    assert resp.status_code == 422


def test_crear_parcela_fuera_del_potrero_400():
    pot = MagicMock(id=1, nombre="P1", finca="F")
    chk = MagicMock(dentro=False, valida=True, area_ha=5.0)
    with patch("api.routers.parcelas.repo.potrero_del_usuario", return_value=pot), \
         patch("api.routers.parcelas.repo.validar_contenida", return_value=chk):
        resp = client.post("/api/potreros/1/parcelas",
                           json={"nombre": "A", "geom": POLI}, headers=auth_headers(1))
    assert resp.status_code == 400
    assert "dentro del potrero" in resp.json()["detail"]


def test_crear_parcela_solapada_409():
    pot = MagicMock(id=1, nombre="P1", finca="F")
    chk = MagicMock(dentro=True, valida=True, area_ha=5.0)
    with patch("api.routers.parcelas.repo.potrero_del_usuario", return_value=pot), \
         patch("api.routers.parcelas.repo.validar_contenida", return_value=chk), \
         patch("api.routers.parcelas.repo.hay_solape", return_value=True):
        resp = client.post("/api/potreros/1/parcelas",
                           json={"nombre": "A", "geom": POLI}, headers=auth_headers(1))
    assert resp.status_code == 409


def test_crear_parcela_pisa_exclusion_400():
    pot = MagicMock(id=1, nombre="P1", finca="F")
    chk = MagicMock(dentro=True, valida=True, area_ha=5.0)
    with patch("api.routers.parcelas.repo.potrero_del_usuario", return_value=pot), \
         patch("api.routers.parcelas.repo.validar_contenida", return_value=chk), \
         patch("api.routers.parcelas.repo.area_choque_exclusiones", return_value=50.0):
        resp = client.post("/api/potreros/1/parcelas",
                           json={"nombre": "A", "geom": POLI}, headers=auth_headers(1))
    assert resp.status_code == 400
    assert "exclusi" in resp.json()["detail"]


def test_exclusiones_finca_requiere_auth():
    resp = client.get("/api/exclusiones/geojson?finca=F")
    assert resp.status_code == 401


def test_fincas_con_potreros_requiere_auth():
    resp = client.get("/api/potreros/fincas")
    assert resp.status_code == 401


def test_detalle_gestion_404_sin_auth():
    resp = client.get("/api/potreros/999/detalle")
    assert resp.status_code == 401


def test_sugerir_nombre_requiere_auth():
    resp = client.get("/api/parcelas/sugerir-nombre?potrero_id=1")
    assert resp.status_code == 401
