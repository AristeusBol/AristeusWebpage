from datetime import date
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api.main import app
from tests.conftest import auth_headers

client = TestClient(app)


def _parcela_row(**kw):
    base = dict(
        id=2, potrero_id=3, nombre="A1", estado="optimo",
        geom_json={"type": "Polygon", "coordinates": []}, finca="Don Carlos",
        area_ha=4.0,
    )
    base.update(kw)
    return MagicMock(**base)


def _conn_from(rows, fetchall_side_effect):
    conn = MagicMock()
    conn.execute.return_value.fetchall.side_effect = fetchall_side_effect
    eng = MagicMock()
    eng.connect.return_value.__enter__.return_value = conn
    patcher = patch("api.routers.balance.repo_parcelas.listar_parcelas_finca", return_value=rows)
    patcher.start()
    return conn, eng, patcher


def test_balance_sin_auth_401():
    assert client.get("/api/balance").status_code == 401


def test_balance_finca_vacia_400():
    resp = client.get("/api/balance", params={"finca": ""}, headers=auth_headers(1))
    assert resp.status_code == 400


def test_balance_utilizacion_invalida_400():
    conn, eng, patcher = _conn_from([_parcela_row()], [])
    try:
        with patch("api.routers.balance.engine", eng):
            resp = client.get(
                "/api/balance", params={"finca": "Don Carlos", "utilizacion": 30},
                headers=auth_headers(1),
            )
        assert resp.status_code == 400
    finally:
        patcher.stop()


def _zonal(masa=8000.0, t_ha=2.0, area=4.0, n=10):
    return {
        "masa_verde_kg": masa, "masa_muerta_kg": 0.0, "masa_total_kg": masa,
        "t_ha_verde": t_ha, "t_ha_muerta": 0.0, "t_ha_total": t_ha,
        "tiene_calculo": True, "estimado_zonal": True,
        "n_puntos": n, "area_ha": area,
    }


