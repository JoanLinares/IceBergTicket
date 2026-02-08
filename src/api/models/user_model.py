from src.models.DB import get_db

class UserModel:

    @staticmethod
    def get_by_email_full(email):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, password_hash
            FROM users
            WHERE email=%s
        """, (email,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row

    @staticmethod
    def set_refresh_token(user_id, refresh_hash):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            UPDATE users
            SET refresh_token_hash=%s
            WHERE id=%s
        """, (refresh_hash, user_id))
        conn.commit()
        cur.close()
        conn.close()

    @staticmethod
    def get_by_refresh_hash(refresh_hash):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT id
            FROM users
            WHERE refresh_token_hash=%s
        """, (refresh_hash,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row

    @staticmethod
    def clear_refresh_token(user_id):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            UPDATE users
            SET refresh_token_hash=NULL
            WHERE id=%s
        """, (user_id,))
        conn.commit()
        cur.close()
        conn.close()
