from flask import Blueprint
from .auth_routes import auth_routes

api_blueprint = Blueprint("api", __name__)
api_blueprint.register_blueprint(auth_routes)
