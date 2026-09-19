from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api.main import app
from tests.conftest import auth_headers

client = TestClient(app)


def _fila_row(**kw):
    base = dict(
        asignacion_id=7, fecha_entrada=date(2026, 3, 1), fecha_salida=None, notas=None,
        trayectoria_inicio=None,
        rodeo_id=1, rodeo="Lote 1", categoria="vaca_lactancia",
        cabezas=80, peso_prom_kg=450.0, consumo_pct=2.8,
        parcela_id=2, parcela="A1", estado="optimo",
        potrero_id=3, potrero="Norte", finca="Don Carlos",
    )
    base.update(kw)
    return MagicMock(**base)


def _mock_engine_conexiones(conns_connect=None, conn_begin=None):
    """engine.connect devuelve conns_connect (lista, una por llamada); engine.begin devuelve conn_begin."""
    eng = MagicMock()
    if conns_connect is None:
        conns_connect = [MagicMock()]
    eng.connect.side_effect = [
        MagicMock(__enter__=(lambda self, c=c: c)) for c in conns_connect
    ]
    begin = MagicMock()
    if conn_begin is not None:
        begin.__enter__ = lambda self: conn_begin
    eng.begin.return_value = begin
    return eng


def _mock_trayectoria(filas, lotes, fin):
    """Una sola conexión con 3 executes: filas, lotes, finalizadas."""
    conn = MagicMock()
    conn.execute.side_effect = [
        MagicMock(fetchall=lambda: filas),
        MagicMock(fetchall=lambda: lotes),
        MagicMock(fetchall=lambda: fin),
    ]
    return _mock_engine_conexiones([conn])


def _fecha_fila(fecha_entrada: date, fecha_salida: date | None, trayectoria_inicio=None):
    return _fila_row(
        fecha_entrada=fecha_entrada,
        fecha_salida=fecha_salida,
        trayectoria_inicio=trayectoria_inicio,
    )


def test_trayectoria_agrupa_por_lote_con_estado_de_etapa():
    hoy = date.today()
    # lote 1 con 2 trayectorias: A (cerrada) y B (vigente → programada); lote 2 sin etapas
    filas = [
        _fecha_fila(hoy - timedelta(days=10), hoy - timedelta(days=3), trayectoria_inicio=hoy - timedelta(days=10)),
        _fecha_fila(hoy - timedelta(days=2), hoy + timedelta(days=3), trayectoria_inicio=hoy - timedelta(days=2)),
        _fecha_fila(hoy + timedelta(days=5), hoy + timedelta(days=9), trayectoria_inicio=hoy - timedelta(days=2)),
    ]
    lotes = [
        MagicMock(id=1, nombre="Lote 1", color="#ff8800",
                  cabezas=80, peso_prom_kg=450.0, consumo_pct=2.8),
        MagicMock(id=2, nombre="Lote 2", color=None,
                  cabezas=60, peso_prom_kg=380.0, consumo_pct=2.6),
    ]
    with patch("api.routers.rotacion.engine", _mock_trayectoria(
        filas, lotes,
        [MagicMock(rodeo_id=1, trayectoria_inicio=hoy - timedelta(days=2), finalizada_en=hoy - timedelta(days=1))],
    )):
        resp = client.get("/api/rotacion/trayectoria", headers=auth_headers(1))
    assert resp.status_code == 200
    data = resp.json()
    assert [t["rodeo"] for t in data["trayectoria"]] == ["Lote 1", "Lote 2"]
    lote1 = data["trayectoria"][0]
    assert lote1["color"] == "#ff8800"
    # Ordenadas de la más reciente a la más antigua
    assert [t["inicio"] for t in lote1["trayectorias"]] == [
        (hoy - timedelta(days=2)).isoformat(),
        (hoy - timedelta(days=10)).isoformat(),
    ]
    b, a = lote1["trayectorias"]
    assert [e["estado_etapa"] for e in b["etapas"]] == ["vigente", "programada"]
    assert [e["estado_etapa"] for e in a["etapas"]] == ["cerrada"]
    assert b["finalizada"] is True and b["finalizada_en"] == (hoy - timedelta(days=1)).isoformat()
    assert a["finalizada"] is False and a["finalizada_en"] is None
    vigente = b["etapas"][0]
    assert vigente["dias_planificados"] == 6
    assert vigente["dias_transcurridos"] == 3
    programada = b["etapas"][1]
    assert programada["dias_planificados"] == 5
    assert programada["dias_transcurridos"] is None
    assert data["trayectoria"][1]["trayectorias"] == []
    assert data["trayectoria"][1]["consumo_diario_ms_kg"] == 592.8


