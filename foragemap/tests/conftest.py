from unittest.mock import MagicMock

import pytest
from jose import jwt

from core.config import ALGORITHM, SECRET_KEY


def auth_headers(uid: int = 1) -> dict:
    token = jwt.encode({"sub": str(uid)}, SECRET_KEY, algorithm=ALGORITHM)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def h():
    return auth_headers


@pytest.fixture(autouse=True)
def _usuario_existente(monkeypatch):
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = (1,)
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    monkeypatch.setattr("core.seguridad.engine", mock_engine)
