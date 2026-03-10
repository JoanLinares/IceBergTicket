from flask import Blueprint
from src.api.controllers.file_controller import (
    upload_file,
    list_files,
    get_file,
    delete_file,
    generate_share_code,
    join_database,
)

file_routes = Blueprint("file_routes", __name__)

file_routes.route("/files/upload",            methods=["POST"])(upload_file)
file_routes.route("/files/join",              methods=["POST"])(join_database)
file_routes.route("/files",                   methods=["GET"])(list_files)
file_routes.route("/files/<int:file_id>",     methods=["GET"])(get_file)
file_routes.route("/files/<int:file_id>",     methods=["DELETE"])(delete_file)
file_routes.route("/files/<int:file_id>/share", methods=["POST"])(generate_share_code)