def test_trayectoria_agrupa_por_inicio():
    """Filas con trayectoria_inicio se agrupan por su grupo."""
    filas = [
        _fecha_fila(date(2026, 3, 2), date(2026, 3, 6), trayectoria_inicio=date(2026, 3, 2)),
        _fecha_fila(date(2026, 3, 7), date(2026, 3, 10), trayectoria_inicio=date(2026, 3, 2)),
        _fecha_fila(date(2026, 4, 1), None, trayectoria_inicio=date(2026, 4, 1)),
    ]
    lotes = [MagicMock(id=1, nombre="Lote 1", color=None,
                       cabezas=80, peso_prom_kg=450.0, consumo_pct=2.8)]
    with patch("api.routers.rotacion.engine", _mock_trayectoria(filas, lotes, [])):
        resp = client.get("/api/rotacion/trayectoria", headers=auth_headers(1))
    assert resp.status_code == 200
    lote1 = resp.json()["trayectoria"][0]
    assert [t["inicio"] for t in lote1["trayectorias"]] == [
        "2026-04-01",
        "2026-03-02",
    ]
    assert len(lote1["trayectorias"][0]["etapas"]) == 1
    assert len(lote1["trayectorias"][1]["etapas"]) == 2


def test_trayectoria_incluye_todos_los_lotes():
    lotes = [MagicMock(id=1, nombre="Activo", color=None,
                       cabezas=80, peso_prom_kg=450.0, consumo_pct=2.8)]
    with patch("api.routers.rotacion.engine", _mock_trayectoria([], lotes, [])):
        resp = client.get("/api/rotacion/trayectoria", headers=auth_headers(1))
    assert resp.status_code == 200
    assert [t["rodeo"] for t in resp.json()["trayectoria"]] == ["Activo"]


def test_finalizar_trayectoria_ok():
    inicio = date(2026, 4, 13)
    conn1 = MagicMock()
    conn1.execute.return_value.fetchone.return_value = (1,)  # trayectoria existe
    conn_begin = MagicMock()
    with patch("api.routers.rotacion.engine", _mock_engine_conexiones([conn1], conn_begin)):
        resp = client.post(f"/api/rotacion/trayectoria/1/{inicio}/finalizar", headers=auth_headers(1))
    assert resp.status_code == 200
    assert resp.json() == {"inicio": "2026-04-13", "finalizada": True, "parcelas_a_critico": 0}
    insert = conn_begin.execute.call_args
    assert "INSERT INTO trayectorias_finalizadas" in str(insert[0][0])
    assert insert[0][1] == {"uid": 1, "rid": 1, "inicio": inicio}


def test_finalizar_trayectoria_marca_parcelas_critico():
    inicio = date(2026, 4, 13)
    conn1 = MagicMock()
    conn1.execute.return_value.fetchone.return_value = (1,)  # trayectoria existe
    conn_begin = MagicMock()
    conn_begin.execute.return_value.fetchall.return_value = [MagicMock(id=1), MagicMock(id=2)]
    with patch("api.routers.rotacion.engine", _mock_engine_conexiones([conn1], conn_begin)):
        resp = client.post(
            f"/api/rotacion/trayectoria/1/{inicio}/finalizar",
            json={"enviar_critico": True},
            headers=auth_headers(1),
        )
    assert resp.status_code == 200
    assert resp.json()["parcelas_a_critico"] == 2
    criticas = [c for c in conn_begin.execute.call_args_list if "UPDATE parcelas" in str(c[0][0])]
    assert len(criticas) == 1
    assert criticas[0][0][1] == {"uid": 1, "rid": 1, "inicio": inicio}
    inserts = [c for c in conn_begin.execute.call_args_list if "INSERT INTO trayectorias_finalizadas" in str(c[0][0])]
    assert len(inserts) == 1


