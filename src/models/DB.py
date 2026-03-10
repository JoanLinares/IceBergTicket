import psycopg2
import os


def get_db():
    url = os.getenv('DATABASE_URL')
    if not url:
        raise RuntimeError('DATABASE_URL no está configurada en el entorno')
    return psycopg2.connect(url)
