from src.models.DB import get_db


class FileModel:

    @staticmethod
    def create(owner_user_id, filename, file_type, storage_path,
               size_bytes, sha256, enc_nonce, api_password_hash=None):
        """Inserta un registro en public.files y devuelve (id, created_at)."""
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO files
                (owner_user_id, filename, file_type, storage_path,
                 size_bytes, sha256, enc_nonce, api_password_hash)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, created_at
        """, (owner_user_id, filename, file_type, storage_path,
               size_bytes, sha256, enc_nonce, api_password_hash))
        row = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        return row  # (id, created_at)

    @staticmethod
    def get_by_owner(user_id):
        """Lista todos los archivos de un usuario ordenados por fecha desc."""
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, filename, file_type, size_bytes, sha256,
                   status, created_at, is_encrypted, enc_version
            FROM files
            WHERE owner_user_id = %s
            ORDER BY created_at DESC
        """, (user_id,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows

    @staticmethod
    def get_by_id(file_id):
        """Obtiene un archivo por id (incluye campos de cifrado)."""
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, owner_user_id, filename, file_type, storage_path,
                   size_bytes, sha256, status, created_at,
                   is_encrypted, enc_version, enc_nonce, key_ref
            FROM files
            WHERE id = %s
        """, (file_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row

    @staticmethod
    def delete(file_id, owner_user_id):
        """Elimina un archivo solo si pertenece al usuario. Devuelve el id eliminado o None."""
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            DELETE FROM files
            WHERE id = %s AND owner_user_id = %s
            RETURNING id
        """, (file_id, owner_user_id))
        row = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        return row

    @staticmethod
    def get_accessible_by_user(user_id):
        """Archivos propios + compartidos con info de acceso."""
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT f.id, f.filename, f.file_type, f.size_bytes, f.status,
                   f.created_at, uf.is_owner, uf.invited_at, f.share_code
            FROM user_files uf
            JOIN files f ON f.id = uf.file_id
            WHERE uf.user_id = %s
            ORDER BY f.created_at DESC
        """, (user_id,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows

    @staticmethod
    def check_user_access(file_id: int, user_id: int):
        """Devuelve fila del archivo + is_owner si el usuario tiene acceso, o None."""
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT f.id, f.filename, f.file_type, f.size_bytes, f.status,
                   f.created_at, f.is_encrypted, f.enc_version,
                   f.share_code, uf.is_owner
            FROM files f
            JOIN user_files uf ON uf.file_id = f.id
            WHERE f.id = %s AND uf.user_id = %s
        """, (file_id, user_id))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row

    @staticmethod
    def get_share_code(file_id: int, owner_user_id: int):
        """Devuelve el share_code actual del archivo (solo propietario)."""
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT share_code FROM files WHERE id = %s AND owner_user_id = %s",
            (file_id, owner_user_id)
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row[0] if row else None

    @staticmethod
    def set_share_code(file_id: int, owner_user_id: int, code: str) -> bool:
        """Guarda o actualiza el share_code (solo propietario)."""
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            UPDATE files SET share_code = %s
            WHERE id = %s AND owner_user_id = %s
            RETURNING id
        """, (code, file_id, owner_user_id))
        updated = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        return updated is not None

    @staticmethod
    def get_by_share_code(code: str):
        """Busca un archivo por share_code. Devuelve (id, owner_user_id, filename, status) o None."""
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, owner_user_id, filename, status FROM files WHERE share_code = %s",
            (code.strip().upper(),)
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row

    @staticmethod
    def get_full_with_access(file_id: int, user_id: int):
        """
        Devuelve el registro completo del archivo + is_owner si el usuario tiene acceso.
        Índices: id(0) owner_user_id(1) filename(2) file_type(3) storage_path(4)
                 size_bytes(5) sha256(6) status(7) created_at(8)
                 is_encrypted(9) enc_version(10) enc_nonce(11) is_owner(12)
        """
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT f.id, f.owner_user_id, f.filename, f.file_type, f.storage_path,
                   f.size_bytes, f.sha256, f.status, f.created_at,
                   f.is_encrypted, f.enc_version, f.enc_nonce,
                   uf.is_owner
            FROM files f
            JOIN user_files uf ON uf.file_id = f.id
            WHERE f.id = %s AND uf.user_id = %s
        """, (file_id, user_id))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row

    @staticmethod
    def update_encryption_meta(file_id: int, sha256: str, enc_nonce: str, size_bytes: int):
        """Actualiza sha256, enc_nonce y size_bytes tras un re-cifrado (escritura + re-subida)."""
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            UPDATE files SET sha256 = %s, enc_nonce = %s, size_bytes = %s
            WHERE id = %s
        """, (sha256, enc_nonce, size_bytes, file_id))
        conn.commit()
        cur.close()
        conn.close()

    @staticmethod
    def set_api_password_hash(file_id: int, owner_user_id: int, pw_hash: str) -> bool:
        """Almacena o regenera el hash de la API key (solo propietario)."""
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("""
            UPDATE files SET api_password_hash = %s
            WHERE id = %s AND owner_user_id = %s
            RETURNING id
        """, (pw_hash, file_id, owner_user_id))
        updated = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        return updated is not None

    @staticmethod
    def get_api_password_hash(file_id: int):
        """
        Devuelve (id, owner_user_id, filename, api_password_hash, storage_path, enc_nonce)
        sin requerir autenticación JWT (usado por el endpoint de ingest).
        """
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("""
            SELECT id, owner_user_id, filename, api_password_hash,
                   storage_path, enc_nonce, status
            FROM files
            WHERE id = %s
        """, (file_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row


class UserFileModel:

    @staticmethod
    def create(user_id, file_id, is_owner=True, invited_by=None):
        """Vincula un usuario con un archivo en user_files."""
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO user_files (user_id, file_id, is_owner, invited_by)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_id, file_id) DO NOTHING
        """, (user_id, file_id, is_owner, invited_by))
        conn.commit()
        cur.close()
        conn.close()

    @staticmethod
    def get_files_for_user(user_id):
        """Devuelve todos los file_id accesibles para un usuario (propios + compartidos)."""
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT uf.file_id, uf.is_owner, uf.invited_at,
                   f.filename, f.file_type, f.size_bytes, f.status, f.created_at
            FROM user_files uf
            JOIN files f ON f.id = uf.file_id
            WHERE uf.user_id = %s
            ORDER BY f.created_at DESC
        """, (user_id,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
