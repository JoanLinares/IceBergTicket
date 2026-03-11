import re
import secrets

from flask import request, jsonify, g
from werkzeug.security import generate_password_hash

from src.api.middlewares.jwt_required import jwt_required
from src.api.models.file_model import FileModel, UserFileModel
from src.services.file_service import FileService
from src.services.ml_service import MLService
from src.services.dw_service import DWService


def _ext(filename: str) -> str:
    return "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def _extract_level(filename: str) -> str | None:
    """Extrae el nivel DW del nombre de archivo: base_LEVEL.db → 'LEVEL'."""
    m = re.search(r'_(BASIC|MEDIUM|PRO)\.db$', filename or '', re.IGNORECASE)
    return m.group(1).upper() if m else None


@jwt_required
def upload_file():
    """
    POST /files/upload
    multipart/form-data  →  campo "file" con el CSV de tickets

    Flujo:
      1. Valida que sea un CSV
      2. Clasifica cada ticket con los modelos ML (tipo, idioma, nivel DW)
      3. Determina el nivel óptimo (BASIC / MEDIUM / PRO) para todo el dataset
      4. Crea UN solo SQLite .db con el esquema óptimo y TODOS los tickets
      5. Cifra el .db con AES-256-GCM y lo sube a Supabase Storage
      6. Registra el .db en public.files y public.user_files
      7. Devuelve un resumen con el archivo creado
    """
    if "file" not in request.files:
        return jsonify({"error": "No se encontró el campo 'file' en la petición"}), 400

    f = request.files["file"]

    if not f.filename:
        return jsonify({"error": "Nombre de archivo vacío"}), 400

    if _ext(f.filename) != ".csv":
        return jsonify({"error": "Solo se admiten archivos CSV"}), 400

    csv_bytes = f.read()
    if not csv_bytes:
        return jsonify({"error": "El archivo está vacío"}), 400

    # ── Paso 2: clasificar con ML ──────────────────────────────────────
    try:
        df = MLService.get_instance().classify_csv(csv_bytes)
    except Exception as exc:
        return jsonify({"error": f"Error en clasificación ML: {exc}"}), 500

    # ── Paso 3: crear .db con el nivel óptimo ─────────────────────────
    try:
        db_files = DWService.create_databases(df)
    except Exception as exc:
        return jsonify({"error": f"Error creando bases de datos: {exc}"}), 500

    if not db_files:
        return jsonify({"error": "No se generó ninguna base de datos (CSV sin tickets válidos)"}), 422

    # ── Pasos 4-6: cifrar, subir y registrar el .db ──────────────────
    base_name = f.filename.rsplit(".", 1)[0]
    created = []

    for level, db_bytes in db_files.items():
        filename  = f"{base_name}_{level}.db"
        n_tickets = len(df)

        try:
            meta = FileService.upload(db_bytes, filename, g.user_id)
        except ValueError as exc:
            return jsonify({"error": f"Archivo demasiado grande ({level}): {exc}"}), 400
        except RuntimeError as exc:
            return jsonify({"error": f"Error subiendo {level}: {exc}"}), 502

        # Generar API key — se devuelve en texto plano solo esta vez
        plain_api_key = secrets.token_urlsafe(32)
        api_pw_hash   = generate_password_hash(plain_api_key)

        file_id, created_at = FileModel.create(
            owner_user_id=g.user_id,
            filename=meta["filename"],
            file_type=meta["file_type"],
            storage_path=meta["storage_path"],
            size_bytes=meta["size_bytes"],
            sha256=meta["sha256"],
            enc_nonce=meta["enc_nonce"],
            api_password_hash=api_pw_hash,
        )
        UserFileModel.create(user_id=g.user_id, file_id=file_id, is_owner=True)

        created.append({
            "id":           file_id,
            "filename":     filename,
            "level":        level,
            "n_tickets":    n_tickets,
            "size_bytes":   meta["size_bytes"],
            "sha256":       meta["sha256"],
            "is_encrypted": True,
            "enc_version":  "aes-256-gcm-v1",
            "created_at":   created_at.isoformat(),
            "api_key":      plain_api_key,
            "ingest_url":   f"/api/v1/ingest/{file_id}/{plain_api_key}",
        })

    return jsonify(created), 201


@jwt_required
def list_files():
    """
    GET /files
    Devuelve todas las bases de datos accesibles por el usuario (propias + compartidas).
    Respuesta: [{ id, filename, level, file_type, size_bytes, status, created_at, is_owner }]
    """
    rows = FileModel.get_accessible_by_user(g.user_id)
    # r: id(0) filename(1) file_type(2) size_bytes(3) status(4)
    #    created_at(5) is_owner(6) invited_at(7) share_code(8)
    files = [
        {
            "id":           r[0],
            "filename":     r[1],
            "level":        _extract_level(r[1]),
            "file_type":    r[2],
            "size_bytes":   r[3],
            "status":       r[4],
            "created_at":   r[5].isoformat(),
            "is_owner":     r[6],
            "invited_at":   r[7].isoformat() if r[7] else None,
        }
        for r in rows
    ]
    return jsonify(files), 200


