from flask import Blueprint
from .auth_routes import auth_routes
from .file_routes import file_routes
from .db_routes import db_routes
from .saved_query_routes import saved_query_routes
from .ingest_routes import ingest_routes

api_blueprint = Blueprint("api", __name__)
api_blueprint.register_blueprint(auth_routes)
api_blueprint.register_blueprint(file_routes)
api_blueprint.register_blueprint(db_routes)
api_blueprint.register_blueprint(saved_query_routes)
api_blueprint.register_blueprint(ingest_routes)
api_blueprint.register_blueprint(file_routes)
