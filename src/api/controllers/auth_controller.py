from flask import request, jsonify
from src.services.auth_service import AuthService
from src.services.jwt_service import create_token
from src.api.middlewares.register_validation import validate_register

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

    token = create_token(user_id)
    return jsonify({
        "message": "User registered",
        "token": token
    }), 201
