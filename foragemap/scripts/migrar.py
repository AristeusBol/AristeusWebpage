#!/usr/bin/env python3
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

from core.config import DATABASE_URL

DIR = Path(__file__).resolve().parents[1] / "infraestructura" / "init_db"


def main():
    engine = create_engine(DATABASE_URL, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS schema_migrations (nombre TEXT PRIMARY KEY)"))
        aplicadas = {r[0] for r in conn.execute(text("SELECT nombre FROM schema_migrations"))}
        pendientes = [f for f in sorted(DIR.glob("1*.sql")) if f.name not in aplicadas]
        if not pendientes:
            print("[=] sin migraciones pendientes")
            return
        for f in pendientes:
            print(f"[*] aplicando {f.name}...")
            try:
                conn.execute(text(f.read_text()))
            except Exception as e:
                print(f"[X] {f.name}: {e}")
                sys.exit(1)
            conn.execute(text("INSERT INTO schema_migrations (nombre) VALUES (:n)"), {"n": f.name})
            print(f"[+] {f.name}")


if __name__ == "__main__":
    main()
