#!/usr/bin/env python3
"""
migrate.py — Sistema de migraciones SQL ligero para IceBergTicket.

Uso:
    python scripts/migrate.py status         → Muestra las migraciones aplicadas y pendientes.
    python scripts/migrate.py up             → Aplica todas las migraciones pendientes en orden.
    python scripts/migrate.py create <nombre> → Genera un nuevo archivo de migración SQL.
"""
import os
import sys
import argparse
from datetime import datetime
from pathlib import Path
import psycopg2
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = BASE_DIR / "migrations"

load_dotenv()
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR.parent / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    if not DATABASE_URL:
        print("\n❌ Error: DATABASE_URL no está configurada en .env.")
        sys.exit(1)
    return psycopg2.connect(DATABASE_URL)


def ensure_migrations_table(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS public.schema_migrations (
                version VARCHAR(255) PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """)
    conn.commit()


def get_applied_migrations(conn) -> set:
    ensure_migrations_table(conn)
    with conn.cursor() as cur:
        cur.execute("SELECT version FROM public.schema_migrations ORDER BY version ASC;")
        rows = cur.fetchall()
        return {r[0] for r in rows}


def get_migration_files() -> list:
    if not MIGRATIONS_DIR.exists():
        MIGRATIONS_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted([f for f in MIGRATIONS_DIR.glob("*.sql") if f.is_file()])
    return files


def cmd_status():
    conn = get_connection()
    applied = get_applied_migrations(conn)
    files = get_migration_files()

    print("\n" + "=" * 65)
    print("📋 ESTADO DE LAS MIGRACIONES")
    print("=" * 65)

    if not files:
        print("  (No hay archivos de migración en migrations/)")
    else:
        for f in files:
            version = f.name
            status = "✅ APLICADA" if version in applied else "⏳ PENDIENTE"
            print(f"  [{status}]  {version}")

    print("=" * 65 + "\n")
    conn.close()


def cmd_up():
    conn = get_connection()
    applied = get_applied_migrations(conn)
    files = get_migration_files()
    pending = [f for f in files if f.name not in applied]

    if not pending:
        print("\n✅ La base de datos ya está al día. No hay migraciones pendientes.\n")
        conn.close()
        return

    print(f"\n🚀 Aplicando {len(pending)} migración(es) pendiente(s)...\n")

    for f in pending:
        version = f.name
        print(f"  ▶️  Ejecutando: {version}...", end=" ", flush=True)
        sql = f.read_text(encoding="utf-8")

        try:
            with conn.cursor() as cur:
                cur.execute(sql)
                cur.execute(
                    "INSERT INTO public.schema_migrations (version) VALUES (%s);",
                    (version,)
                )
            conn.commit()
            print("OK ✅")
        except Exception as e:
            conn.rollback()
            print(f"FALLÓ ❌\n\nError al ejecutar {version}:\n{e}\n")
            conn.close()
            sys.exit(1)

    print("\n🎉 Todas las migraciones se aplicaron con éxito.\n")
    conn.close()


def cmd_create(name: str):
    if not MIGRATIONS_DIR.exists():
        MIGRATIONS_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = name.lower().replace(" ", "_").replace("-", "_")
    filename = f"{timestamp}_{safe_name}.sql"
    filepath = MIGRATIONS_DIR / filename

    content = f"""-- Migración: {filename}
-- Creada en: {datetime.now().isoformat()}

-- BEGIN TRANSACTION;

-- Escribe tus sentencias DDL / DML aquí:

"""
    filepath.write_text(content, encoding="utf-8")
    print(f"\n✨ Nueva migración creada: migrations/{filename}\n")


def main():
    parser = argparse.ArgumentParser(description="Gestor de migraciones SQL para IceBergTicket")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("status", help="Ver estado de las migraciones")
    subparsers.add_parser("up", help="Aplicar migraciones pendientes")
    create_parser = subparsers.add_parser("create", help="Crear nueva migración")
    create_parser.add_argument("name", help="Nombre descriptivo de la migración")

    args = parser.parse_args()

    if args.command == "status":
        cmd_status()
    elif args.command == "up":
        cmd_up()
    elif args.command == "create":
        cmd_create(args.name)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
