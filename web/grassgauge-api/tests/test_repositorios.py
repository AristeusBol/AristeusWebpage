import datetime
from unittest.mock import MagicMock

from repositorios.filtros import listar_fechas_disponibles, listar_fincas_disponibles


def test_repositorio_fincas_query():
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = [("A",), ("B",)]
    res = listar_fincas_disponibles(mock_conn, usuario_id=1)
    assert res == ["A", "B"]
    sql = str(mock_conn.execute.call_args[0][0])
    assert "SELECT DISTINCT finca" in sql
    assert "calculos_stock" in sql


def test_repositorio_fechas_sin_finca():
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = [(datetime.date(2024, 1, 1),)]
    res = listar_fechas_disponibles(mock_conn, usuario_id=1, finca=None)
    assert res == ["2024-01-01"]
    sql = str(mock_conn.execute.call_args[0][0])
    assert "AND finca" not in sql


def test_repositorio_fechas_con_finca():
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = [(datetime.date(2024, 1, 1),)]
    res = listar_fechas_disponibles(mock_conn, usuario_id=1, finca="X")
    assert res == ["2024-01-01"]
    sql = str(mock_conn.execute.call_args[0][0])
    assert "AND finca = :finca" in sql
