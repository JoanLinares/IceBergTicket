"""
Ingest API — permite a sistemas externos enviar tickets nuevos o actualizar estados
sin necesitar un JWT. La autenticación es mediante la api_key en la URL.

Endpoints:
  POST  /ingest/<file_id>/<api_key>/tickets          → añadir uno o varios tickets
  PATCH /ingest/<file_id>/<api_key>/tickets/<tid>/status → actualizar estado de un ticket
"""
import sqlite3

from datetime import datetime
from flask import request, jsonify
from werkzeug.security import check_password_hash

from src.api.models.file_model import FileModel
from src.services.file_service import FileService
from src.services.ml_service import MLService
from src.services.dw_service import (
    _upsert_date, _upsert_customer, _upsert_agent,
    _upsert_dim_text, _upsert_language, _insert_tags,
    _conn_to_bytes, decompress_db, compress_db_fast, _to_epoch, LANG_NAMES,
)

import os
import tempfile


def _authenticate(file_id: int, api_key: str):
    """
    Valida api_key contra el hash almacenado.
    Devuelve la fila del archivo o None si falla.
    """
    row = FileModel.get_api_password_hash(file_id)
    if not row:
        return None
    # row: id(0) owner_user_id(1) filename(2) api_password_hash(3)
    #      storage_path(4) enc_nonce(5) status(6)
    pw_hash = row[3]
    if not pw_hash or not check_password_hash(pw_hash, api_key):
        return None
    return row


def _open_db(file_row) -> tuple[sqlite3.Connection, str]:
    """Descarga, descifra y abre el .db. Devuelve (conn, tmp_path)."""
    storage_path = file_row[4]
    enc_nonce    = file_row[5]
    encrypted    = FileService.download_from_storage(storage_path)
    db_bytes     = decompress_db(FileService.decrypt(encrypted, enc_nonce))
    fd, tmp = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    with open(tmp, 'wb') as f:
        f.write(db_bytes)
    conn = sqlite3.connect(tmp, timeout=10)
    return conn, tmp


def _detect_level(filename: str) -> str:
    """Extrae el nivel (BASIC/MEDIUM/PRO) del nombre de fichero."""
    import re
    m = re.search(r'_(BASIC|MEDIUM|PRO)\.db$', filename or '', re.IGNORECASE)
    return m.group(1).upper() if m else 'BASIC'


def _save_back(conn: sqlite3.Connection, tmp: str, file_id: int):
    """Re-cifra el .db modificado y lo sube sobreescribiendo el original."""
    conn.commit()
    conn.close()
    with open(tmp, 'rb') as f:
        raw_bytes = f.read()
    new_bytes = compress_db_fast(raw_bytes)
    row = FileModel.get_api_password_hash(file_id)
    storage_path = row[4]
    up = FileService.upload_overwrite(new_bytes, storage_path)
    FileModel.update_encryption_meta(file_id, up['sha256'], up['enc_nonce'], up['size_bytes'])
    os.unlink(tmp)


# ──────────────────────────────────────────────────────────────────────
# POST /ingest/<file_id>/<api_key>/tickets
# ──────────────────────────────────────────────────────────────────────

