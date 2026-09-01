from sqlalchemy import text


def insertar_usuario(conn, nombre, email, password_hash):
    consulta = text(
        "INSERT INTO usuarios (nombre, email, password_hash) "
        "VALUES (:n, :e, :p) RETURNING id"
    )
    return conn.execute(consulta, {"n": nombre, "e": email, "p": password_hash}).scalar()


def obtener_por_email(conn, email):
    consulta = text(
        "SELECT id, nombre, password_hash FROM usuarios WHERE email = :e"
    )
    return conn.execute(consulta, {"e": email}).fetchone()
