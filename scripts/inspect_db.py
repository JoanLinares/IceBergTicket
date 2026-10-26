#!/usr/bin/env python3
"""
inspect_db.py — Inspecciona la base de datos PostgreSQL/Supabase conectada mediante DATABASE_URL.
Analiza tablas, columnas, claves primarias, claves foráneas, índices y número de filas.
"""
import os
import sys
import json
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Cargar .env desde el directorio actual o el directorio padre
load_dotenv()
load_dotenv(Path(__file__).resolve().parents[1] / '.env')
load_dotenv(Path(__file__).resolve().parents[2] / '.env')

DATABASE_URL = os.getenv('DATABASE_URL')


def get_connection():
    if not DATABASE_URL:
        print("\n❌ Error: La variable de entorno DATABASE_URL no está definida.")
        print("Asegúrate de configurarla en el archivo .env:\n")
        print("DATABASE_URL=postgresql://postgres:[PASSWORD]@[HOST]:[PORT]/postgres\n")
        sys.exit(1)
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        print(f"\n❌ Error al conectar a PostgreSQL/Supabase: {e}\n")
        sys.exit(1)


def inspect_database():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    print("=" * 70)
    print("🔍 INSPECCIÓN DE LA BASE DE DATOS SUPABASE / POSTGRESQL")
    print("=" * 70)

    # 1. Información del servidor
    cur.execute("SELECT version();")
    v = cur.fetchone()
    print(f"\n📌 Versión del motor:\n   {v['version']}\n")

    # 2. Esquemas existentes
    cur.execute("""
        SELECT schema_name 
        FROM information_schema.schemata 
        WHERE schema_name NOT IN ('pg_catalog', 'information_schema')
          AND schema_name NOT LIKE 'pg_toast%'
          AND schema_name NOT LIKE 'pg_temp%'
        ORDER BY schema_name;
    """)
    schemas = [r['schema_name'] for r in cur.fetchall()]
    print(f"📁 Esquemas encontrados: {', '.join(schemas)}")

    # 3. Tablas por esquema
    for schema in schemas:
        cur.execute("""
            SELECT table_name, table_type
            FROM information_schema.tables
            WHERE table_schema = %s
            ORDER BY table_name;
        """, (schema,))
        tables = cur.fetchall()

        if not tables:
            continue

        print(f"\n" + "-" * 70)
        print(f"📂 Esquema: [{schema}] ({len(tables)} objetos)")
        print("-" * 70)

        for t in tables:
            tname = t['table_name']
            ttype = t['table_type']

            # Contar filas
            try:
                cur.execute(f'SELECT COUNT(*) AS total FROM "{schema}"."{tname}"')
                count = cur.fetchone()['total']
            except Exception:
                count = "N/A"

            print(f"\n🔹 {ttype}: {schema}.{tname}  (Filas: {count})")

            # Columnas
            cur.execute("""
                SELECT 
                    column_name, 
                    data_type, 
                    character_maximum_length,
                    is_nullable, 
                    column_default
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position;
            """, (schema, tname))
            cols = cur.fetchall()

            for c in cols:
                dtype = c['data_type']
                if c['character_maximum_length']:
                    dtype += f"({c['character_maximum_length']})"
                nullable = "NULL" if c['is_nullable'] == 'YES' else "NOT NULL"
                default = f" DEFAULT {c['column_default']}" if c['column_default'] else ""
                print(f"     • {c['column_name']:<22} {dtype:<18} {nullable:<9} {default}")

            # Primary Key & Foreign Keys
            cur.execute("""
                SELECT
                    tc.constraint_name, 
                    tc.constraint_type,
                    kcu.column_name,
                    ccu.table_name AS foreign_table_name,
                    ccu.column_name AS foreign_column_name 
                FROM information_schema.table_constraints AS tc 
                JOIN information_schema.key_column_usage AS kcu
                  ON tc.constraint_name = kcu.constraint_name
                  AND tc.table_schema = kcu.table_schema
                LEFT JOIN information_schema.constraint_column_usage AS ccu
                  ON ccu.constraint_name = tc.constraint_name
                  AND ccu.table_schema = tc.table_schema
                WHERE tc.table_schema = %s AND tc.table_name = %s
                ORDER BY tc.constraint_type, tc.constraint_name;
            """, (schema, tname))
            constraints = cur.fetchall()
            if constraints:
                print("     Restricciones:")
                for c in constraints:
                    if c['constraint_type'] == 'FOREIGN KEY':
                        print(f"       🔑 {c['constraint_type']} ({c['column_name']}) -> {c['foreign_table_name']}({c['foreign_column_name']})")
                    else:
                        print(f"       🔒 {c['constraint_type']} ({c['column_name']}) [{c['constraint_name']}]")

    print("\n" + "=" * 70)
    print("✅ Inspección finalizada.")
    print("=" * 70 + "\n")
    cur.close()
    conn.close()


if __name__ == '__main__':
    inspect_database()