def ingest_tickets(file_id: int, api_key: str):
    """
    Añade uno o varios tickets al .db sin necesitar JWT.
    Los tickets se clasifican automáticamente con ML (tipo e idioma).
    El nivel (BASIC/MEDIUM/PRO) viene determinado por el .db al que se ingesta.

    Body JSON:
        Un objeto único  { "subject": "...", "body": "...", "priority": "high", ... }
        O una lista      [{ ... }, { ... }]

    Response 201:
        { "inserted": 2, "ticket_ids": [101, 102] }
    """
    file_row = _authenticate(file_id, api_key)
    if not file_row:
        return jsonify({"error": "API key no válida o base de datos no encontrada"}), 401

    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "Se esperaba JSON en el body"}), 400

    tickets = body if isinstance(body, list) else [body]
    if not tickets:
        return jsonify({"error": "No se proporcionaron tickets"}), 400

    level = _detect_level(file_row[2])  # filename

    # Clasificar con ML para obtener pred_type y pred_language
    try:
        import pandas as pd
        df_in = pd.DataFrame(tickets)
        df_classified = MLService.get_instance().classify_dataframe(df_in)
    except Exception as exc:
        return jsonify({"error": f"Error en clasificación ML: {exc}"}), 500

    conn, tmp = _open_db(file_row)
    inserted_ids = []

    try:
        for _, row in df_classified.iterrows():
            pred_type = str(row.get('pred_type', ''))
            pred_lang = str(row.get('pred_language', ''))
            subj = str(row.get('subject', row.get('title', '')))
            body_text = str(row.get('body', row.get('description', row.get('message', ''))))
            email = str(row.get('email', row.get('submitter_email', row.get('customer_email', ''))))
            name  = str(row.get('name', row.get('submitter_name', row.get('customer_name', ''))))
            prio  = str(row.get('priority', row.get('prioridad', 'normal'))).lower()
            created_at_val = row.get('created_at', datetime.now().isoformat())
            created_ts = _to_epoch(created_at_val)
            agent = row.get('agent_name', row.get('assigned_to', None))

            date_key     = _upsert_date(conn, created_at_val)
            customer_key = _upsert_customer(conn, name, email)
            agent_key    = _upsert_agent(conn, agent)
            status_val   = 'open'
            prio_key     = _upsert_dim_text(conn, 'dim_priority', 'priority_name', 'priority_key', prio)
            status_key   = _upsert_dim_text(conn, 'dim_status',   'status_name',   'status_key',   status_val)

            if level == 'BASIC':
                conn.execute("""
                    INSERT INTO fact_tickets
                    (date_key, customer_key, agent_key, priority_key, status_key,
                     created_at, pred_type, pred_language)
                    VALUES (?,?,?,?,?,?,?,?)
                """, (date_key, customer_key, agent_key, prio_key, status_key,
                      created_ts, pred_type, pred_lang))
                tid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                conn.execute("INSERT INTO ticket_text VALUES (?,?,?)", (tid, subj, body_text))

            elif level == 'MEDIUM':
                type_key = _upsert_dim_text(conn, 'dim_type', 'type_name', 'type_key', pred_type)
                lang_key = _upsert_language(conn, pred_lang)
                conn.execute("""
                    INSERT INTO fact_tickets
                    (date_key, customer_key, agent_key, type_key, priority_key,
                     status_key, language_key, created_at)
                    VALUES (?,?,?,?,?,?,?,?)
                """, (date_key, customer_key, agent_key, type_key, prio_key,
                      status_key, lang_key, created_ts))
                tid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                conn.execute("INSERT INTO ticket_text VALUES (?,?,?)", (tid, subj, body_text))

            else:  # PRO
                type_key  = _upsert_dim_text(conn, 'dim_ticket_type', 'type_name', 'type_key', pred_type)
                lang_key  = _upsert_language(conn, pred_lang)
                queue_val = str(row.get('queue', row.get('department', 'general')))
                queue_key = _upsert_dim_text(conn, 'dim_queue', 'queue_name', 'queue_key', queue_val)
                conn.execute("""
                    INSERT INTO fact_tickets
                    (date_key, customer_key, agent_key, type_key, priority_key, queue_key,
                     language_key, status_key,
                     created_at, word_count_subject, word_count_body)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """, (date_key, customer_key, agent_key, type_key, prio_key, queue_key,
                      lang_key, status_key, created_ts,
                      len(subj.split()), len(body_text.split())))
                tid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                conn.execute("INSERT INTO ticket_text VALUES (?,?,?,?)",
                             (tid, subj, body_text, None))
                tag_cols = [c for c in df_classified.columns if c.startswith('tag_')]
                if tag_cols:
                    _insert_tags(conn, tid, tag_cols, row)

            inserted_ids.append(tid)

        _save_back(conn, tmp, file_id)

    except Exception as exc:
        conn.close()
        os.unlink(tmp)
        return jsonify({"error": f"Error insertando tickets: {exc}"}), 500

    return jsonify({"inserted": len(inserted_ids), "ticket_ids": inserted_ids}), 201


# ──────────────────────────────────────────────────────────────────────
# PATCH /ingest/<file_id>/<api_key>/tickets/<ticket_id>/status
# ──────────────────────────────────────────────────────────────────────

def update_ticket_status(file_id: int, api_key: str, ticket_id: int):
    """
    Actualiza el estado de un ticket en el .db.
    No requiere JWT — usa la api_key en la URL.

    Body JSON: { "status": "closed" }

    Response 200: { "ticket_id": 42, "status": "closed" }
    """
    file_row = _authenticate(file_id, api_key)
    if not file_row:
        return jsonify({"error": "API key no válida o base de datos no encontrada"}), 401

    body   = request.get_json(silent=True) or {}
    status = str(body.get("status", "")).strip().lower()
    if not status:
        return jsonify({"error": "El campo 'status' es obligatorio"}), 400

    conn, tmp = _open_db(file_row)
    try:
        # Upsert del status en dim_status (por si es nuevo)
        status_key = _upsert_dim_text(conn, 'dim_status', 'status_name', 'status_key', status)

        cur = conn.execute(
            "UPDATE fact_tickets SET status_key = ? WHERE ticket_id = ?",
            (status_key, ticket_id)
        )
        if cur.rowcount == 0:
            conn.close()
            os.unlink(tmp)
            return jsonify({"error": f"Ticket {ticket_id} no encontrado"}), 404

        _save_back(conn, tmp, file_id)

    except Exception as exc:
        conn.close()
        os.unlink(tmp)
        return jsonify({"error": f"Error actualizando estado: {exc}"}), 500

    return jsonify({"ticket_id": ticket_id, "status": status}), 200
