import os
import re
import sys
import math
import sqlite3
import tempfile
from datetime import datetime, timezone
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

RESOLVED_STATUSES = {"resolved", "closed"}
SORTABLE_FIELDS = {
    "id": "ticket_id",
    "ticket_id": "ticket_id",
    "created_at": "created_at",
    "date": "created_at",
    "status": "status_name",
    "type": "ticket_type",
    "subject": "subject",
    "responded": "responded",
    "email": "email",
    "user": "customer_name",
}


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


def _parse_date(value: str | None, end_of_day: bool = False) -> int | None:
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        try:
            dt = datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            return None
    if end_of_day and dt.hour == 0 and dt.minute == 0 and dt.second == 0:
        dt = dt.replace(hour=23, minute=59, second=59)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row is not None


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not _table_exists(conn, table):
        return set()
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _list_tickets_page(
    page: int,
    per_page: int,
    *,
    q: str | None = None,
    ticket_type: str | None = None,
    user: str | None = None,
    statuses: list[str] | None = None,
    responded: str | None = None,
    date_from: int | None = None,
    date_to: int | None = None,
    sort: str = "created_at",
    order: str = "desc",
) -> dict:
    file_row = _authenticate_with_api_key()
    conn, tmp = _open_decrypted_db(file_row)
    try:
        text_cols = _columns(conn, "ticket_text")
        fact_cols = _columns(conn, "fact_tickets")
        cust_cols = _columns(conn, "dim_customer")
        has_customer = bool(cust_cols)
        has_priority = "priority_key" in fact_cols and _table_exists(conn, "dim_priority")
        has_type_key = "type_key" in fact_cols
        has_dim_ticket_type = has_type_key and _table_exists(conn, "dim_ticket_type")
        has_dim_type = has_type_key and _table_exists(conn, "dim_type")
        has_pred_type = "pred_type" in fact_cols

        answer_expr = "tt.answer" if "answer" in text_cols else "NULL"
        desc_expr = "tt.description" if "description" in text_cols else "NULL"
        email_expr = "c.email" if has_customer else "NULL"
        name_expr = "c.customer_name" if has_customer else "NULL"
        priority_expr = "p.priority_name" if has_priority else "NULL"

        if has_dim_ticket_type:
            type_expr = "dtt.type_name"
        elif has_dim_type:
            type_expr = "dt.type_name"
        elif has_pred_type:
            type_expr = "f.pred_type"
        else:
            type_expr = "NULL"

        customer_join = (
            "LEFT JOIN dim_customer c ON c.customer_key = f.customer_key"
            if has_customer else ""
        )
        priority_join = (
            "LEFT JOIN dim_priority p ON p.priority_key = f.priority_key"
            if has_priority else ""
        )
        type_join = (
            "LEFT JOIN dim_ticket_type dtt ON dtt.type_key = f.type_key"
            if has_dim_ticket_type else (
                "LEFT JOIN dim_type dt ON dt.type_key = f.type_key"
                if has_dim_type else ""
            )
        )

        base_cte = f"""
            WITH base AS (
                SELECT
                    f.ticket_id                                       AS ticket_id,
                    COALESCE(tt.subject, '')                          AS subject,
                    COALESCE({desc_expr}, '')                         AS description,
                    LOWER(COALESCE(s.status_name, 'open'))            AS status_name,
                    LOWER(COALESCE(NULLIF(TRIM({type_expr}), ''), '')) AS ticket_type,
                    {answer_expr}                                     AS response_text,
                    COALESCE(f.created_at, 0)                         AS created_at,
                    COALESCE({email_expr}, '')                        AS email,
                    COALESCE({name_expr}, '')                         AS customer_name,
                    {priority_expr}                                   AS priority_name,
                    CASE
                        WHEN LOWER(COALESCE(s.status_name, 'open')) IN ('resolved','closed') THEN 1
                        WHEN TRIM(COALESCE({answer_expr}, '')) != ''                         THEN 1
                        ELSE 0
                    END                                               AS responded
                FROM fact_tickets f
                LEFT JOIN ticket_text tt ON tt.ticket_id = f.ticket_id
                LEFT JOIN dim_status s   ON s.status_key = f.status_key
                {type_join}
                {customer_join}
                {priority_join}
            )
        """

        where: list[str] = []
        params: list[Any] = []

        if q:
            like = f"%{q.strip().lower()}%"
            parts = [
                "LOWER(subject) LIKE ?",
                "LOWER(description) LIKE ?",
                "LOWER(COALESCE(response_text, '')) LIKE ?",
                "LOWER(ticket_type) LIKE ?",
                "LOWER(email) LIKE ?",
                "LOWER(customer_name) LIKE ?",
                "CAST(ticket_id AS TEXT) LIKE ?",
            ]
            where.append("(" + " OR ".join(parts) + ")")
            params.extend([like] * len(parts))

        if ticket_type:
            where.append("ticket_type = ?")
            params.append(ticket_type.strip().lower())

        if user:
            where.append("(LOWER(email) LIKE ? OR LOWER(customer_name) LIKE ?)")
            like = f"%{user.strip().lower()}%"
            params.extend([like, like])

        if statuses:
            placeholders = ",".join(["?"] * len(statuses))
            where.append(f"status_name IN ({placeholders})")
            params.extend([s.lower() for s in statuses])

        if responded == "yes":
            where.append("responded = 1")
        elif responded == "no":
            where.append("responded = 0")

        if date_from is not None:
            where.append("created_at >= ?")
            params.append(date_from)
        if date_to is not None:
            where.append("created_at <= ?")
            params.append(date_to)

        where_sql = " AND ".join(where) if where else "1=1"

        sort_col = SORTABLE_FIELDS.get((sort or "").lower(), "ticket_id")
        order_dir = "ASC" if str(order).lower() == "asc" else "DESC"

        total = conn.execute(
            base_cte + f"SELECT COUNT(*) FROM base WHERE {where_sql}",
            params,
        ).fetchone()[0]

        total_pages = max(1, math.ceil(total / per_page)) if total > 0 else 1
        page = min(page, total_pages)
        offset = (page - 1) * per_page

        rows = conn.execute(
            base_cte + f"""
                SELECT ticket_id, subject, status_name, response_text, created_at,
                       email, customer_name, priority_name, ticket_type, responded
                FROM base
                WHERE {where_sql}
                ORDER BY {sort_col} {order_dir}, ticket_id DESC
                LIMIT ? OFFSET ?
            """,
            params + [per_page, offset],
        ).fetchall()

        tickets = []
        for (ticket_id, subj, status_name, response_text, created_at,
             email, customer_name, priority_name, type_name, responded_flag) in rows:
            answer_text = (response_text or "").strip()
            status_norm = str(status_name or "open").strip().lower()
            is_resolved = status_norm in RESOLVED_STATUSES
            if answer_text:
                response_name = answer_text[:180]
            elif is_resolved:
                response_name = "Resuelto sin texto de respuesta"
            else:
                response_name = "Sin respuesta"
            tickets.append({
                "ticket_id": ticket_id,
                "subject": subj,
                "status": status_norm,
                "response_name": response_name,
                "responded": bool(responded_flag),
                "created_at": int(created_at) if created_at else 0,
                "email": email or "",
                "customer_name": customer_name or "",
                "type": (type_name or "").strip().lower() or None,
                "priority": (priority_name or "").strip().lower() or None,
            })

        available_statuses: list[str] = []
        if _table_exists(conn, "dim_status"):
            try:
                rows_s = conn.execute(
                    "SELECT DISTINCT LOWER(COALESCE(status_name,'open')) "
                    "FROM dim_status ORDER BY status_name"
                ).fetchall()
                available_statuses = [r[0] for r in rows_s if r[0]]
            except sqlite3.DatabaseError:
                available_statuses = []

        available_types: list[str] = []
        if type_expr != "NULL":
            try:
                rows_t = conn.execute(
                    base_cte + "SELECT DISTINCT ticket_type FROM base "
                    "WHERE ticket_type != '' ORDER BY ticket_type"
                ).fetchall()
                available_types = [r[0] for r in rows_t if r[0]]
            except sqlite3.DatabaseError:
                available_types = []

        return {
            "tickets": tickets,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
            "facets": {
                "statuses": available_statuses,
                "types": available_types,
            },
            "capabilities": {
                "has_customer": has_customer,
                "has_priority": has_priority,
                "has_answer": answer_expr != "NULL",
                "has_type": type_expr != "NULL",
            },
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

    q = (request.args.get("q") or "").strip() or None
    ticket_type = (
        request.args.get("type")
        or request.args.get("subject")
        or ""
    ).strip() or None
    user = (request.args.get("user") or "").strip() or None

    status_raw = (request.args.get("status") or "").strip()
    statuses = [s.strip().lower() for s in status_raw.split(",") if s.strip()] or None

    responded_raw = (request.args.get("responded") or "").strip().lower()
    responded = responded_raw if responded_raw in {"yes", "no"} else None

    date_from = _parse_date(request.args.get("date_from"))
    date_to = _parse_date(request.args.get("date_to"), end_of_day=True)

    sort = (request.args.get("sort") or "created_at").strip().lower()
    order = (request.args.get("order") or "desc").strip().lower()

    try:
        payload = _list_tickets_page(
            page, per_page,
            q=q, ticket_type=ticket_type, user=user,
            statuses=statuses, responded=responded,
            date_from=date_from, date_to=date_to,
            sort=sort, order=order,
        )
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
