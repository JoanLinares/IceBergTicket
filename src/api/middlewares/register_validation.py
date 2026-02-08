from flask import request, jsonify
from functools import wraps
from src.services.hash_password_service import validate_password

def validate_register(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        data = request.get_json()

        username = data.get("username", "")
        email = data.get("email", "")
        password = data.get("password", "")
        confirm = data.get("confirm_password", "")

        if len(username) < 5:
            return jsonify({"error": "Username must be at least 5 characters"}), 400

        if "@" not in email:
            return jsonify({"error": "Invalid email"}), 400

        if password != confirm:
            return jsonify({"error": "Passwords do not match"}), 400

        ok, msg = validate_password(password)
        if not ok:
            return jsonify({"error": msg}), 400

        return fn(*args, **kwargs)
    return wrapper
