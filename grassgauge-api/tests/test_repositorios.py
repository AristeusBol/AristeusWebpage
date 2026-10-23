import datetime
from unittest.mock import MagicMock

from repositorios.filtros import listar_fechas_disponibles, listar_fincas_disponibles
from repositorios.parcelas import hay_solape


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


def test_hay_solape_sin_excluir_no_bindea_null():
    """Al crear (excluir_id=None) no debe mandarse un parámetro NULL a comparar:
    psycopg/PG no puede inferir su tipo y la consulta falla (500)."""
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = MagicMock(solapa=False)
    assert hay_solape(mock_conn, "{}", potrero_id=1, usuario_id=1) is False
    sql = str(mock_conn.execute.call_args[0][0])
    params = mock_conn.execute.call_args[0][1]
    assert "IS NULL" not in sql
    assert "excluir" not in params


def test_hay_solape_con_excluir_filtra_la_propia():
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = MagicMock(solapa=False)
    assert hay_solape(mock_conn, "{}", potrero_id=1, usuario_id=1, excluir_id=7) is False
    sql = str(mock_conn.execute.call_args[0][0])
    params = mock_conn.execute.call_args[0][1]
    assert "id != :excluir" in sql
    assert params["excluir"] == 7