def test_finalizar_trayectoria_inexistente_404():
    conn1 = MagicMock()
    conn1.execute.return_value.fetchone.return_value = None
    with patch("api.routers.rotacion.engine", _mock_engine_conexiones([conn1])):
        resp = client.post(
            "/api/rotacion/trayectoria/1/2026-04-13/finalizar", headers=auth_headers(1)
        )
    assert resp.status_code == 404


def test_listar_rotacion_ok():
    hoy = date.today()
    fila_filas = [
        _fecha_fila(hoy - timedelta(days=2), None),        # vigente
        _fecha_fila(hoy - timedelta(days=10), hoy - timedelta(days=3)),  # cerrada
        _fecha_fila(hoy + timedelta(days=5), None),        # futura
    ]
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = fila_filas
    with patch("api.routers.rotacion.engine", _mock_engine_conexiones([conn])):
        resp = client.get("/api/rotacion", headers=auth_headers(1))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["asignaciones"]) == 3
    assert len(data["estado_actual"]) == 1
    assert data["estado_actual"][0]["parcela"] == "A1"
    assert data["estado_actual"][0]["consumo_diario_ms_kg"] == 1008.0
    assert data["resumen"]["rodeos_pastoreando"] == 1
    assert data["resumen"]["cabezas_pastoreando"] == 80
    assert data["resumen"]["consumo_diario_ms_kg"] == 1008.0
    assert data["resumen"]["parcelas_ocupadas"] == 1


def test_cerrar_asignacion_200():
    conn_check = MagicMock()
    conn_check.execute.return_value.fetchone.return_value = MagicMock(id=7, fecha_entrada=date(2026, 3, 1))
    conn_fila = MagicMock()
    conn_fila.execute.return_value.fetchone.return_value = _fila_row(fecha_salida=date(2026, 3, 15))
    with patch(
        "api.routers.rotacion.engine",
        _mock_engine_conexiones([conn_check, conn_fila], MagicMock()),
    ):
        resp = client.patch(
            "/api/rotacion/7",
            json={"fecha_salida": "2026-03-15"},
            headers=auth_headers(1),
        )
    assert resp.status_code == 200
    assert resp.json()["fecha_salida"] == "2026-03-15"


def test_cerrar_asignacion_salida_antes_entrada_400():
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = MagicMock(id=7, fecha_entrada=date(2026, 3, 1))
    with patch("api.routers.rotacion.engine", _mock_engine_conexiones([conn])):
        resp = client.patch(
            "/api/rotacion/7",
            json={"fecha_salida": "2026-02-01"},
            headers=auth_headers(1),
        )
    assert resp.status_code == 400


