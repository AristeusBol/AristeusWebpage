"""Backfill de celdas precalculadas del mapa de masa seca (mapa_celdas).

El endpoint de tiles lee geometrías ya recortadas (celdas 16x16m ∩ potrero
− exclusiones) en vez de construirlas por tile: ~50-150ms vs ~2-7s por tile.
La ingesta por CSV lo hace solo (ingestar_csv.py); este CLI sirve para:

  - la carga inicial / migración de bases que ya tenían datos;
  - regenerar a mano tras tocar la BD por fuera de la app.

Uso:
    python motor_analitico/precalcular_celdas.py                     # todos los grupos
    python motor_analitico/precalcular_celdas.py --fecha 2026-09-14  # solo esa fecha
    python motor_analitico/precalcular_celdas.py --usuario 1 --finca Aristeus
"""

import argparse
import sys
import time
from datetime import date

from sqlalchemy import text

from core.db import engine
from repositorios import celdas


def _parsear_fecha(valor):
    if not valor:
        return None
    try:
        return date.fromisoformat(valor.strip())
    except ValueError:
        print(f"[X] Fecha inválida '{valor}'. Usá formato YYYY-MM-DD.")
        sys.exit(2)


def principal():
    parser = argparse.ArgumentParser(
        description="Precalcula mapa_celdas desde mapa_color (el mapa de masa seca lee esas celdas)."
    )
    parser.add_argument("--usuario", type=int, default=None, help="Solo ese usuario")
    parser.add_argument("--finca", type=str, default=None, help="Solo esa estancia (requiere --usuario)")
    parser.add_argument("--fecha", type=str, default=None, help="Solo esa fecha YYYY-MM-DD")
    parser.add_argument(
        "--sin-invalidar-cache",
        action="store_true",
        help="No borra mapa_tiles_cache tras regenerar (por defecto se borra: los tiles viejos ya no aplican)",
    )
    args = parser.parse_args()

    if args.finca and args.usuario is None:
        print("[X] --finca requiere --usuario.")
        return 2

    fecha = _parsear_fecha(args.fecha)

    print("[*] Asegurando esquema (mapa_celdas, mapa_tiles_cache)...")
    try:
        celdas.asegurar_esquema(engine)
    except Exception as e:  # noqa: BLE001
        print(f"[X] No se pudo crear el esquema: {e}")
        return 1

    with engine.connect() as conn:
        if args.usuario is not None and args.finca:
            grupos = [(args.usuario, args.finca)]
        else:
            # Condición armada en Python: un parámetro opcional comparado
            # contra NULL hace que PG no pueda inferir su tipo
            # ("could not determine data type of parameter").
            sql_txt = "SELECT DISTINCT usuario_id, finca FROM mapa_color"
            params: dict = {}
            if args.usuario is not None:
                sql_txt += " WHERE usuario_id = :uid"
                params["uid"] = args.usuario
            sql_txt += " ORDER BY usuario_id, finca"
            grupos = [(int(r[0]), str(r[1])) for r in conn.execute(text(sql_txt), params).fetchall()]

    if not grupos:
        print("[!] No hay grupos con datos de mapa_color; nada que precalcular.")
        return 0

    total_celdas, t_total = 0, 0.0
    for uid, finca in grupos:
        with engine.connect() as conn:
            sql_txt = """
                SELECT DISTINCT fecha FROM mapa_color
                WHERE usuario_id = :uid AND finca = :finca
            """
            params: dict = {"uid": uid, "finca": finca}
            if fecha is not None:
                sql_txt += " AND fecha = :fecha"
                params["fecha"] = fecha
            sql_txt += " ORDER BY fecha"
            fechas = [r[0] for r in conn.execute(text(sql_txt), params).fetchall()]
        if not fechas:
            print(f"[!] Usuario {uid} / '{finca}': sin fechas con datos.")
            continue
        for f in fechas:
            t0 = time.time()
            try:
                with engine.begin() as conn:
                    n = celdas.precalcular_grupo(conn, uid, finca, f)
                    if not args.sin_invalidar_cache:
                        celdas.invalidar_cache_tiles(conn, uid, finca, f)
            except Exception as e:  # noqa: BLE001
                print(f"[X] {finca} {f} (usuario {uid}): {e}")
                # Sin celdas del grupo el mapa vuelve al cálculo on-the-fly:
                # nunca servir celdas viejas.
                try:
                    with engine.begin() as conn:
                        celdas.limpiar_celdas(conn, uid, finca, f)
                        if not args.sin_invalidar_cache:
                            celdas.invalidar_cache_tiles(conn, uid, finca, f)
                except Exception as e2:  # noqa: BLE001
                    print(f"    No se pudo limpiar el grupo: {e2}")
                continue
            dt = time.time() - t0
            total_celdas += n
            t_total += dt
            print(f"[+] {finca} {f} (usuario {uid}): {n} celdas en {dt:.1f}s")

    print(f"[+] Listo: {total_celdas} celdas en {t_total:.1f}s. Los tiles ahora se sirven desde mapa_celdas.")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
