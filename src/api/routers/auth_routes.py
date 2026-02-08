from flask import Blueprint
from src.api.controllers.auth_controller import (
    register,
    login,
    refresh,
    logout
)

auth_routes = Blueprint("auth_routes", __name__)

auth_routes.route("/auth/register", methods=["POST"])(register)
auth_routes.route("/auth/login", methods=["POST"])(login)
auth_routes.route("/auth/refresh", methods=["POST"])(refresh)
auth_routes.route("/auth/logout", methods=["POST"])(logout)