def test_armar_semana_ok():
    """7 días (lista de parcelas por día) → tramos: A1 días 13-14, B1 el 15, C1 los 18-19."""
    inicio = date(2026, 4, 13)
    conn1 = MagicMock()
    conn1.execute.return_value.fetchone.side_effect = [
        (1, "Lote 1"),                    # rodeo existe
        MagicMock(id=1, nombre="A1"),
        MagicMock(id=2, nombre="B1"),
        MagicMock(id=3, nombre="C1"),
    ]
    conn1.execute.return_value.fetchall.return_value = []  # sin solape del lote
    conn_begin = MagicMock()
    conn_begin.execute.return_value.fetchall.return_value = []  # sin choques
    with patch(
        "api.routers.rotacion.engine",
        _mock_engine_conexiones([conn1], conn_begin),
    ):
        resp = client.post(
            "/api/rotacion/semana",
            json={
                "rodeo_id": 1,
                "inicio": "2026-04-13",
                "dias": [[1], [1], [2], [], [], [3], [3]],
            },
            headers=auth_headers(1),
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["guardado"] is True
    assert len(data["dias"]) == 7
    assert data["dias"][0]["parcelas"][0]["parcela"] == "A1"
    assert data["dias"][1]["parcelas"][0]["parcela"] == "A1"
    assert data["dias"][3]["parcelas"] == []
    inserts = [c for c in conn_begin.execute.call_args_list if "INSERT INTO asignaciones" in str(c[0][0])]
    assert len(inserts) == 3
    p1 = inserts[0][0][1]
    assert p1["pid"] == 1 and p1["entrada"] == date(2026, 4, 13) and p1["salida"] == date(2026, 4, 14)
    assert p1["trayectoria"] == inicio
    p3 = inserts[2][0][1]
    assert p3["pid"] == 3 and p3["entrada"] == date(2026, 4, 18) and p3["salida"] == date(2026, 4, 19)


def test_armar_semana_repite_dias_mismo_lote_409():
    """Los días ya cubiertos por otra trayectoria del lote no se pueden ocupar."""
    inicio = date(2026, 4, 13)
    conn1 = MagicMock()
    conn1.execute.return_value.fetchone.side_effect = [
        (1, "Lote 1"),                    # rodeo existe
        MagicMock(id=1, nombre="A1"),
    ]
    conn1.execute.return_value.fetchall.return_value = [
        MagicMock(fecha_entrada=date(2026, 4, 15), fecha_salida=date(2026, 4, 16)),  # otra trayectoria
    ]
    with patch(
        "api.routers.rotacion.engine",
        _mock_engine_conexiones([conn1], MagicMock()),
    ):
        resp = client.post(
            "/api/rotacion/semana",
            json={
                "rodeo_id": 1,
                "inicio": "2026-04-13",
                "dias": [[], [], [1], [], [], [], []],   # día 15/04 ya ocupado
            },
            headers=auth_headers(1),
        )
    assert resp.status_code == 409
    assert "Se repiten días" in resp.json()["detail"]


def test_armar_semana_reemplaza_excluye_grupo_anterior():
    """Al editar (reemplazar_inicio) las filas del grupo anterior se borran y
    no cuentan como solape; las nuevas quedan con trayectoria_inicio."""
    inicio = date(2026, 4, 13)
    conn1 = MagicMock()
    conn1.execute.return_value.fetchone.side_effect = [
        (1, "Lote 1"),                    # rodeo existe
        MagicMock(id=1, nombre="A1"),
    ]
    conn1.execute.return_value.fetchall.return_value = [
        # El grupo propio queda excluido por reemplazar_inicio en el SQL;
        # el mock simula el resultado post-WHERE: sin filas cruzadas.
    ]
    conn_begin = MagicMock()
    conn_begin.execute.return_value.fetchall.return_value = []
    with patch(
        "api.routers.rotacion.engine",
        _mock_engine_conexiones([conn1], conn_begin),
    ):
        resp = client.post(
            "/api/rotacion/semana",
            json={
                "rodeo_id": 1,
                "inicio": "2026-04-13",
                "reemplazar_inicio": "2026-04-13",
                "dias": [[1], [], [], [], [], [], []],
            },
            headers=auth_headers(1),
        )
    assert resp.status_code == 200
    deletes = [c for c in conn_begin.execute.call_args_list if "DELETE FROM asignaciones" in str(c[0][0])]
    assert len(deletes) == 1
    assert deletes[0][0][1] == {"uid": 1, "rid": 1, "reemplazo": inicio}
    inserts = [c for c in conn_begin.execute.call_args_list if "INSERT INTO asignaciones" in str(c[0][0])]
    assert len(inserts) == 1
    assert inserts[0][0][1]["trayectoria"] == inicio


def test_eliminar_trayectoria_borra_grupo():
    inicio = date(2026, 4, 13)
    conn_begin = MagicMock()
    conn_begin.execute.return_value.fetchall.return_value = [MagicMock(id=1), MagicMock(id=2)]
    with patch("api.routers.rotacion.engine", _mock_engine_conexiones([], conn_begin)):
        resp = client.delete(f"/api/rotacion/trayectoria/1/{inicio}", headers=auth_headers(1))
    assert resp.status_code == 200
    assert resp.json()["asignaciones"] == 2
    deletes = [c for c in conn_begin.execute.call_args_list if "DELETE FROM asignaciones" in str(c[0][0])]
    assert len(deletes) == 1
    params = deletes[0][0][1]
    assert params["rid"] == 1 and params["inicio"] == inicio
    assert "trayectoria_inicio IS NULL" not in str(deletes[0][0][0])


def test_armar_semana_varias_parcelas_por_dia():
    """Día 0 con dos parcelas y la 2da continúa el día 1 → dos tramos bien formados."""
    inicio = date(2026, 4, 13)
    conn1 = MagicMock()
    conn1.execute.return_value.fetchone.side_effect = [
        (1, "Lote 1"),
        MagicMock(id=1, nombre="A1"),
        MagicMock(id=2, nombre="B1"),
    ]
    conn1.execute.return_value.fetchall.return_value = []  # sin solape del lote
    conn_begin = MagicMock()
    conn_begin.execute.return_value.fetchall.return_value = []
    with patch(
        "api.routers.rotacion.engine",
        _mock_engine_conexiones([conn1], conn_begin),
    ):
        resp = client.post(
            "/api/rotacion/semana",
            json={
                "rodeo_id": 1,
                "inicio": "2026-04-13",
                "dias": [[1, 2], [2], [], [], [], [], []],
            },
            headers=auth_headers(1),
        )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["dias"][0]["parcelas"]) == 2
    inserts = [c for c in conn_begin.execute.call_args_list if "INSERT INTO asignaciones" in str(c[0][0])]
    assert len(inserts) == 2
    p1, p2 = inserts[0][0][1], inserts[1][0][1]
    assert p1["pid"] == 1 and p1["entrada"] == date(2026, 4, 13) and p1["salida"] == date(2026, 4, 13)
    assert p2["pid"] == 2 and p2["entrada"] == date(2026, 4, 13) and p2["salida"] == date(2026, 4, 14)
    # Guardar no toca estados: solo finalizar con enviar_critico marca a crítico.
    assert not [c for c in conn_begin.execute.call_args_list if "UPDATE parcelas" in str(c[0][0])]


