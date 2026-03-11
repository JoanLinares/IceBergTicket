from flask import request, jsonify, g

from src.api.middlewares.jwt_required import jwt_required
from src.services.db_session_service import DBSessionService
from src.api.models.file_model import FileModel
from src.api.models.saved_query_model import SavedQueryModel


@jwt_required
def list_tables(file_id: int):
    """
    GET /files/<file_id>/tables
    Lista todas las tablas y vistas del .db con su número de filas.

    Response 200:
        [{ "name": "fact_tickets", "type": "table", "row_count": 243 }, ...]
    """
    try:
        tables = DBSessionService.list_tables(file_id, g.user_id)
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 502

    return jsonify(tables), 200


@jwt_required
def get_table_data(file_id: int, table_name: str):
    """
    GET /files/<file_id>/tables/<table_name>?page=1&per_page=50
    Devuelve una página de datos de la tabla o vista indicada.

    Query params:
        page      int  (default 1)
        per_page  int  (default 50, max 200)

    Response 200:
        {
          "table": "fact_tickets",
          "columns": ["ticket_id", "date_key", ...],
          "rows": [{ "ticket_id": 1, ... }, ...],
          "total": 243,
          "page": 1,
          "per_page": 50,
          "total_pages": 5
        }
    """
    try:
        page     = max(1, int(request.args.get("page",     1)))
        per_page = max(1, int(request.args.get("per_page", 50)))
    except (TypeError, ValueError):
        return jsonify({"error": "Los parámetros page y per_page deben ser enteros"}), 400

    try:
        data = DBSessionService.get_table_data(file_id, g.user_id, table_name, page, per_page)
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 502

    return jsonify(data), 200


@jwt_required
def execute_query(file_id: int):
    """
    POST /files/<file_id>/query
    Ejecuta una query SQLite sobre el .db.

    Body (JSON):
        { "sql": "SELECT f.*, t.type_name FROM fact_tickets f JOIN dim_ticket_type t USING(type_key)" }

    Response 200:
        {
          "columns": ["ticket_id", "date_key", ...],
          "rows": [{ ... }, ...],
          "row_count": 12,
          "affected_rows": null,
          "is_write": false
        }

    Para queries de escritura (INSERT/UPDATE/DELETE/etc.) el .db se re-cifra
    y se re-sube automáticamente a Supabase Storage.
    """
    body = request.get_json(silent=True) or {}
    sql  = str(body.get("sql", "")).strip()
    save_name = body.get("save_as")   # opcional: nombre para guardar la query

    if not sql:
        return jsonify({"error": "El campo 'sql' es obligatorio"}), 400

    try:
        result = DBSessionService.execute_query(file_id, g.user_id, sql)
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 502

    # Guardar query si el cliente lo pidió
    if save_name:
        # Verificar acceso al archivo (ya comprobado en execute_query, pero necesitamos file_id)
        query_json = {
            "sql":            sql,
            "columns":        result["columns"],
            "result_preview": result["rows"][:5],
            "row_count":      result["row_count"],
            "is_write":       result["is_write"],
        }
        saved_id, saved_at = SavedQueryModel.create(file_id, g.user_id, save_name, query_json)
        result["saved_query_id"] = saved_id

    return jsonify(result), 200
