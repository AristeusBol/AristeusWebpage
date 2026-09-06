from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api.main import app
from tests.conftest import auth_headers

client = TestClient(app)


AREA_M2 = 280630.0


def _mock_hist_engine(valores):
    mock_conn = MagicMock()
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    if valores:
        vmin, vmax = min(valores), max(valores)
        mean = sum(valores) / len(valores)
        stats = MagicMock(n=len(valores), vmin=vmin, vmax=vmax, vmean=mean)
        n = len(valores)
        buckets = [MagicMock(bucket=i + 1, c=1) for i in range(min(n, 5))]
    else:
        stats = MagicMock(n=0, vmin=None, vmax=None, vmean=None)
        buckets = []
    mock_area = MagicMock()
    mock_area.fetchone.return_value = (AREA_M2,)
    mock_stats = MagicMock()
    mock_stats.fetchone.return_value = stats
    mock_buckets = MagicMock()
    mock_buckets.fetchall.return_value = buckets
    mock_conn.execute.side_effect = [mock_area, mock_stats, mock_buckets]
    return mock_engine, mock_conn


def test_histograma_ok():
    eng, conn = _mock_hist_engine([10.0, 20.0, 30.0, 40.0])
    with patch("api.routers.mapa.engine", eng):
        resp = client.get("/api/mapa/histograma?finca=F&fecha=2024-04-01&tipo_densidad=total&bins=5", headers=auth_headers(1))
    assert resp.status_code == 200
    data = resp.json()
    factor = (AREA_M2 / 4) / 1000.0
    assert data["stats"]["count"] == 4
    assert data["stats"]["unidad"] == "kg"
    assert abs(data["stats"]["min"] - 10.0 * factor) < 0.001
    assert abs(data["stats"]["max"] - 40.0 * factor) < 0.001
    assert abs(data["stats"]["mean"] - 25.0 * factor) < 0.001
    assert len(data["intervalos"]) == 5
    assert sum(b["count"] for b in data["intervalos"]) == 4
    assert abs(sum(b["pct"] for b in data["intervalos"]) - 100.0) < 0.05
    assert data["sin_datos"] is False
    assert data["filtros"]["tipo_densidad"] == "total"
    sql = str(conn.execute.call_args[0][0])
    assert "densidad_total_g_m2" in sql


def test_histograma_tipos_whitelist():
    for tipo, col in [("verde", "densidad_verde_g_m2"), ("muerta", "densidad_muerta_g_m2")]:
        eng, conn = _mock_hist_engine([1.0, 2.0])
        with patch("api.routers.mapa.engine", eng):
            resp = client.get(f"/api/mapa/histograma?finca=F&fecha=2024-04-01&tipo_densidad={tipo}", headers=auth_headers(1))
        assert resp.status_code == 200
        assert col in str(conn.execute.call_args[0][0])


def test_histograma_tipo_invalido_400():
    resp = client.get("/api/mapa/histograma?finca=F&fecha=2024-04-01&tipo_densidad=azul", headers=auth_headers(1))
    assert resp.status_code == 400


def test_histograma_sin_auth_401():
    resp = client.get("/api/mapa/histograma?finca=F&fecha=2024-04-01")
    assert resp.status_code == 401


def test_histograma_valor_unico_un_bin():
    eng, _ = _mock_hist_engine([50.0, 50.0])
    with patch("api.routers.mapa.engine", eng):
        resp = client.get("/api/mapa/histograma?finca=F&fecha=2024-04-01&tipo_densidad=total&bins=5", headers=auth_headers(1))
    data = resp.json()
    assert data["sin_datos"] is False
    assert len(data["intervalos"]) == 1
    assert data["intervalos"][0]["count"] == 2
    assert data["intervalos"][0]["pct"] == 100.0
    assert data["stats"]["unidad"] == "kg"


def test_histograma_sin_datos():
    eng, _ = _mock_hist_engine([])
    with patch("api.routers.mapa.engine", eng):
        resp = client.get("/api/mapa/histograma?finca=Vacia&fecha=2024-04-01", headers=auth_headers(1))
    assert resp.status_code == 200
    data = resp.json()
    assert data["sin_datos"] is True
    assert data["intervalos"] == []
    assert data["stats"]["count"] == 0
