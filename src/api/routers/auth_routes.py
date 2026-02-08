from flask import Blueprint
from src.api.controllers.auth_controller import register

auth_routes = Blueprint("auth_routes", __name__)
auth_routes.route("/auth/register", methods=["POST"])(register)
