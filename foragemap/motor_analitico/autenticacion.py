import argparse
import bcrypt

from core.db import engine
from repositorios import usuarios


def registrar_usuario(email, password):
    nombre_extraido = email.split('@')[0].replace('.', ' ').title()

    salt = bcrypt.gensalt()
    hash_seguro = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    try:
        with engine.begin() as conn:
            nuevo_id = usuarios.insertar_usuario(conn, nombre_extraido, email, hash_seguro)
        print(f"[+] Ganadero '{nombre_extraido}' registrado con éxito. (ID asignado: {nuevo_id})")
    except Exception as e:
        print(f"[X] Error al registrar (¿El email ya existe?): {e}")


def login_usuario(email, password):
    with engine.connect() as conn:
        resultado = usuarios.obtener_por_email(conn, email)

    if not resultado:
        print("[X] Acceso denegado: El email no existe.")
        return

    usuario_id, nombre, hash_guardado = resultado

    if bcrypt.checkpw(password.encode('utf-8'), hash_guardado.encode('utf-8')):
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
