"""
MinioService — Cliente para almacenamiento de objetos en MinIO local (API compatible con Amazon S3).
Utiliza boto3 para interactuar con el contenedor de MinIO sin dependencias externas ni servicios cloud.
"""
import os
import io
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError


class MinioService:
    _client = None

    @classmethod
    def get_client(cls):
        """Inicializa y devuelve el cliente S3 para MinIO local."""
        if cls._client is None:
            endpoint = os.getenv("MINIO_ENDPOINT", "minio:9000")
            # Soporta formato host:puerto o http://host:puerto
            if not endpoint.startswith("http://") and not endpoint.startswith("https://"):
                protocol = "https" if os.getenv("MINIO_USE_SSL", "false").lower() == "true" else "http"
                endpoint_url = f"{protocol}://{endpoint}"
            else:
                endpoint_url = endpoint

            access_key = os.getenv("MINIO_ROOT_USER", "minioadmin")
            secret_key = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")

            cls._client = boto3.client(
                "s3",
                endpoint_url=endpoint_url,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                config=Config(signature_version="s3v4"),
                region_name="us-east-1",
            )
        return cls._client

    @classmethod
    def get_default_bucket(cls) -> str:
        return os.getenv("MINIO_BUCKET", "iceberg-tickets")

    @classmethod
    def ensure_bucket(cls, bucket_name: str = None):
        """Verifica que el bucket exista en MinIO; si no, lo crea."""
        bucket = bucket_name or cls.get_default_bucket()
        client = cls.get_client()
        try:
            client.head_bucket(Bucket=bucket)
        except ClientError:
            try:
                client.create_bucket(Bucket=bucket)
            except ClientError as e:
                # Si ya existe (condición de carrera), ignorar
                if e.response["Error"]["Code"] not in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
                    raise

    @classmethod
    def upload_file(cls, file_bytes: bytes, object_name: str, bucket_name: str = None, content_type: str = "application/octet-stream") -> dict:
        """
        Sube un archivo a MinIO local.
        
        Args:
            file_bytes: Contenido binario del archivo.
            object_name: Ruta del objeto en el bucket (ej. 'datasets/users/1/tickets.csv').
            bucket_name: Nombre del bucket (opcional, usa el predeterminado).
            content_type: Tipo MIME del archivo.
            
        Returns:
            dict con bucket, object_name y tamaño en bytes.
        """
        bucket = bucket_name or cls.get_default_bucket()
        cls.ensure_bucket(bucket)
        client = cls.get_client()

        client.upload_fileobj(
            Fileobj=io.BytesIO(file_bytes),
            Bucket=bucket,
            Key=object_name,
            ExtraArgs={"ContentType": content_type},
        )

        return {
            "bucket": bucket,
            "object_name": object_name,
            "size_bytes": len(file_bytes),
        }

    @classmethod
    def download_file(cls, object_name: str, bucket_name: str = None) -> bytes:
        """Descarga un objeto de MinIO y devuelve sus bytes."""
        bucket = bucket_name or cls.get_default_bucket()
        client = cls.get_client()
        buf = io.BytesIO()
        client.download_fileobj(Bucket=bucket, Key=object_name, Fileobj=buf)
        buf.seek(0)
        return buf.read()

    @classmethod
    def delete_file(cls, object_name: str, bucket_name: str = None) -> bool:
        """Elimina un objeto de MinIO."""
        bucket = bucket_name or cls.get_default_bucket()
        client = cls.get_client()
        try:
            client.delete_object(Bucket=bucket, Key=object_name)
            return True
        except ClientError:
            return False

    @classmethod
    def generate_presigned_url(cls, object_name: str, bucket_name: str = None, expires_in: int = 3600) -> str:
        """Genera una URL temporal presignada para descargar el archivo directamente."""
        bucket = bucket_name or cls.get_default_bucket()
        client = cls.get_client()
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": object_name},
            ExpiresIn=expires_in,
        )
