import os
import hashlib
import base64
import uuid
import requests

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

SUPABASE_URL    = os.getenv("SUPABASE_URL")
SUPABASE_KEY    = os.getenv("SUPABASE_SERVICE_KEY")   # service role key
STORAGE_BUCKET  = os.getenv("SUPABASE_STORAGE_BUCKET", "files")
MASTER_KEY_B64  = os.getenv("MASTER_KEY_V1")          # 32 bytes codificados en base64

MAX_FILE_SIZE   = 50 * 1024 * 1024  # 50 MB

_MIME_TYPES = {
    ".db":  "application/x-sqlite3",
    ".csv": "text/csv",
}


class FileService:

    @staticmethod
    def _get_master_key() -> bytes:
        if not MASTER_KEY_B64:
            raise RuntimeError("MASTER_KEY_V1 no está configurada en el entorno")
        key = base64.b64decode(MASTER_KEY_B64)
        if len(key) != 32:
            raise RuntimeError("MASTER_KEY_V1 debe ser exactamente 32 bytes (base64)")
        return key

    @staticmethod
    def upload(file_bytes: bytes, original_filename: str, user_id: int) -> dict:
        """
        Cifra el archivo con AES-256-GCM y lo sube a Supabase Storage.

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

        # Subir bytes cifrados a Supabase Storage
        FileService._upload_to_supabase(storage_path, encrypted)

        return {
            "filename":     original_filename,
            "file_type":    file_type,
            "storage_path": storage_path,
            "size_bytes":   size_bytes,
            "sha256":       sha256,
            "enc_nonce":    enc_nonce_b64,
        }

    @staticmethod
    def _upload_to_supabase(storage_path: str, data: bytes, upsert: bool = False):
        """POST de bytes al bucket de Supabase Storage."""
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError("SUPABASE_URL o SUPABASE_SERVICE_KEY no configurados")

        url = f"{SUPABASE_URL}/storage/v1/object/{STORAGE_BUCKET}/{storage_path}"
        headers = {
            "Authorization":  f"Bearer {SUPABASE_KEY}",
            "Content-Type":   "application/octet-stream",
            "x-upsert":       "true" if upsert else "false",
        }
        resp = requests.post(url, data=data, headers=headers, timeout=60)
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"Supabase Storage error {resp.status_code}: {resp.text}")

    @staticmethod
    def download_from_storage(storage_path: str) -> bytes:
        """Descarga el blob cifrado desde Supabase Storage y devuelve sus bytes."""
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError("SUPABASE_URL o SUPABASE_SERVICE_KEY no configurados")
        url = f"{SUPABASE_URL}/storage/v1/object/{STORAGE_BUCKET}/{storage_path}"
        headers = {"Authorization": f"Bearer {SUPABASE_KEY}"}
        resp = requests.get(url, headers=headers, timeout=60)
        if resp.status_code != 200:
            raise RuntimeError(f"Supabase Storage error {resp.status_code}: {resp.text}")
        return resp.content

    @staticmethod
    def decrypt(encrypted_bytes: bytes, nonce_b64: str) -> bytes:
        """Descifra bytes con AES-256-GCM usando el nonce en base64."""
        key   = FileService._get_master_key()
        nonce = base64.b64decode(nonce_b64)
        return AESGCM(key).decrypt(nonce, encrypted_bytes, None)

    @staticmethod
    def upload_overwrite(file_bytes: bytes, storage_path: str) -> dict:
        """
        Re-cifra file_bytes y sobreescribe el objeto existente en Supabase Storage.
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

        FileService._upload_to_supabase(storage_path, encrypted, upsert=True)

        return {
            "size_bytes": size_bytes,
            "sha256":     sha256,
            "enc_nonce":  enc_nonce_b64,
        }

    @staticmethod
    def delete_from_storage(storage_path: str):
        """Elimina un objeto del bucket de Supabase Storage."""
        if not SUPABASE_URL or not SUPABASE_KEY:
            return
        url = f"{SUPABASE_URL}/storage/v1/object/{STORAGE_BUCKET}/{storage_path}"
        headers = {"Authorization": f"Bearer {SUPABASE_KEY}"}
        requests.delete(url, headers=headers, timeout=30)
