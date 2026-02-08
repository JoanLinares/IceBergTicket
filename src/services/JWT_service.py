import jwt
import datetime
import os
import hashlib
import secrets

JWT_SECRET = os.getenv("JWT_SECRET", "dev_secret")

ACCESS_TOKEN_HOURS = 24

SECRET = os.getenv("JWT_SECRET", "dev_secret")

def create_token(user_id):
    payload = {
        "user_id": user_id,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")

def create_refresh_token() -> str:
    # token largo, aleatorio, no guessable
    return secrets.token_urlsafe(64)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