def test_armar_semana_no_toca_estado():
    """Guardar una trayectoria no cambia parcelas.estado (solo finalizar pregunta)."""
    inicio = date(2026, 4, 13)
    conn1 = MagicMock()
    conn1.execute.return_value.fetchone.side_effect = [
        (1, "Lote 1"),
        MagicMock(id=1, nombre="A1"),
    ]
    conn1.execute.return_value.fetchall.return_value = []
    conn_begin = MagicMock()
    conn_begin.execute.return_value.fetchall.return_value = []
    with patch(
        "api.routers.rotacion.engine",
        _mock_engine_conexiones([conn1], conn_begin),
    ):
        resp = client.post(
            "/api/rotacion/semana",
            json={
                "rodeo_id": 1,
                "inicio": "2026-04-13",
                "dias": [[1], [], [], [], [], [], []],
            },
            headers=auth_headers(1),
        )
    assert resp.status_code == 200
    assert not [c for c in conn_begin.execute.call_args_list if "UPDATE parcelas" in str(c[0][0])]
    assert len([c for c in conn_begin.execute.call_args_list if "INSERT INTO asignaciones" in str(c[0][0])]) == 1


def test_armar_semana_conflicto_otro_rodeo_409():
    inicio = date(2026, 4, 13)
    conn1 = MagicMock()
    conn1.execute.return_value.fetchone.side_effect = [
        (1, "Lote 1"),
        MagicMock(id=1, nombre="A1"),
        MagicMock(id=2, nombre="B1"),
    ]
    conn1.execute.return_value.fetchall.return_value = []  # sin solape del lote
    conn_begin = MagicMock()
    conn_begin.execute.return_value.fetchall.return_value = [MagicMock(parcela_id=2)]
    with patch(
        "api.routers.rotacion.engine",
        _mock_engine_conexiones([conn1], conn_begin),
    ):
        resp = client.post(
            "/api/rotacion/semana",
            json={
                "rodeo_id": 1,
                "inicio": "2026-04-13",
                "dias": [[1], [2], [], [], [], [], []],
            },
            headers=auth_headers(1),
        )
    assert resp.status_code == 409
    assert "B1" in resp.json()["detail"]


def test_armar_semana_len_invalido_422():
    resp = client.post(
        "/api/rotacion/semana",
        json={"rodeo_id": 1, "inicio": "2026-04-13", "dias": [[1]] * 8},  # más de 7 días
        headers=auth_headers(1),
    )
    assert resp.status_code == 422
    resp = client.post(
        "/api/rotacion/semana",
        json={"rodeo_id": 1, "inicio": "2026-04-13", "dias": []},  # vacío
        headers=auth_headers(1),
    )
    assert resp.status_code == 422


def test_rotacion_sin_auth_401():
    assert client.get("/api/rotacion").status_code == 401
    assert client.patch("/api/rotacion/7", json={}).status_code == 401
    assert client.post("/api/rotacion/semana", json={}).status_code == 401