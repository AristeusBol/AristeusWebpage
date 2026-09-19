from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_health_root():
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_health_db_up():
    mock_conn = MagicMock()
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    with patch("core.db.engine", mock_engine):
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "db": "up"}
    mock_conn.execute.assert_called_once()


def test_auth_usuario_eliminado_401():
    from tests.conftest import auth_headers
    mock_conn = MagicMock()
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.return_value.fetchone.return_value = None
    with patch("core.seguridad.engine", mock_engine):
        resp = client.get("/api/mapa/filtros", headers=auth_headers(1))
    assert resp.status_code == 401


def test_registro_email_largo_400():
    resp = client.post("/api/auth/registro", json={"email": "a" * 140 + "@x.com", "password": "123456"})
    assert resp.status_code == 400


def test_openapi_expone_endpoints():
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json()["paths"]
    assert "/api/mapa/filtros" in paths
    assert "/api/mapa/tiles/{z}/{x}/{y}.pbf" in paths
    assert "/api/dashboard/serie" in paths
    assert "/api/auth/registro" in paths
    assert "/api/auth/login" in paths


def test_obtener_por_email_case_insensitive():
    from unittest.mock import MagicMock

    from repositorios.usuarios import obtener_por_email

    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = (1, "Pepe", "hash")
    row = obtener_por_email(conn, "PEPE@X.COM")
    assert row == (1, "Pepe", "hash")
    sql = str(conn.execute.call_args[0][0])
    assert "lower(email)" in sql


def test_login_email_mayusculas_ok():
    from unittest.mock import MagicMock, patch

    from fastapi.testclient import TestClient

    from api.main import app

    conn = MagicMock()
    with patch("api.routers.auth.usuarios.obtener_por_email", return_value=(1, "Pepe", "hash")) as q, \
         patch("api.routers.auth.bcrypt.checkpw", return_value=True):
        resp = TestClient(app).post(
            "/api/auth/login", json={"email": "PEPE@X.COM", "password": "cualquiera"}
        )
    assert resp.status_code == 200
    assert resp.json()["email"] == "pepe@x.com"
    # El repo recibe el email ya normalizado a minúsculas.
    assert q.call_args[0][1] == "pepe@x.com"
