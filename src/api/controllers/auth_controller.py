from flask import request, jsonify

from src.services.auth_service import AuthService
from src.api.middlewares.register_validation import validate_register
from src.services.JWT_service import (
    create_access_token,
    create_refresh_token,
    hash_refresh_token
)
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
