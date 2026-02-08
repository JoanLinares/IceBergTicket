from flask import request, jsonify

from src.services.auth_service import AuthService
from src.api.middlewares.register_validation import validate_register
from src.services.JWT_service import (
    create_access_token,
    create_refresh_token,
    hash_refresh_token,
    JWT_SECRET
)
import jwt
from src.api.models.user_model import UserModel


@validate_register
def register():
    data = request.get_json()

    user_id, error = AuthService.register(
        data["username"],
        data["email"],
        data["password"]
    )

    if error:
        return jsonify({"error": error}), 400

    # Crear tokens igual que en login
    access_token = create_access_token(user_id)

    refresh_token = create_refresh_token()
    refresh_hash = hash_refresh_token(refresh_token)
    UserModel.set_refresh_token(user_id, refresh_hash)

    return jsonify({
        "message": "User registered",
        "access_token": access_token,
        "refresh_token": refresh_token
    }), 201


def login():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    result, error = AuthService.login(
        data.get("email"),
        data.get("password")
    )

    if error:
        return jsonify({"error": error}), 401

    return jsonify(result), 200


def refresh():
    data = request.get_json()

    if not data or "refresh_token" not in data:
        return jsonify({"error": "Refresh token required"}), 400

    refresh_token = data["refresh_token"]
    refresh_hash = hash_refresh_token(refresh_token)

    user = UserModel.get_by_refresh_hash(refresh_hash)
    if not user:
        return jsonify({"error": "Invalid refresh token"}), 401

    user_id = user[0]

    # Rotación del refresh token
    new_refresh = create_refresh_token()
    new_refresh_hash = hash_refresh_token(new_refresh)
    UserModel.set_refresh_token(user_id, new_refresh_hash)

    access_token = create_access_token(user_id)

    return jsonify({
        "access_token": access_token,
        "refresh_token": new_refresh
    }), 200

def logout():
    # Espera un header Authorization: Bearer <access_token>
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"error": "Authorization header required"}), 401

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return jsonify({"error": "Invalid authorization header format"}), 400

    token = parts[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Access token expired"}), 401
    except jwt.InvalidTokenError as e:
        print(f"DEBUG JWT: secret='{JWT_SECRET}', error={e}")
        return jsonify({"error": "Invalid access token"}), 401

    user_id = payload.get("user_id")
    if not user_id:
        return jsonify({"error": "Invalid token payload"}), 400

    UserModel.clear_refresh_token(user_id)
    return jsonify({"message": "Logged out successfully"}), 200

