from flask import request, jsonify, g

from src.api.middlewares.jwt_required import jwt_required
from src.api.models.file_model import FileModel
from src.api.models.saved_query_model import SavedQueryModel


def _check_file_access(file_id: int, user_id: int):
    """Devuelve la fila de acceso o None."""
    return FileModel.check_user_access(file_id, user_id)


@jwt_required
def list_saved_queries(file_id: int):
    """
    GET /files/<file_id>/queries
    Lista todas las queries guardadas del archivo.

    Response 200:
        [{ "id", "name", "query_json", "created_at", "updated_at" }]
    """
    if not _check_file_access(file_id, g.user_id):
        return jsonify({"error": "Base de datos no encontrada o sin acceso"}), 404

    rows = SavedQueryModel.get_by_file(file_id)
    # row: id(0) file_id(1) name(2) query_json(3) created_at(4) updated_at(5)
    result = [
        {
            "id":         r[0],
            "name":       r[2],
            "query_json": r[3],
            "created_at": r[4].isoformat(),
            "updated_at": r[5].isoformat(),
        }
        for r in rows
    ]
    return jsonify(result), 200


@jwt_required
def get_saved_query(file_id: int, query_id: int):
    """
    GET /files/<file_id>/queries/<query_id>
    Devuelve el detalle de una query guardada.
    """
    if not _check_file_access(file_id, g.user_id):
        return jsonify({"error": "Base de datos no encontrada o sin acceso"}), 404

    row = SavedQueryModel.get_by_id(query_id, file_id)
    if not row:
        return jsonify({"error": "Query no encontrada"}), 404

    return jsonify({
        "id":         row[0],
        "file_id":    row[1],
        "name":       row[2],
        "query_json": row[3],
        "created_at": row[4].isoformat(),
        "updated_at": row[5].isoformat(),
    }), 200


@jwt_required
def save_query(file_id: int):
    """
    POST /files/<file_id>/queries
    Guarda una query manualmente (sin ejecutarla).

    Body: { "name": "Tickets de alta prioridad", "sql": "SELECT * FROM fact_tickets WHERE ..." }
    """
    if not _check_file_access(file_id, g.user_id):
        return jsonify({"error": "Base de datos no encontrada o sin acceso"}), 404

    body = request.get_json(silent=True) or {}
    name = str(body.get("name", "")).strip()
    sql  = str(body.get("sql", "")).strip()

    if not name:
        return jsonify({"error": "El campo 'name' es obligatorio"}), 400
    if not sql:
        return jsonify({"error": "El campo 'sql' es obligatorio"}), 400

    query_json = {"sql": sql}
    query_id, created_at = SavedQueryModel.create(file_id, g.user_id, name, query_json)

    return jsonify({
        "id":         query_id,
        "file_id":    file_id,
        "name":       name,
        "query_json": query_json,
        "created_at": created_at.isoformat(),
    }), 201


@jwt_required
def update_saved_query(file_id: int, query_id: int):
    """
    PATCH /files/<file_id>/queries/<query_id>
    Actualiza el nombre o la SQL de una query guardada.

    Body (cualquier combinación): { "name": "...", "sql": "..." }
    """
    if not _check_file_access(file_id, g.user_id):
        return jsonify({"error": "Base de datos no encontrada o sin acceso"}), 404

    row = SavedQueryModel.get_by_id(query_id, file_id)
    if not row:
        return jsonify({"error": "Query no encontrada"}), 404

    body = request.get_json(silent=True) or {}
    name = body.get("name")
    sql  = body.get("sql")

    if name is None and sql is None:
        return jsonify({"error": "Proporciona al menos 'name' o 'sql'"}), 400

    # Construir query_json actualizado
    existing_qj = row[3] if isinstance(row[3], dict) else {}
    new_qj = {**existing_qj, **({"sql": sql} if sql is not None else {})}

    updated = SavedQueryModel.update(
        query_id, file_id,
        name=name,
        query_json=new_qj if sql is not None else None,
    )
    if not updated:
        return jsonify({"error": "No se pudo actualizar la query"}), 500

    return jsonify({"message": "Query actualizada", "id": query_id}), 200


@jwt_required
def delete_saved_query(file_id: int, query_id: int):
    """
    DELETE /files/<file_id>/queries/<query_id>
    Elimina una query guardada.
    """
    if not _check_file_access(file_id, g.user_id):
        return jsonify({"error": "Base de datos no encontrada o sin acceso"}), 404

    deleted = SavedQueryModel.delete(query_id, file_id)
    if not deleted:
        return jsonify({"error": "Query no encontrada"}), 404

    return jsonify({"message": "Query eliminada"}), 200