@jwt_required
def get_file(file_id: int):
    """
    GET /files/<file_id>
    Devuelve los detalles de una base de datos si el usuario tiene acceso.
    """
    row = FileModel.check_user_access(file_id, g.user_id)
    if not row:
        return jsonify({"error": "Base de datos no encontrada o sin acceso"}), 404
    # row: id(0) filename(1) file_type(2) size_bytes(3) status(4)
    #      created_at(5) is_encrypted(6) enc_version(7) share_code(8) is_owner(9)
    return jsonify({
        "id":           row[0],
        "filename":     row[1],
        "level":        _extract_level(row[1]),
        "file_type":    row[2],
        "size_bytes":   row[3],
        "status":       row[4],
        "created_at":   row[5].isoformat(),
        "is_encrypted": row[6],
        "enc_version":  row[7],
        "has_share_code": row[8] is not None,
        "is_owner":     row[9],
    }), 200


@jwt_required
def generate_share_code(file_id: int):
    """
    POST /files/<file_id>/share
    Genera (o devuelve el existente) share_code para la base de datos.
    Solo el propietario puede hacerlo.
    Body opcional: { "regenerate": true } para forzar un código nuevo.
    """
    # Verificar que el usuario es propietario
    row = FileModel.check_user_access(file_id, g.user_id)
    if not row:
        return jsonify({"error": "Base de datos no encontrada"}), 404
    if not row[9]:  # is_owner
        return jsonify({"error": "Solo el propietario puede generar códigos de compartir"}), 403

    data       = request.get_json(silent=True) or {}
    regenerate = bool(data.get("regenerate", False))

    existing = row[8]  # share_code
    if existing and not regenerate:
        return jsonify({"share_code": existing, "file_id": file_id}), 200

    # Generar código de 8 caracteres alfanuméricos en mayúsculas
    code = secrets.token_hex(4).upper()
    ok   = FileModel.set_share_code(file_id, g.user_id, code)
    if not ok:
        return jsonify({"error": "No se pudo guardar el código"}), 500

    return jsonify({"share_code": code, "file_id": file_id}), 200


@jwt_required
def join_database():
    """
    POST /files/join
    Body: { "share_code": "A3F9B2C1" }
    Vincula al usuario autenticado con la base de datos del código.
    """
    data = request.get_json(silent=True) or {}
    code = str(data.get("share_code", "")).strip().upper()
    if not code:
        return jsonify({"error": "El campo 'share_code' es obligatorio"}), 400

    file_row = FileModel.get_by_share_code(code)
    if not file_row:
        return jsonify({"error": "Código de compartir no válido o caducado"}), 404

    file_id, owner_user_id, filename, status = file_row

    if owner_user_id == g.user_id:
        return jsonify({"error": "Ya eres el propietario de esta base de datos"}), 409

    # Comprobar si ya tiene acceso
    existing = FileModel.check_user_access(file_id, g.user_id)
    if existing:
        return jsonify({"error": "Ya tienes acceso a esta base de datos"}), 409

    UserFileModel.create(
        user_id=g.user_id,
        file_id=file_id,
        is_owner=False,
        invited_by=owner_user_id,
    )

    return jsonify({
        "message":  "Te has unido correctamente a la base de datos",
        "file_id":  file_id,
        "filename": filename,
        "level":    _extract_level(filename),
    }), 200


@jwt_required
def regenerate_api_key(file_id: int):
    """
    POST /files/<file_id>/api-key
    Regenera la API key de ingest (solo propietario).
    La clave anterior queda invalidada inmediatamente.
    Devuelve la nueva clave en texto plano UNA SOLA VEZ.
    """
    row = FileModel.check_user_access(file_id, g.user_id)
    if not row:
        return jsonify({"error": "Base de datos no encontrada"}), 404
    if not row[9]:  # is_owner
        return jsonify({"error": "Solo el propietario puede regenerar la API key"}), 403

    plain_key = secrets.token_urlsafe(32)
    pw_hash   = generate_password_hash(plain_key)

    ok = FileModel.set_api_password_hash(file_id, g.user_id, pw_hash)
    if not ok:
        return jsonify({"error": "No se pudo actualizar la API key"}), 500

    return jsonify({
        "file_id":    file_id,
        "api_key":    plain_key,
        "ingest_url": f"/api/v1/ingest/{file_id}/{plain_key}",
        "warning":    "Guarda esta clave, no se volverá a mostrar.",
    }), 200


@jwt_required
def delete_file(file_id: int):
    """
    DELETE /files/<file_id>
    Elimina el archivo del storage y de la BD (solo el propietario puede hacerlo).
    """
    row = FileModel.get_by_id(file_id)
    if not row:
        return jsonify({"error": "Archivo no encontrado"}), 404

    owner_user_id = row[1]
    if owner_user_id != g.user_id:
        return jsonify({"error": "No tienes permiso para eliminar este archivo"}), 403

    storage_path = row[4]

    deleted = FileModel.delete(file_id, g.user_id)
    if not deleted:
        return jsonify({"error": "No se pudo eliminar el archivo"}), 500

    FileService.delete_from_storage(storage_path)

    return jsonify({"message": "Archivo eliminado correctamente"}), 200
