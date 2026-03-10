from src.models.DB import get_db


class SavedQueryModel:

    @staticmethod
    def create(file_id: int, user_id: int, name: str, query_json: dict) -> tuple:
        """Guarda una query. Devuelve (id, created_at)."""
        import json
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("""
            INSERT INTO saved_queries (file_id, name, query_json)
            VALUES (%s, %s, %s)
            RETURNING id, created_at
        """, (file_id, name, json.dumps({**query_json, "saved_by": user_id})))
        row = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        return row  # (id, created_at)

    @staticmethod
    def get_by_file(file_id: int) -> list:
        """Lista todas las queries guardadas de un archivo."""
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("""
            SELECT id, file_id, name, query_json, created_at, updated_at
            FROM saved_queries
            WHERE file_id = %s
            ORDER BY created_at DESC
        """, (file_id,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows

    @staticmethod
    def get_by_id(query_id: int, file_id: int):
        """Obtiene una query por id asegurando que pertenece al archivo."""
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("""
            SELECT id, file_id, name, query_json, created_at, updated_at
            FROM saved_queries
            WHERE id = %s AND file_id = %s
        """, (query_id, file_id))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row

    @staticmethod
    def update(query_id: int, file_id: int, name: str = None, query_json: dict = None) -> bool:
        """Actualiza nombre y/o query_json. Devuelve True si actualizó."""
        import json
        if name is None and query_json is None:
            return False
        conn = get_db()
        cur  = conn.cursor()
        if name is not None and query_json is not None:
            cur.execute("""
                UPDATE saved_queries
                SET name = %s, query_json = %s, updated_at = now()
                WHERE id = %s AND file_id = %s
                RETURNING id
            """, (name, json.dumps(query_json), query_id, file_id))
        elif name is not None:
            cur.execute("""
                UPDATE saved_queries
                SET name = %s, updated_at = now()
                WHERE id = %s AND file_id = %s
                RETURNING id
            """, (name, query_id, file_id))
        else:
            cur.execute("""
                UPDATE saved_queries
                SET query_json = %s, updated_at = now()
                WHERE id = %s AND file_id = %s
                RETURNING id
            """, (json.dumps(query_json), query_id, file_id))
        updated = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        return updated is not None

    @staticmethod
    def delete(query_id: int, file_id: int) -> bool:
        """Elimina una query. Devuelve True si la eliminó."""
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("""
            DELETE FROM saved_queries
            WHERE id = %s AND file_id = %s
            RETURNING id
        """, (query_id, file_id))
        deleted = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        return deleted is not None
