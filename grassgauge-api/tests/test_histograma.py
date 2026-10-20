from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api.main import app
from tests.conftest import auth_headers

client = TestClient(app)


AREA_M2 = 280630.0


def _mock_hist_engine(valores, dueno=True):
    """Motor mockeado: [ownership], area, stats fecha, stats global, buckets x3."""
    mock_conn = MagicMock()
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    mock_area = MagicMock()
    mock_area.fetchone.return_value = (AREA_M2,)
    stats = MagicMock()
    if valores:
        vmin, vmax = min(valores), max(valores)
        mean = sum(valores) / len(valores)
        n = len(valores)
        stats.configure_mock(**{
            "n": n,
            "n_verde": n, "vmin_verde": vmin, "vmax_verde": vmax, "vmean_verde": mean,
            "n_muerta": n, "vmin_muerta": vmin, "vmax_muerta": vmax, "vmean_muerta": mean,
            "n_total": n, "vmin_total": vmin, "vmax_total": vmax, "vmean_total": mean,
        })
        buckets = [MagicMock(bucket=i + 1, c=1) for i in range(min(n, 5))]
    else:
        stats.configure_mock(**{
            "n": 0,
            "n_verde": 0, "vmin_verde": None, "vmax_verde": None, "vmean_verde": None,
            "n_muerta": 0, "vmin_muerta": None, "vmax_muerta": None, "vmean_muerta": None,
            "n_total": 0, "vmin_total": None, "vmax_total": None, "vmean_total": None,
        })
        buckets = []
    mock_stats = MagicMock()
    mock_stats.fetchone.return_value = stats
    mock_global = MagicMock()
    if valores:
        gvmin, gvmax = min(valores), max(valores)
    else:
        gvmin = gvmax = None
    mock_global.fetchone.return_value = MagicMock(
        gmin_verde=gvmin, gmax_verde=gvmax,
        gmin_muerta=gvmin, gmax_muerta=gvmax,
        gmin_total=gvmin, gmax_total=gvmax,
    )
    mock_buckets = MagicMock()
    mock_buckets.fetchall.return_value = buckets
    seq = []
    if dueno is not None:
        mock_dueno = MagicMock()
        mock_dueno.fetchone.return_value = (1,) if dueno is True else (dueno or None)
        seq.append(mock_dueno)
    seq += [mock_area, mock_stats, mock_global, mock_buckets, mock_buckets, mock_buckets]
    mock_conn.execute.side_effect = seq
    return mock_engine, mock_conn


def test_histograma_ok():
    eng, conn = _mock_hist_engine([10.0, 20.0, 30.0, 40.0], dueno=None)
    with patch("api.routers.mapa.engine", eng):
        resp = client.get("/api/mapa/histograma?finca=F&fecha=2024-04-01&bins=5", headers=auth_headers(1))
    assert resp.status_code == 200
    data = resp.json()
    factor = (AREA_M2 / 4) / 1000.0
    assert data["stats"]["count"] == 4
    assert data["sin_datos"] is False
    # Bines comunes: un solo edges de largo bins+1 para las 3 series.
    assert len(data["edges"]) == 6
    assert set(data["series"].keys()) == {"verde", "muerta", "total"}
    for t in ("verde", "muerta", "total"):
        s = data["series"][t]
        assert s["count"] == 4
        assert len(s["counts"]) == 5
        assert sum(s["counts"]) == 4
        assert abs(sum(s["pcts"]) - 100.0) < 0.05
        assert abs(s["min"] - 10.0 * factor) < 0.001
        assert abs(s["max"] - 40.0 * factor) < 0.001
        assert abs(s["mean"] - 25.0 * factor) < 0.001
    assert data["filtros"]["potrero_id"] is None
    all_sql = " ".join(str(c[0][0]) for c in conn.execute.call_args_list)
    for col in ("densidad_verde_g_m2", "densidad_muerta_g_m2", "densidad_total_g_m2"):
        assert col in all_sql


def test_histograma_potrero_ok_y_404():
    eng, _ = _mock_hist_engine([10.0, 20.0], dueno=True)
    with patch("api.routers.mapa.engine", eng):
        resp = client.get("/api/mapa/histograma?finca=F&fecha=2024-04-01&bins=5&potrero_id=3", headers=auth_headers(1))
    assert resp.status_code == 200
    assert resp.json()["filtros"]["potrero_id"] == 3

    eng, _ = _mock_hist_engine([10.0, 20.0], dueno=False)
    with patch("api.routers.mapa.engine", eng):
        resp = client.get("/api/mapa/histograma?finca=F&fecha=2024-04-01&bins=5&potrero_id=999", headers=auth_headers(1))
    assert resp.status_code == 404


def test_histograma_sin_auth_401():
    resp = client.get("/api/mapa/histograma?finca=F&fecha=2024-04-01")
    assert resp.status_code == 401


def test_histograma_valor_unico_un_bin():
    eng, _ = _mock_hist_engine([50.0, 50.0], dueno=None)
    with patch("api.routers.mapa.engine", eng):
        resp = client.get("/api/mapa/histograma?finca=F&fecha=2024-04-01&bins=5", headers=auth_headers(1))
    data = resp.json()
    assert data["sin_datos"] is False
    assert len(data["edges"]) == 2
    for t in ("verde", "muerta", "total"):
        assert data["series"][t]["counts"] == [2]
        assert data["series"][t]["pcts"] == [100.0]


