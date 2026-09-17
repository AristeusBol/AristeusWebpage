import datetime
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from api.main import app
from tests.conftest import auth_headers
import api.routers.calibracion as calib

client = TestClient(app)

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 100


def _mock_conn(fetchone=None, fetchall=None):
    mock_conn = MagicMock()
    if fetchone is not None:
        mock_conn.execute.return_value.fetchone.return_value = fetchone
    if fetchall is not None:
        mock_conn.execute.return_value.fetchall.return_value = fetchall
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    mock_engine.begin.return_value.__enter__.return_value = mock_conn
    return mock_engine, mock_conn


def test_potreros_sin_auth_401():
    resp = client.get("/api/potreros")
    assert resp.status_code == 401


def test_potreros_lista_ok():
    eng, _ = _mock_conn(fetchall=[
        MagicMock(id=1, nombre="Lote a1", finca="Finca Don Carlos"),
        MagicMock(id=2, nombre="Lote a2", finca="Finca Don Carlos"),
    ])
    with patch("api.routers.calibracion.engine", eng):
        resp = client.get("/api/potreros", headers=auth_headers(1))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["potreros"]) == 2
    assert data["potreros"][0]["nombre"] == "Lote a1"


def test_potrero_detalle_404():
    mock_conn = MagicMock()
    eng = MagicMock()
    eng.connect.return_value.__enter__.return_value = mock_conn
    with patch("api.routers.calibracion.engine", eng):
        with patch("api.routers.calibracion.repo_potreros.potrero_y_exclusiones_geojson", return_value=None):
            resp = client.get("/api/potreros/999", headers=auth_headers(1))
    assert resp.status_code == 404


def test_subir_foto_sin_auth_401():
    resp = client.post("/api/calibracion/fotos", data={"potrero_id": 1})
    assert resp.status_code in (401, 422)


def test_subir_foto_ok(tmp_path, monkeypatch):
    monkeypatch.setattr(calib, "UPLOAD_DIR", tmp_path)
    dentro = MagicMock(nombre="Lote a1", finca="Finca Don Carlos", dentro=True)
    ins = MagicMock(id=7, created_at=datetime.datetime(2026, 9, 6, 12, 0, 0))
    mock_connect = MagicMock()
    mock_connect.execute.return_value.fetchone.return_value = dentro
    mock_begin = MagicMock()
    mock_begin.execute.return_value.fetchone.return_value = ins
    eng = MagicMock()
    eng.connect.return_value.__enter__.return_value = mock_connect
    eng.begin.return_value.__enter__.return_value = mock_begin
    with patch("api.routers.calibracion.engine", eng):
        resp = client.post(
            "/api/calibracion/fotos",
            data={"potrero_id": "1", "latitud": "-15.95", "longitud": "-61.04", "fecha": "2026-08-31"},
            files={"foto": ("campo.jpg", JPEG, "image/jpeg")},
            headers=auth_headers(1),
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["id"] == 7
    assert data["url"].startswith("/uploads/1/")
    assert data["finca"] == "Finca Don Carlos"
    guardados = list((tmp_path / "1").glob("*.jpg"))
    assert len(guardados) == 1


def test_subir_foto_punto_fuera_400(tmp_path, monkeypatch):
    monkeypatch.setattr(calib, "UPLOAD_DIR", tmp_path)
    fuera = MagicMock(nombre="Lote a1", finca="F", dentro=False)
    eng, _ = _mock_conn(fetchone=fuera)
    with patch("api.routers.calibracion.engine", eng):
        resp = client.post(
            "/api/calibracion/fotos",
            data={"potrero_id": "1", "latitud": "0", "longitud": "0", "fecha": "2026-08-31"},
            files={"foto": ("a.jpg", JPEG, "image/jpeg")},
            headers=auth_headers(1),
        )
    assert resp.status_code == 400
    assert "fuera del potrero" in resp.json()["detail"]


def test_subir_foto_no_imagen_400():
    eng, _ = _mock_conn()
    with patch("api.routers.calibracion.engine", eng):
        resp = client.post(
            "/api/calibracion/fotos",
            data={"potrero_id": "1", "latitud": "-15.9", "longitud": "-61.0", "fecha": "2026-08-31"},
            files={"foto": ("a.txt", b"hola mundo", "text/plain")},
            headers=auth_headers(1),
        )
    assert resp.status_code == 400


def test_subir_foto_carrera_404(tmp_path, monkeypatch):
    from sqlalchemy.exc import IntegrityError
    monkeypatch.setattr(calib, "UPLOAD_DIR", tmp_path)
    dentro = MagicMock(nombre="Lote a1", finca="Finca Don Carlos", dentro=True)
    mock_connect = MagicMock()
    mock_connect.execute.return_value.fetchone.return_value = dentro
    mock_begin = MagicMock()
    mock_begin.execute.side_effect = IntegrityError("INSERT", {}, Exception("fk"))
    eng = MagicMock()
    eng.connect.return_value.__enter__.return_value = mock_connect
    eng.begin.return_value.__enter__.return_value = mock_begin
    with patch("api.routers.calibracion.engine", eng):
        resp = client.post(
            "/api/calibracion/fotos",
            data={"potrero_id": "1", "latitud": "-15.9", "longitud": "-61.0", "fecha": "2026-08-31"},
            files={"foto": ("a.jpg", JPEG, "image/jpeg")},
            headers=auth_headers(1),
        )
    assert resp.status_code == 404


def test_subir_foto_potrero_ajeno_404(tmp_path, monkeypatch):
    monkeypatch.setattr(calib, "UPLOAD_DIR", tmp_path)
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = None
    eng = MagicMock()
    eng.connect.return_value.__enter__.return_value = mock_conn
    eng.begin.return_value.__enter__.return_value = mock_conn
    with patch("api.routers.calibracion.engine", eng):
        resp = client.post(
            "/api/calibracion/fotos",
            data={"potrero_id": "999", "latitud": "-15.9", "longitud": "-61.0", "fecha": "2026-08-31"},
            files={"foto": ("a.jpg", JPEG, "image/jpeg")},
            headers=auth_headers(1),
        )
    assert resp.status_code == 404


def test_listar_fotos_ok():
    eng, _ = _mock_conn(fetchall=[
        MagicMock(id=7, fecha=datetime.date(2026, 8, 31), lat=-15.9, lon=-61.0,
                  foto_path="1/abc.jpg", mime="image/jpeg",
                  created_at=datetime.datetime(2026, 9, 6, 12, 0, 0)),
    ])
    with patch("api.routers.calibracion.engine", eng):
        resp = client.get("/api/calibracion/fotos?potrero_id=1", headers=auth_headers(1))
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1
    assert data["fotos"][0]["url"] == "/uploads/1/abc.jpg"


def test_detectar_mime():
    assert calib._detectar_mime(b"\xff\xd8\xff" + b"0" * 10) == "image/jpeg"
    assert calib._detectar_mime(b"\x89PNG\r\n\x1a\n" + b"0" * 10) == "image/png"
    assert calib._detectar_mime(b"RIFF1234WEBP" + b"0" * 10) == "image/webp"
    assert calib._detectar_mime(b"hola mundo") is None


def test_openapi_expone_calibracion():
    resp = client.get("/openapi.json")
    paths = resp.json()["paths"]
    assert "/api/potreros" in paths
    assert "/api/potreros/{potrero_id}" in paths
    assert "/api/calibracion/fotos" in paths
