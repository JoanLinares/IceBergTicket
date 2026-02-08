import jwt
import datetime
import os

SECRET = os.getenv("JWT_SECRET", "dev_secret")

def create_token(user_id):
    payload = {
        "user_id": user_id,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")
