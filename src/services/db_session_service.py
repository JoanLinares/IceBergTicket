"""
DBSessionService — Descarga, descifra y opera sobre una BD SQLite almacenada en Supabase.

Operaciones:
  - list_tables(file_id, user_id)                        → lista de tablas + n.º de filas
  - get_table_data(file_id, user_id, table, page, pp)    → página de filas + columnas + total
  - execute_query(file_id, user_id, sql)                 → columnas + filas + rowcount
     Si la query es de escritura → re-cifra y re-sube automáticamente.

Seguridad:
  - ATTACH / DETACH bloqueados (acceso al sistema de ficheros del servidor).
  - El nombre de tabla se valida contra un patrón seguro.
  - El resultado de SELECT se limita a 1 000 filas.
  - La query tiene un timeout de 10 s.
  - El fichero temporal se borra siempre en el bloque finally.
"""
import os
import re
import sqlite3
import tempfile

from src.api.models.file_model import FileModel
from src.services.file_service import FileService

# ──────────────────────────────────────────────────────────────────────
# Clasificación de queries
# ──────────────────────────────────────────────────────────────────────

_WRITE_KEYWORDS = frozenset([
    'INSERT', 'UPDATE', 'DELETE', 'REPLACE', 'UPSERT',
    'CREATE', 'DROP', 'ALTER', 'RENAME',
])

_BLOCKED = re.compile(r'^\s*(ATTACH|DETACH)\b', re.IGNORECASE)

_TABLE_NAME_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_ ]*$')

MAX_SELECT_ROWS = 1_000
MAX_PER_PAGE    = 200


def _first_keyword(sql: str) -> str:
    """Primera palabra clave real (ignora comentarios)."""
    clean = re.sub(r'--[^\n]*', '', sql)
    clean = re.sub(r'/\*.*?\*/', '', clean, flags=re.DOTALL)
    parts = clean.strip().split()
    return parts[0].upper() if parts else ''


def _is_write(sql: str) -> bool:
    return _first_keyword(sql) in _WRITE_KEYWORDS


# ──────────────────────────────────────────────────────────────────────
# Helpers internos
# ──────────────────────────────────────────────────────────────────────

def _fetch_db(file_id: int, user_id: int) -> tuple[bytes, dict]:
    """
    Descarga y descifra el .db. Devuelve (db_bytes, meta_dict).
    meta_dict keys: file_id, storage_path, enc_nonce, is_owner
    """
    row = FileModel.get_full_with_access(file_id, user_id)
    if not row:
        raise PermissionError("Base de datos no encontrada o sin acceso")
    # row: id(0) owner_user_id(1) filename(2) file_type(3) storage_path(4)
    #      size_bytes(5) sha256(6) status(7) created_at(8)
    #      is_encrypted(9) enc_version(10) enc_nonce(11) is_owner(12)
    storage_path = row[4]
    enc_nonce    = row[11]
    is_owner     = row[12]

    if not enc_nonce:
        raise RuntimeError("El archivo no tiene metadatos de cifrado")

    encrypted = FileService.download_from_storage(storage_path)
    db_bytes  = FileService.decrypt(encrypted, enc_nonce)

    return db_bytes, {
        'file_id':      row[0],
        'storage_path': storage_path,
        'enc_nonce':    enc_nonce,
        'is_owner':     is_owner,
    }


