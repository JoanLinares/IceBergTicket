from flask import Blueprint
from src.api.controllers.db_controller import list_tables, get_table_data, execute_query

db_routes = Blueprint("db_routes", __name__)

db_routes.route("/files/<int:file_id>/tables",                    methods=["GET"])(list_tables)
db_routes.route("/files/<int:file_id>/tables/<string:table_name>", methods=["GET"])(get_table_data)
db_routes.route("/files/<int:file_id>/query",                     methods=["POST"])(execute_query)
