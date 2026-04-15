import os
import re
import sys
import math
import sqlite3
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from flask import Flask, jsonify, render_template, request
from werkzeug.security import check_password_hash

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.api.models.file_model import FileModel
from src.services.file_service import FileService
from src.services.dw_service import decompress_db

app = Flask(__name__, template_folder="templates", static_folder="static")

DEFAULT_INGEST_BASE_URL = (
    "http://127.0.0.1:5000/api/v1/ingest/16/8ij3niXyWclUPlWlcpsVW4llq1331pRtuJY7cN0j830"
)
READ_TIMEOUT = 20
WRITE_TIMEOUT = 180
_INGEST_PATH_RE = re.compile(r"/api/v1/ingest/(?P<file_id>\d+)/(?P<api_key>[^/]+)$")


def _normalize_ingest_base(url: str) -> str:
    value = (url or "").strip().rstrip("/")
    if value.endswith("/tickets"):
        value = value[: -len("/tickets")]
    return value


def _ingest_base_url() -> str:
    return _normalize_ingest_base(
        os.getenv("TESTWEB_INGEST_BASE_URL", DEFAULT_INGEST_BASE_URL)
    )


def _extract_file_auth() -> tuple:
    parsed = urlparse(_ingest_base_url())
    path = parsed.path.rstrip("/")
    match = _INGEST_PATH_RE.search(path)
    if not match:
        raise ValueError(
            "TESTWEB_INGEST_BASE_URL debe terminar en /api/v1/ingest/<file_id>/<api_key>"
        )
    return int(match.group("file_id")), match.group("api_key")


def _authenticate_with_api_key() -> tuple:
    file_id, api_key = _extract_file_auth()
    row = FileModel.get_api_password_hash(file_id)
    if not row:
        raise PermissionError("Base de datos no encontrada")
    pw_hash = row[3]
    if not pw_hash or not check_password_hash(pw_hash, api_key):
        raise PermissionError("API key no valida para ese file_id")
    return row


def _open_decrypted_db(file_row) -> tuple:
    storage_path = file_row[4]
    enc_nonce = file_row[5]
    encrypted = FileService.download_from_storage(storage_path)
    db_bytes = decompress_db(FileService.decrypt(encrypted, enc_nonce))

    fd, tmp = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    with open(tmp, "wb") as fh:
        fh.write(db_bytes)
    conn = sqlite3.connect(tmp, timeout=10)
    return conn, tmp


def _list_tickets_page(page: int, per_page: int) -> dict:
    file_row = _authenticate_with_api_key()
    conn, tmp = _open_decrypted_db(file_row)
    try:
        total = conn.execute("SELECT COUNT(*) FROM fact_tickets").fetchone()[0]
        offset = (page - 1) * per_page

        text_cols = {
            r[1] for r in conn.execute("PRAGMA table_info(ticket_text)").fetchall()
        }
        answer_select = "tt.answer" if "answer" in text_cols else "NULL"

        rows = conn.execute(f"""
            SELECT f.ticket_id,
                   COALESCE(tt.subject, ''),
                   COALESCE(s.status_name, 'open'),
                   {answer_select} AS response_text,
                   COALESCE(f.created_at, 0)
            FROM fact_tickets f
            LEFT JOIN ticket_text tt ON tt.ticket_id = f.ticket_id
            LEFT JOIN dim_status s ON s.status_key = f.status_key
            ORDER BY f.ticket_id DESC
            LIMIT ? OFFSET ?
        """, (per_page, offset)).fetchall()

        resolved_statuses = {"resolved", "closed"}
        tickets = []
        for ticket_id, subject, status_name, response_text, created_at in rows:
            status_norm = str(status_name or "open").strip().lower()
            answer_text = (response_text or "").strip()
            is_resolved = status_norm in resolved_statuses
            responded = bool(answer_text) or is_resolved

            if answer_text:
                response_name = answer_text[:120]
            elif is_resolved:
                response_name = "Resuelto (sin texto de respuesta)"
            else:
                response_name = "Sin respuesta"

            tickets.append({
                "ticket_id": ticket_id,
                "subject": subject,
                "status": status_norm,
                "response_name": response_name,
                "responded": responded,
                "created_at": int(created_at) if created_at is not None else 0,
            })

        total_pages = math.ceil(total / per_page) if total > 0 else 1
        return {
            "tickets": tickets,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
        }
    finally:
        conn.close()
        os.unlink(tmp)


def _proxy_request(
    method: str,
    path: str,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], int]:
    url = f"{_ingest_base_url()}{path}"
    timeout = WRITE_TIMEOUT if method.upper() in {"POST", "PATCH"} else READ_TIMEOUT
    try:
        response = requests.request(
            method=method,
            url=url,
            json=json_body,
            params=params,
            timeout=timeout,
        )
    except requests.Timeout:
        return {
            "error": (
                "La API de ingest tardó demasiado en responder. "
                "El alta usa los modelos ML para clasificar el ticket y luego reescribe la base de datos; "
                "en la primera petición puede tardar bastante."
            )
        }, 504
    except requests.RequestException as exc:
        return {"error": f"No se pudo conectar con la API ingest: {exc}"}, 502

    try:
        payload = response.json()
    except ValueError:
        payload = {"error": response.text or f"Respuesta no JSON ({response.status_code})"}

    return payload, response.status_code


@app.get("/")
def index():
    return render_template("index.html", ingest_base_url=_ingest_base_url())


@app.get("/api/config")
def config():
    return jsonify({"ingest_base_url": _ingest_base_url()})


@app.get("/api/tickets")
def list_tickets_proxy():
    try:
        page = max(1, int(request.args.get("page", "1")))
        per_page = max(1, min(100, int(request.args.get("per_page", "10"))))
    except (TypeError, ValueError):
        return jsonify({"error": "page y per_page deben ser enteros"}), 400

    try:
        payload = _list_tickets_page(page, per_page)
        return jsonify(payload), 200
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 401
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"Error listando tickets: {exc}"}), 500


@app.post("/api/tickets")
def create_ticket_proxy():
    body = request.get_json(silent=True) or {}
    email = str(body.get("email", "")).strip()
    message = str(body.get("message", "")).strip()

    if not email or not message:
        return jsonify({"error": "Los campos email y message son obligatorios"}), 400

    default_name = email.split("@", 1)[0] if "@" in email else email

    payload, status = _proxy_request(
        method="POST",
        path="/tickets",
        json_body={
            "email": email,
            "name": default_name or "User",
            "body": message,
            "priority": "normal",
        },
    )
    return jsonify(payload), status


@app.patch("/api/tickets/<int:ticket_id>/status")
def update_status_proxy(ticket_id: int):
    body = request.get_json(silent=True) or {}
    status_value = str(body.get("status", "resolved")).strip().lower() or "resolved"

    payload, status = _proxy_request(
        method="PATCH",
        path=f"/tickets/{ticket_id}/status",
        json_body={"status": status_value},
    )
    return jsonify(payload), status


if __name__ == "__main__":
    port = int(os.getenv("TESTWEB_PORT", "5055"))
    app.run(host="127.0.0.1", port=port, debug=True)