def _write_tmp(db_bytes: bytes) -> str:
    """Escribe los bytes del .db a un fichero temporal y devuelve su ruta."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    with open(path, 'wb') as f:
        f.write(db_bytes)
    return path


# ──────────────────────────────────────────────────────────────────────
# API pública
# ──────────────────────────────────────────────────────────────────────

class DBSessionService:

    @staticmethod
    def list_tables(file_id: int, user_id: int) -> list[dict]:
        """
        Lista todas las tablas y vistas del .db con su número de filas.

        Returns:
            [{ name, type, row_count }]
        """
        db_bytes, _ = _fetch_db(file_id, user_id)
        tmp = _write_tmp(db_bytes)
        try:
            conn = sqlite3.connect(tmp, timeout=10)
            cur  = conn.cursor()
            cur.execute("""
                SELECT name, type
                FROM sqlite_master
                WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%'
                ORDER BY type DESC, name ASC
            """)
            entries = cur.fetchall()
            tables  = []
            for name, ttype in entries:
                count = conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
                tables.append({'name': name, 'type': ttype, 'row_count': count})
            conn.close()
        finally:
            os.unlink(tmp)

        return tables

    @staticmethod
    def get_table_data(
        file_id: int,
        user_id: int,
        table_name: str,
        page: int = 1,
        per_page: int = 50,
    ) -> dict:
        """
        Devuelve una página de datos de una tabla o vista.

        Returns:
            { table, columns, rows, total, page, per_page, total_pages }
        """
        if not _TABLE_NAME_RE.match(table_name):
            raise ValueError("Nombre de tabla no válido")

        per_page = min(max(1, per_page), MAX_PER_PAGE)
        page     = max(1, page)

        db_bytes, _ = _fetch_db(file_id, user_id)
        tmp = _write_tmp(db_bytes)
        try:
            conn             = sqlite3.connect(tmp, timeout=10)
            conn.row_factory = sqlite3.Row

            # Validar que la tabla existe
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type IN ('table','view') AND name=?",
                (table_name,)
            ).fetchone()
            if not exists:
                conn.close()
                raise ValueError(f"Tabla '{table_name}' no encontrada")

            total  = conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]
            offset = (page - 1) * per_page
            cur    = conn.execute(
                f'SELECT * FROM "{table_name}" LIMIT ? OFFSET ?',
                (per_page, offset)
            )
            columns = [d[0] for d in cur.description] if cur.description else []
            rows    = [dict(r) for r in cur.fetchall()]
            conn.close()
        finally:
            os.unlink(tmp)

        return {
            'table':       table_name,
            'columns':     columns,
            'rows':        rows,
            'total':       total,
            'page':        page,
            'per_page':    per_page,
            'total_pages': max(1, -(-total // per_page)),
        }

    @staticmethod
    def execute_query(file_id: int, user_id: int, sql: str) -> dict:
        """
        Ejecuta una query SQLite arbitraria.

        - SELECT → devuelve columnas + filas (máx. 1 000).
        - Escritura (INSERT/UPDATE/DELETE/CREATE/DROP/ALTER) →
            ejecuta, hace commit, re-cifra el .db y lo re-sube a Supabase.
        - ATTACH / DETACH → bloqueados por seguridad.

        Returns:
            { columns, rows, row_count, affected_rows, is_write }
        """
        sql = sql.strip()
        if not sql:
            raise ValueError("La query no puede estar vacía")

        if _BLOCKED.search(sql):
            raise PermissionError("ATTACH y DETACH están bloqueados por seguridad")

        write = _is_write(sql)

        db_bytes, meta = _fetch_db(file_id, user_id)
        tmp = _write_tmp(db_bytes)
        try:
            conn             = sqlite3.connect(tmp, timeout=10)
            conn.row_factory = sqlite3.Row
            try:
                cur = conn.execute(sql)
                if write:
                    conn.commit()
                if cur.description:
                    columns      = [d[0] for d in cur.description]
                    rows         = [dict(r) for r in cur.fetchmany(MAX_SELECT_ROWS)]
                    affected     = None
                else:
                    columns      = []
                    rows         = []
                    affected     = cur.rowcount
            except sqlite3.Error as exc:
                conn.close()
                raise ValueError(f"Error SQLite: {exc}") from exc
            conn.close()

            # Re-cifrar y re-subir si la query modificó datos
            if write:
                with open(tmp, 'rb') as f:
                    new_bytes = f.read()
                up = FileService.upload_overwrite(new_bytes, meta['storage_path'])
                FileModel.update_encryption_meta(
                    file_id,
                    sha256=up['sha256'],
                    enc_nonce=up['enc_nonce'],
                    size_bytes=up['size_bytes'],
                )
        finally:
            os.unlink(tmp)

        return {
            'columns':       columns,
            'rows':          rows,
            'row_count':     len(rows) if rows else 0,
            'affected_rows': affected,
            'is_write':      write,
        }