def test_balance_ok_urgente_por_consumo():
    p = _parcela_row()
    conn = MagicMock()
    conn.execute.return_value.fetchall.side_effect = [
        [MagicMock(id=3, nombre="Norte")],                       # potreros
        [],                                                      # calculos (no usado: zonal ok)
        [MagicMock(parcela_id=2, rodeo_id=1, rodeo="Lote 1",
                   cabezas=80, peso_prom_kg=450.0, consumo_pct=2.8)],  # asignaciones
    ]
    eng = MagicMock()
    eng.connect.return_value.__enter__.return_value = conn
    with patch("api.routers.balance.repo_parcelas.listar_parcelas_finca", return_value=[p]), \
         patch("api.routers.balance._zonales_finca", return_value={2: _zonal(masa=8000.0)}), \
         patch("api.routers.balance.engine", eng):
        resp = client.get(
            "/api/balance",
            params={"finca": "Don Carlos", "fecha": "2026-09-13"},
            headers=auth_headers(1),
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["utilizacion_pct"] == 50
    assert data["resumen"]["parcelas_total"] == 1
    assert data["resumen"]["consumo_diario_total_kg"] == 1008.0
    assert data["resumen"]["oferta_total_kg"] == 8000.0
    parc = data["parcelas"][0]
    # días = 8000 × 0.5 / 1008 = 3.96 → urgente (no atento); usamos masa mayor
    assert parc["parcela"] == "A1"
    assert parc["potrero"] == "Norte"
    assert parc["ocupada"] is True
    assert parc["consumo_diario_kg"] == 1008.0
    assert parc["rodeos"][0]["rodeo"] == "Lote 1"
    assert 3 < parc["dias_pastoreo"] < 4.2
    assert parc["semaforo"] == "urgente"


def test_balance_semaforo_ok_con_masa_alta():
    p = _parcela_row()
    conn = MagicMock()
    conn.execute.return_value.fetchall.side_effect = [
        [MagicMock(id=3, nombre="Norte")],
        [],
        [MagicMock(parcela_id=2, rodeo_id=1, rodeo="Lote 1",
                   cabezas=80, peso_prom_kg=450.0, consumo_pct=2.8)],
    ]
    eng = MagicMock()
    eng.connect.return_value.__enter__.return_value = conn
    with patch("api.routers.balance.repo_parcelas.listar_parcelas_finca", return_value=[p]), \
         patch("api.routers.balance._zonales_finca", return_value={2: _zonal(masa=50000.0)}), \
         patch("api.routers.balance.engine", eng):
        resp = client.get(
            "/api/balance",
            params={"finca": "Don Carlos", "fecha": "2026-09-13"},
            headers=auth_headers(1),
        )
    parc = resp.json()["parcelas"][0]
    # 50000 × 0.5 / 1008 = 24.8 → ok
    assert parc["semaforo"] == "ok"
    assert parc["dias_pastoreo"] >= 24


def test_balance_libre_sin_rodeo():
    p = _parcela_row()
    conn = MagicMock()
    conn.execute.return_value.fetchall.side_effect = [
        [MagicMock(id=3, nombre="Norte")], [], [],
    ]
    eng = MagicMock()
    eng.connect.return_value.__enter__.return_value = conn
    with patch("api.routers.balance.repo_parcelas.listar_parcelas_finca", return_value=[p]), \
         patch("api.routers.balance._zonales_finca", return_value={2: _zonal()}):
        with patch("api.routers.balance.engine", eng):
            resp = client.get(
                "/api/balance",
                params={"finca": "Don Carlos", "fecha": "2026-09-13"},
                headers=auth_headers(1),
            )
    parc = resp.json()["parcelas"][0]
    assert parc["ocupada"] is False
    assert parc["dias_pastoreo"] is None
    assert parc["semaforo"] == "libre"


def test_balance_fallback_prorrateo():
    """Parcela sin puntos zonales: usa prorrateo del potrero (calculo_stock)."""
    p = _parcela_row(area_ha=2.0)
    conn = MagicMock()
    conn.execute.return_value.fetchall.side_effect = [
        [MagicMock(id=3, nombre="Norte")],
        [MagicMock(potrero_id=3, area_neta_ha=40.0, masa_seca_verde=60000.0,
                   masa_seca_muerta=0.0, masa_seca_total=60000.0)],
        [],
    ]
    eng = MagicMock()
    eng.connect.return_value.__enter__.return_value = conn
    with patch("api.routers.balance.repo_parcelas.listar_parcelas_finca", return_value=[p]), \
         patch("api.routers.balance._zonales_finca", return_value={2: _zonal(n=0)}), \
         patch("api.routers.balance.engine", eng):
        resp = client.get(
            "/api/balance",
            params={"finca": "Don Carlos", "fecha": "2026-09-13"},
            headers=auth_headers(1),
        )
    parc = resp.json()["parcelas"][0]
    # prorrateo: 60000 × 2/40 = 3000 kg MS
    assert parc["masa_total_kg"] == 3000.0
    assert parc["estimado_por_prorrateo"] is True
    assert parc["tiene_calculo"] is True


def test_balance_sin_dato_con_rodeo():
    """Rodeo comiendo pero sin cálculo en la fecha → sin_dato."""
    p = _parcela_row()
    conn = MagicMock()
    conn.execute.return_value.fetchall.side_effect = [
        [MagicMock(id=3, nombre="Norte")],
        [],
        [MagicMock(parcela_id=2, rodeo_id=1, rodeo="Lote 1",
                   cabezas=80, peso_prom_kg=450.0, consumo_pct=2.8)],
    ]
    eng = MagicMock()
    eng.connect.return_value.__enter__.return_value = conn
    with patch("api.routers.balance.repo_parcelas.listar_parcelas_finca", return_value=[p]), \
         patch("api.routers.balance._zonales_finca", return_value={}), \
         patch("api.routers.balance._prorrateo",
               return_value={"masa_total_kg": None, "t_ha_total": None,
                             "tiene_calculo": False, "estimado_por_prorrateo": False}), \
         patch("api.routers.balance.engine", eng):
        resp = client.get(
            "/api/balance",
            params={"finca": "Don Carlos", "fecha": "2026-09-13"},
            headers=auth_headers(1),
        )
    parc = resp.json()["parcelas"][0]
    assert parc["ocupada"] is True
    assert parc["dias_pastoreo"] is None
    assert parc["semaforo"] == "sin_dato"


def test_balance_sin_parcelas_200():
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = []
    eng = MagicMock()
    eng.connect.return_value.__enter__.return_value = conn
    with patch("api.routers.balance.repo_parcelas.listar_parcelas_finca", return_value=[]), \
         patch("api.routers.balance.engine", eng):
        resp = client.get(
            "/api/balance",
            params={"finca": "Otra Finca", "fecha": "2026-09-13"},
            headers=auth_headers(1),
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["resumen"]["parcelas_total"] == 0
    assert data["parcelas"] == []


def test_balance_sin_fecha_usa_la_ultima():
    """Sin fecha pedida, se resuelve la última con datos y se calcula la masa."""
    p = _parcela_row()
    conn = MagicMock()
    conn.execute.return_value.fetchone.side_effect = [
        (date(2026, 8, 31),),   # SELECT MAX(fecha) → última fecha del usuario
    ]
    conn.execute.return_value.fetchall.side_effect = [
        [MagicMock(id=3, nombre="Norte")],                 # potreros
        [],                                                # calculos (zonal ok)
        [],                                                # asignaciones
    ]
    eng = MagicMock()
    eng.connect.return_value.__enter__.return_value = conn
    with patch("api.routers.balance.repo_parcelas.listar_parcelas_finca", return_value=[p]), \
         patch("api.routers.balance._zonales_finca", return_value={2: _zonal(masa=8000.0)}), \
         patch("api.routers.balance.engine", eng):
        resp = client.get(
            "/api/balance",
            params={"finca": "Don Carlos"},
            headers=auth_headers(1),
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["fecha"] == "2026-08-31"
    assert data["parcelas"][0]["masa_total_kg"] == 8000.0

def test_ultima_fecha_prefiere_calculos():
    from api.routers.balance import _ultima_fecha

    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = (date(2026, 8, 31),)
    assert _ultima_fecha(conn, 1, "F") == date(2026, 8, 31)
    assert conn.execute.call_count == 1  # no llega a mapa_color
    assert "calculos_stock" in str(conn.execute.call_args[0][0])


def test_ultima_fecha_fallback_mapa():
    from api.routers.balance import _ultima_fecha

    conn = MagicMock()
    conn.execute.return_value.fetchone.side_effect = [(None,), (date(2026, 7, 1),)]
    assert _ultima_fecha(conn, 1, "F") == date(2026, 7, 1)
    assert conn.execute.call_count == 2
    assert "mapa_color" in str(conn.execute.call_args_list[1][0][0])


def test_ultima_fecha_sin_datos_none():
    from api.routers.balance import _ultima_fecha

    conn = MagicMock()
    conn.execute.return_value.fetchone.side_effect = [(None,), (None,)]
    assert _ultima_fecha(conn, 1, "F") is None
