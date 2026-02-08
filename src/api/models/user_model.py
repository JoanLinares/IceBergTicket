from src.models.db import get_db

class UserModel:

    @staticmethod
    def get_by_email(email):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE email=%s", (email,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        return user

    @staticmethod
    def create(username, email, password_hash):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO users (name, email, password_hash)
            VALUES (%s, %s, %s)
            RETURNING id
        """, (username, email, password_hash))
        user_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return user_id
