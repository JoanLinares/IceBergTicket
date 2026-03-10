from flask import Blueprint
from src.api.controllers.saved_query_controller import (
    list_saved_queries,
    get_saved_query,
    save_query,
    update_saved_query,
    delete_saved_query,
)

saved_query_routes = Blueprint("saved_query_routes", __name__)

saved_query_routes.route("/files/<int:file_id>/queries",              methods=["GET"])(list_saved_queries)
saved_query_routes.route("/files/<int:file_id>/queries",              methods=["POST"])(save_query)
saved_query_routes.route("/files/<int:file_id>/queries/<int:query_id>", methods=["GET"])(get_saved_query)
saved_query_routes.route("/files/<int:file_id>/queries/<int:query_id>", methods=["PATCH"])(update_saved_query)
saved_query_routes.route("/files/<int:file_id>/queries/<int:query_id>", methods=["DELETE"])(delete_saved_query)
