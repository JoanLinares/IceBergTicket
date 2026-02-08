from werkzeug.security import check_password_hash

from src.api.models.user_model import UserModel
from src.services.hash_password_service import hash_password
from src.services.JWT_service import (
    create_access_token,
    create_refresh_token,
    hash_refresh_token
)


class AuthService:

    @staticmethod
    def register(username, email, password):
        # Comprobar si el email ya existe
        if UserModel.get_by_email(email):
            return None, "Email already registered"

        # Hash de la password
        password_hash = hash_password(password)

        # Crear usuario
        user_id = UserModel.create(username, email, password_hash)

        return user_id, None

    @staticmethod
    def login(email, password):
        # Obtener usuario con password
        user = UserModel.get_by_email_full(email)
        if not user:
            return None, "Invalid credentials"

        user_id, password_hash = user

        # Verificar password
        if not check_password_hash(password_hash, password):
            return None, "Invalid credentials"

        # Crear tokens
        access_token = create_access_token(user_id)

        refresh_token = create_refresh_token()
        refresh_hash = hash_refresh_token(refresh_token)

        # Guardar refresh token (invalida el anterior)
        UserModel.set_refresh_token(user_id, refresh_hash)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token
        }, None
