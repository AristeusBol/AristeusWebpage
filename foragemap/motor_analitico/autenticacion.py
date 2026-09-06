import argparse

from core.db import engine
from core.seguridad import (
    email_valido,
    hash_password,
    verificar_password,
    derivar_nombre,
)
from repositorios import usuarios


def registrar_usuario(email, password):
    email = email.strip().lower()
    if not email_valido(email):
        print("[X] Email inválido.")
        return
    if len(email) > 100:
        print("[X] Email demasiado largo (máx. 100).")
        return
    if len(password) < 6:
        print("[X] Contraseña debe tener al menos 6 caracteres.")
        return

    nombre_extraido = derivar_nombre(email)
    hash_seguro = hash_password(password)

    try:
        with engine.begin() as conn:
            nuevo_id = usuarios.insertar_usuario(conn, nombre_extraido, email, hash_seguro)
        print(f"[+] Ganadero '{nombre_extraido}' registrado con éxito. (ID asignado: {nuevo_id})")
    except Exception as e:
        print(f"[X] Error al registrar (¿El email ya existe?): {e}")


def login_usuario(email, password):
    email = email.strip().lower()
    with engine.connect() as conn:
        resultado = usuarios.obtener_por_email(conn, email)

    if not resultado:
        print("[X] Acceso denegado: El email no existe.")
        return

    usuario_id, nombre, hash_guardado = resultado

    if verificar_password(password, hash_guardado):
        print(f"[+] ¡Login exitoso! Bienvenido {nombre} (ID: {usuario_id})")
    else:
        print("[X] Acceso denegado: Contraseña incorrecta.")


def principal():
    parser = argparse.ArgumentParser(description="Módulo de Seguridad y Login.")
    parser.add_argument("--accion", choices=['registro', 'login'], required=True, help="Qué querés hacer")
    parser.add_argument("--email", type=str, required=True, help="Correo del ganadero")
    parser.add_argument("--password", type=str, required=True, help="Contraseña plana")
    args = parser.parse_args()

    if args.accion == 'registro':
        registrar_usuario(args.email, args.password)
    elif args.accion == 'login':
        login_usuario(args.email, args.password)


if __name__ == "__main__":
    principal()