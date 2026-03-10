from flask import Blueprint
from src.api.controllers.ingest_controller import ingest_tickets, update_ticket_status

ingest_routes = Blueprint("ingest_routes", __name__)

ingest_routes.route(
    "/ingest/<int:file_id>/<string:api_key>/tickets",
    methods=["POST"]
)(ingest_tickets)

ingest_routes.route(
    "/ingest/<int:file_id>/<string:api_key>/tickets/<int:ticket_id>/status",
    methods=["PATCH"]
)(update_ticket_status)
