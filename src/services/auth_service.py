from src.api.models.user_model import UserModel
from src.services.hash_password_service import hash_password

class AuthService:

    @staticmethod
    def register(username, email, password):
        if UserModel.get_by_email(email):
            return None, "Email already registered"

        password_hash = hash_password(password)
        user_id = UserModel.create(username, email, password_hash)
        return user_id, None
