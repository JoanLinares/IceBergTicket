import os
import hashlib
import base64
import uuid
import psycopg2

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

def _env(name, default=None):
    """Read env var lazily so load_dotenv() always takes effect."""
    return os.getenv(name, default)




MAX_FILE_SIZE   = 50 * 1024 * 1024  # 50 MB

_MIME_TYPES = {
    ".db":  "application/x-sqlite3",
    ".csv": "text/csv",
}


class FileService:

    @staticmethod
    def _get_database_url() -> str:
        url = _env("DATABASE_URL")
        if not url:
            raise RuntimeError("DATABASE_URL no está configurada en el entorno")
        return url

    @staticmethod
    def _ensure_blob_table(conn):
        """Creates blob table if needed for encrypted payload storage."""
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS public.file_storage_blobs (
                    storage_path TEXT PRIMARY KEY,
                    encrypted_blob BYTEA NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)

    @staticmethod
    def _get_master_key() -> bytes:
        val = _env("MASTER_KEY_V1")
        if not val:
            raise RuntimeError("MASTER_KEY_V1 no está configurada en el entorno")
        key = base64.b64decode(val)
        if len(key) != 32:
            raise RuntimeError("MASTER_KEY_V1 debe ser exactamente 32 bytes (base64)")
        return key

    @staticmethod
    def upload(file_bytes: bytes, original_filename: str, user_id: int) -> dict:
        """
        Cifra el archivo con AES-256-GCM y lo guarda en PostgreSQL (BYTEA)
        usando DATABASE_URL.

        Returns:
            dict con filename, file_type, storage_path, size_bytes, sha256, enc_nonce
            listo para insertar en public.files.
        """
        if len(file_bytes) > MAX_FILE_SIZE:
            raise ValueError(f"El archivo supera el tamaño máximo ({MAX_FILE_SIZE // (1024*1024)} MB)")

        # SHA-256 del archivo ORIGINAL (antes de cifrar)
        sha256 = hashlib.sha256(file_bytes).hexdigest()
        size_bytes = len(file_bytes)

        # Cifrado AES-256-GCM
        key    = FileService._get_master_key()
        nonce  = os.urandom(12)          # 96 bits — estándar para GCM
        aesgcm = AESGCM(key)
        encrypted = aesgcm.encrypt(nonce, file_bytes, None)   # None = sin AAD

        enc_nonce_b64 = base64.b64encode(nonce).decode()

        # Path en el bucket:  users/{user_id}/{uuid}<ext>.enc
        ext = os.path.splitext(original_filename)[1] or ".bin"
        storage_path = f"users/{user_id}/{uuid.uuid4().hex}{ext}.enc"
        file_type    = _MIME_TYPES.get(ext.lower(), "application/octet-stream")

        # Persistir bytes cifrados en PostgreSQL
        FileService._upload_to_storage(storage_path, encrypted)

        return {
            "filename":     original_filename,
            "file_type":    file_type,
            "storage_path": storage_path,
            "size_bytes":   size_bytes,
            "sha256":       sha256,
            "enc_nonce":    enc_nonce_b64,
        }

    @staticmethod
    def _upload_to_storage(storage_path: str, data: bytes, upsert: bool = False):
        """Guarda bytes cifrados en PostgreSQL (tabla public.file_storage_blobs)."""
        db_url = FileService._get_database_url()
        if not db_url:
            raise RuntimeError("DATABASE_URL no configurada")

        with psycopg2.connect(db_url) as conn:
            FileService._ensure_blob_table(conn)
            with conn.cursor() as cur:
                if upsert:
                    cur.execute(
                        """
                        INSERT INTO public.file_storage_blobs (storage_path, encrypted_blob)
                        VALUES (%s, %s)
                        ON CONFLICT (storage_path)
                        DO UPDATE SET encrypted_blob = EXCLUDED.encrypted_blob,
                                      updated_at = NOW()
                        """,
                        (storage_path, psycopg2.Binary(data)),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO public.file_storage_blobs (storage_path, encrypted_blob)
                        VALUES (%s, %s)
                        """,
                        (storage_path, psycopg2.Binary(data)),
                    )

    @staticmethod
    def download_from_storage(storage_path: str) -> bytes:
        """Recupera el blob cifrado desde PostgreSQL y devuelve sus bytes."""
        db_url = FileService._get_database_url()
        if not db_url:
            raise RuntimeError("DATABASE_URL no configurada")

        with psycopg2.connect(db_url) as conn:
            FileService._ensure_blob_table(conn)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT encrypted_blob FROM public.file_storage_blobs WHERE storage_path = %s",
                    (storage_path,),
                )
                row = cur.fetchone()

        if not row:
            raise RuntimeError(f"Blob no encontrado en PostgreSQL: {storage_path}")
        return bytes(row[0])

    @staticmethod
    def decrypt(encrypted_bytes: bytes, nonce_b64: str) -> bytes:
        """Descifra bytes con AES-256-GCM usando el nonce en base64."""
        key   = FileService._get_master_key()
        nonce = base64.b64decode(nonce_b64)
        return AESGCM(key).decrypt(nonce, encrypted_bytes, None)

    @staticmethod
    def upload_overwrite(file_bytes: bytes, storage_path: str) -> dict:
        """
        Re-cifra file_bytes y sobreescribe el blob existente en PostgreSQL.
        Returns dict con size_bytes, sha256, enc_nonce.
        """
        if len(file_bytes) > MAX_FILE_SIZE:
            raise ValueError(f"El archivo supera el tamaño máximo ({MAX_FILE_SIZE // (1024*1024)} MB)")

        sha256     = hashlib.sha256(file_bytes).hexdigest()
        size_bytes = len(file_bytes)

        key       = FileService._get_master_key()
        nonce     = os.urandom(12)
        encrypted = AESGCM(key).encrypt(nonce, file_bytes, None)
        enc_nonce_b64 = base64.b64encode(nonce).decode()

        FileService._upload_to_storage(storage_path, encrypted, upsert=True)

        return {
            "size_bytes": size_bytes,
            "sha256":     sha256,
            "enc_nonce":  enc_nonce_b64,
        }

    @staticmethod
    def delete_from_storage(storage_path: str):
        """Elimina un blob cifrado de PostgreSQL."""
        db_url = FileService._get_database_url()
        if not db_url:
            return

        with psycopg2.connect(db_url) as conn:
            FileService._ensure_blob_table(conn)
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM public.file_storage_blobs WHERE storage_path = %s",
                    (storage_path,),
                )