def test_histograma_sin_datos():
    eng, _ = _mock_hist_engine([], dueno=None)
    with patch("api.routers.mapa.engine", eng):
        resp = client.get("/api/mapa/histograma?finca=Vacia&fecha=2024-04-01", headers=auth_headers(1))
    assert resp.status_code == 200
    data = resp.json()
    assert data["sin_datos"] is True
    assert data["edges"] == []
    assert data["stats"]["count"] == 0


def test_histograma_sin_potrero_no_envia_pid_nulo():
    """Regresión: sin potrero_id, el SQL NO debe referenciar :pid.

    Antes se usaba `(:pid IS NULL OR potrero_id = :pid)`: con psycopg3 un
    parámetro None no tiene tipo inferible y Postgres rechaza la consulta
    con AmbiguousParameter ("could not determine data type of parameter"),
    devolviendo un 500 al pedir "Toda la estancia". El filtro por potrero
    ahora es un fragmento condicional que se omite cuando no aplica.
    """
    eng, conn = _mock_hist_engine([10.0, 20.0], dueno=None)
    with patch("api.routers.mapa.engine", eng):
        resp = client.get("/api/mapa/histograma?finca=F&fecha=2024-04-01&bins=5", headers=auth_headers(1))
    assert resp.status_code == 200
    for call in conn.execute.call_args_list:
        sql = str(call[0][0])
        params = call[0][1] if len(call[0]) > 1 else {}
        assert ":pid" not in sql, "SQL referenció :pid sin potrero_id (AmbiguousParameter en psycopg3)"
        assert "pid" not in params, "Se envió pid=None como parámetro sin tipo"


def test_histograma_con_potrero_si_filtra_por_pid():
    """Con potrero_id, las queries de área/stats/buckets sí filtran por :pid."""
    eng, conn = _mock_hist_engine([10.0, 20.0], dueno=True)
    with patch("api.routers.mapa.engine", eng):
        resp = client.get("/api/mapa/histograma?finca=F&fecha=2024-04-01&bins=5&potrero_id=3", headers=auth_headers(1))
    assert resp.status_code == 200
    con_pid = [str(call[0][0]) for call in conn.execute.call_args_list if ":pid" in str(call[0][0])]
    # ownership + área filtran por p.id = :pid; stats + buckets x3 por
    # potrero_id = :pid (la query global no filtra por potrero).
    assert len(con_pid) >= 5
    por_columna = [sql for sql in con_pid if "potrero_id = :pid" in sql]
    assert len(por_columna) >= 4  # stats + buckets de las 3 densidades


def test_histograma_parcela_ok_y_404():
    parc = MagicMock(potrero_id=7, geom_json={"type": "Polygon", "coordinates": []})
    eng, conn = _mock_hist_engine([10.0, 20.0], dueno=parc)
    with patch("api.routers.mapa.engine", eng):
        resp = client.get("/api/mapa/histograma?finca=F&fecha=2024-04-01&bins=5&parcela_id=9", headers=auth_headers(1))
    assert resp.status_code == 200
    data = resp.json()
    assert data["filtros"]["parcela_id"] == 9
    assert data["filtros"]["potrero_id"] == 7
    assert data["filtros"]["area_ha"] == round(AREA_M2 / 10000.0, 2)
    assert data["sin_datos"] is False
    all_sql = " ".join(str(c[0][0]) for c in conn.execute.call_args_list)
    assert "ST_Covers(ST_SetSRID(ST_GeomFromGeoJSON(:gj), 4326), m.geom)" in all_sql

    eng, _ = _mock_hist_engine([10.0, 20.0], dueno=False)
    with patch("api.routers.mapa.engine", eng):
        resp = client.get("/api/mapa/histograma?finca=F&fecha=2024-04-01&bins=5&parcela_id=999", headers=auth_headers(1))
    assert resp.status_code == 404


def test_histograma_potrero_y_parcela_consistente_200_y_mismatch_400():
    parc = MagicMock(potrero_id=7, geom_json={"type": "Polygon", "coordinates": []})
    eng, _ = _mock_hist_engine([10.0, 20.0], dueno=parc)
    with patch("api.routers.mapa.engine", eng):
        resp = client.get("/api/mapa/histograma?finca=F&fecha=2024-04-01&bins=5&potrero_id=7&parcela_id=9", headers=auth_headers(1))
    assert resp.status_code == 200
    assert resp.json()["filtros"]["parcela_id"] == 9

    parc = MagicMock(potrero_id=7, geom_json={"type": "Polygon", "coordinates": []})
    eng, _ = _mock_hist_engine([10.0, 20.0], dueno=parc)
    with patch("api.routers.mapa.engine", eng):
        resp = client.get("/api/mapa/histograma?finca=F&fecha=2024-04-01&potrero_id=3&parcela_id=9", headers=auth_headers(1))
    assert resp.status_code == 400
