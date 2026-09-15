import argparse
import bcrypt

from core.db import engine
from repositorios import usuarios


def registrar_usuario(email, password):
    email = email.strip().lower()
    if "@" not in email or "." not in email:
        print("[X] Email inválido.")
        return
    if len(email) > 100:
        print("[X] Email demasiado largo (máx. 100).")
        return
    if len(password) < 6:
        print("[X] Contraseña debe tener al menos 6 caracteres.")
        return
    if len(password.encode('utf-8')) > 72:
        print("[X] Contraseña demasiado larga (máx. 72 bytes).")
        return

    nombre_extraido = email.split('@')[0].replace('.', ' ').title()

    try:
        salt = bcrypt.gensalt()
        hash_seguro = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    except ValueError:
        print("[X] Contraseña inválida.")
        return

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

    try:
        ok = bcrypt.checkpw(password.encode('utf-8'), hash_guardado.encode('utf-8'))
    except (ValueError, TypeError):
        print("[X] Acceso denegado: Contraseña incorrecta.")
        return
    if ok:
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