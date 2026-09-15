from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from api.main import app
from api.routers.rodeos import _consumo_diario
from tests.conftest import auth_headers

client = TestClient(app)


def test_consumo_diario_unidades():
    # 80 vacas × 450kg × 2.8% = 1008.0 kg MS/día
    assert _consumo_diario(80, 450.0, 2.8) == 1008.0
    assert _consumo_diario(None, 450.0, 2.8) is None
    assert _consumo_diario(10, 0, 2.5) == 0.0


def _mock_engine(fetchone=None, fetchall=None):
    mock_conn = MagicMock()
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    mock_engine.begin.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.return_value.fetchone.return_value = fetchone
    mock_conn.execute.return_value.fetchall.return_value = fetchall or []
    return mock_engine


def _row(**kw):
    base = dict(
        id=1, nombre="Lote 1", categoria="vaca_lactancia",
        cabezas=80, peso_prom_kg=450.0, consumo_pct=2.8, notas=None,
        color=None,
    )
    base.update(kw)
    return MagicMock(**base)


def test_listar_rodeos_ok():
    eng = _mock_engine(fetchall=[_row(), _row(id=2, nombre="Lote 2", categoria="novillo",
                                              cabezas=60, peso_prom_kg=380.0, consumo_pct=2.6)])
    with patch("api.routers.rodeos.engine", eng):
        resp = client.get("/api/rodeos", headers=auth_headers(1))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["rodeos"]) == 2
    assert data["rodeos"][0]["consumo_diario_ms_kg"] == 1008.0
    assert data["rodeos"][0]["categoria_label"] == "Vaca con cría"
    assert data["total_cabezas"] == 140
    assert data["total_consumo_diario_ms_kg"] == 1008.0 + 592.8


def test_crear_rodeo_usa_sugerido_categoria_201():
    eng = _mock_engine(fetchone=_row())
    with patch("api.routers.rodeos.engine", eng):
        resp = client.post("/api/rodeos",
                           json={"nombre": "Lote 1", "categoria": "vaca_lactancia",
                                 "cabezas": 80, "peso_prom_kg": 450},
                           headers=auth_headers(1))
    assert resp.status_code == 201
    assert resp.json()["consumo_diario_ms_kg"] == 1008.0
    params = eng.begin.return_value.__enter__.return_value.execute.call_args[0][1]
    assert params["cons"] == 2.8  # sugerido de la categoría
    assert params["uid"] == 1


def test_crear_rodeo_categoria_invalida_422():
    resp = client.post("/api/rodeos",
                       json={"nombre": "X", "categoria": "dinosaurio",
                             "cabezas": 10, "peso_prom_kg": 300},
                       headers=auth_headers(1))
    assert resp.status_code == 422


def test_crear_rodeo_cabezas_cero_422():
    resp = client.post("/api/rodeos",
                       json={"nombre": "X", "categoria": "novillo",
                             "cabezas": 0, "peso_prom_kg": 300},
                       headers=auth_headers(1))
    assert resp.status_code == 422


def test_crear_rodeo_duplicado_409():
    eng = MagicMock()
    mock_begin = MagicMock()
    mock_begin.execute.side_effect = IntegrityError("INSERT", {}, Exception("dup"))
    eng.begin.return_value.__enter__.return_value = mock_begin
    with patch("api.routers.rodeos.engine", eng):
        resp = client.post("/api/rodeos",
                           json={"nombre": "Lote 1", "categoria": "novillo",
                                 "cabezas": 10, "peso_prom_kg": 300},
                           headers=auth_headers(1))
    assert resp.status_code == 409


def test_listar_rodeos_totales_suman_todos():
    eng = _mock_engine(fetchall=[
        _row(),
        _row(id=2, nombre="Lote 2",
             cabezas=200, peso_prom_kg=380.0, consumo_pct=2.6),
    ])
    with patch("api.routers.rodeos.engine", eng):
        resp = client.get("/api/rodeos", headers=auth_headers(1))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["rodeos"]) == 2
    # Los totales suman todos los rodeos
    assert data["total_cabezas"] == 280
    assert data["total_consumo_diario_ms_kg"] == 1008.0 + 1976.0


def test_crear_rodeo_con_color_fecha_201():
    eng = _mock_engine(fetchone=_row(color="#a1c2d3"))
    with patch("api.routers.rodeos.engine", eng):
        resp = client.post(
            "/api/rodeos",
            json={"nombre": "Lote 1", "categoria": "vaca_lactancia",
                  "cabezas": 80, "peso_prom_kg": 450,
                  "color": "#A1C2D3"},
            headers=auth_headers(1))
    assert resp.status_code == 201
    params = eng.begin.return_value.__enter__.return_value.execute.call_args[0][1]
    assert params["color"] == "#a1c2d3"


def test_crear_rodeo_color_invalido_422():
    for color in ("red", "#FFFG22", "ffffff", "#1A2", "#GGGGGG"):
        resp = client.post(
            "/api/rodeos",
            json={"nombre": "X", "categoria": "novillo",
                  "cabezas": 10, "peso_prom_kg": 300, "color": color},
            headers=auth_headers(1))
        assert resp.status_code == 422, color


def test_actualizar_color_ok():
    eng = _mock_engine(fetchone=_row(color="#ff8800"))
    with patch("api.routers.rodeos.engine", eng):
        resp = client.patch(
            "/api/rodeos/1",
            json={"color": "#FF8800"},
            headers=auth_headers(1))
    assert resp.status_code == 200
    assert resp.json()["color"] == "#ff8800"


def test_eliminar_rodeo_inexistente_404():
    eng = _mock_engine(fetchone=None)
    with patch("api.routers.rodeos.engine", eng):
        resp = client.delete("/api/rodeos/99", headers=auth_headers(1))
    assert resp.status_code == 404


def test_rodeos_sin_auth_401():
    assert client.get("/api/rodeos").status_code == 401
    assert client.post("/api/rodeos", json={}).status_code == 401
