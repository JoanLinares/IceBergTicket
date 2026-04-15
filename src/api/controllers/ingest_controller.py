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
import re
import unicodedata


CANONICAL_TICKET_TYPES = [
    'Estrategia y Análisis',
    'Hardware y Red',
    'Otros',
    'Seguridad y Privacidad',
    'Error de Sistema / Rendimiento',
    'Facturación y Pagos',
    'Acceso y Cuenta',
    'Integración y Software',
]

_CANONICAL_BY_NORMALIZED = {
    'estrategia y analisis': 'Estrategia y Análisis',
    'hardware y red': 'Hardware y Red',
    'otros': 'Otros',
    'seguridad y privacidad': 'Seguridad y Privacidad',
    'error de sistema y rendimiento': 'Error de Sistema / Rendimiento',
    'error de sistema rendimiento': 'Error de Sistema / Rendimiento',
    'facturacion y pagos': 'Facturación y Pagos',
    'acceso y cuenta': 'Acceso y Cuenta',
    'integracion y software': 'Integración y Software',
}

# Compatibilidad con etiquetas históricas/alternativas sin reentrenar modelos.
_TYPE_ALIASES = {
    # Cuentas y facturación
    'account & billing management': 'Facturación y Pagos',
    'account billing management': 'Facturación y Pagos',
    'billing': 'Facturación y Pagos',
    'billing and payments': 'Facturación y Pagos',
    'payments': 'Facturación y Pagos',

    # Acceso/cuenta y onboarding
    'customer onboarding': 'Acceso y Cuenta',
    'account access': 'Acceso y Cuenta',
    'account': 'Acceso y Cuenta',

    # Seguridad/compliance
    'security operations': 'Seguridad y Privacidad',
    'legal & compliance requests': 'Seguridad y Privacidad',
    'legal compliance requests': 'Seguridad y Privacidad',
    'legal and compliance requests': 'Seguridad y Privacidad',
    'security': 'Seguridad y Privacidad',

    # Integraciones/software/dev
    'software development': 'Integración y Software',
    'release management': 'Integración y Software',
    'partner & vendor coordination': 'Integración y Software',
    'partner vendor coordination': 'Integración y Software',
    'partner and vendor coordination': 'Integración y Software',
    'integration': 'Integración y Software',
    'integrations': 'Integración y Software',

    # Rendimiento/errores
    'incident': 'Error de Sistema / Rendimiento',
    'problem': 'Error de Sistema / Rendimiento',
    'request': 'Integración y Software',
    'data analytics reporting': 'Estrategia y Análisis',
    'data analytics and reporting': 'Estrategia y Análisis',
    'user experience design feedback': 'Otros',
    'user experience and design feedback': 'Otros',
    'network infrastructure': 'Hardware y Red',
}

_TYPE_KEYWORDS = {
    'Facturación y Pagos': [
        'facturacion', 'factura', 'pago', 'pagos', 'cobro', 'cobrado',
        'reembolso', 'devolucion', 'invoice', 'billing', 'charge', 'charged',
        'refund', 'payment', 'payments', 'card', 'tarjeta', 'microtransaccion',
        'compra', 'comprado', 'tarifa', 'suscripcion', 'renovacion',
    ],
    'Acceso y Cuenta': [
        'login', 'acceso', 'contrasena', 'password', 'cuenta', 'sign in',
        'signin', 'sesion', 'bloqueada', 'bloqueo', 'usuario', 'auth',
        'autenticacion', 'sso', 'registro',
    ],
    'Seguridad y Privacidad': [
        'phishing', 'hack', 'hacked', 'breach', '2fa', 'mfa', 'seguridad',
        'privacidad', 'data leak', 'vulnerabilidad', 'gdpr', 'rgpd', 'hipaa',
        'compliance', 'compliant', 'audit',
    ],
    'Hardware y Red': [
        'hardware', 'router', 'wifi', 'vpn', 'network', 'red', 'latencia',
        'conexion', 'conectividad', 'switch', 'dns',
    ],
    'Integración y Software': [
        'integracion', 'integration', 'api', 'sdk', 'plugin', 'jira', 'github',
        'gitlab', 'zapier', 'salesforce', 'deployment', 'release', 'pipeline',
        'ci/cd', 'software', 'app', 'aplicacion', 'etl',
    ],
    'Error de Sistema / Rendimiento': [
        'error', 'fallo', 'bug', 'crash', 'timeout', 'caida', 'lento',
        'rendimiento', 'performance', 'falla', 'intermitente', 'no funciona',
        'se ha caido', 'outage',
    ],
    'Estrategia y Análisis': [
        'analisis', 'analysis', 'dashboard', 'reporte', 'report', 'metricas',
        'kpi', 'estrategia', 'planificacion', 'forecast',
    ],
}


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


def _clean_text(value) -> str:
    """Normaliza texto de entrada (trim + colapsar espacios)."""
    text = '' if value is None else str(value)
    return re.sub(r'\s+', ' ', text).strip()


def _normalize_for_match(value: str) -> str:
    """Normaliza texto para matching robusto (minúsculas + sin acentos)."""
    cleaned = _clean_text(value).lower()
    if not cleaned:
        return ''
    decomposed = unicodedata.normalize('NFD', cleaned)
    without_accents = ''.join(ch for ch in decomposed if unicodedata.category(ch) != 'Mn')
    alnum_space = re.sub(r'[^a-z0-9]+', ' ', without_accents)
    return re.sub(r'\s+', ' ', alnum_space).strip()


def _build_subject_from_body(body_text: str) -> str:
    """Genera un asunto corto a partir del cuerpo del ticket."""
    body_text = _clean_text(body_text)
    if not body_text:
        return 'Nuevo ticket'

    # Prioriza la primera frase
    first_sentence = re.split(r'[\.!?\n]+', body_text, maxsplit=1)[0].strip()
    if not first_sentence:
        first_sentence = body_text

    words = first_sentence.split()
    if len(words) <= 12:
        subject = first_sentence
    else:
        subject = ' '.join(words[:12]) + '...'

    # Garantiza que subject no sea idéntico al body completo cuando sea posible
    if subject.lower() == body_text.lower():
        short_words = words[:8]
        subject = (' '.join(short_words) + '...') if short_words else 'Nuevo ticket'

    return subject[:160]


def _infer_queue_from_type(pred_type: str) -> str:
    """Mapea categoría predicha a una cola/departamento por defecto."""
    value = _canonicalize_ticket_type(pred_type, '', '')
    mapping = {
        'Error de Sistema / Rendimiento': 'technical_support',
        'Acceso y Cuenta': 'account_support',
        'Hardware y Red': 'network_support',
        'Facturación y Pagos': 'billing',
        'Seguridad y Privacidad': 'security',
        'Integración y Software': 'integrations',
        'Estrategia y Análisis': 'analytics',
        'Otros': 'general',
    }
    return mapping.get(value, 'general')


def _score_type_from_text(subject: str, body_text: str) -> str | None:
    """Puntuación por keywords para enrutar tickets a las 8 categorías de negocio."""
    text = _normalize_for_match(f"{subject} {body_text}")
    if not text:
        return None

    def score(words: list[str]) -> int:
        points = 0
        for kw in words:
            kw_norm = _normalize_for_match(kw)
            if kw_norm and kw_norm in text:
                points += 1
        return points

    scores = {label: score(words) for label, words in _TYPE_KEYWORDS.items()}
    best_label = max(scores, key=scores.get)
    best_score = scores[best_label]
    if best_score >= 1:
        return best_label
    return None


def _canonicalize_ticket_type(pred_type: str, subject: str, body_text: str) -> str:
    """Normaliza cualquier salida de modelo al catálogo fijo de 8 tipos."""
    normalized_pred = _normalize_for_match(pred_type)

    # Reglas basadas en texto primero: si hay señal clara en el ticket,
    # prevalece sobre aliases de modelos antiguos.
    inferred = _score_type_from_text(subject, body_text)
    if inferred:
        return inferred

    # Si ya viene en catálogo canónico, respetarlo.
    if normalized_pred in _CANONICAL_BY_NORMALIZED:
        return _CANONICAL_BY_NORMALIZED[normalized_pred]

    # Alias de modelos/datasets previos.
    if normalized_pred in _TYPE_ALIASES:
        return _TYPE_ALIASES[normalized_pred]

    # Fall-back seguro dentro del catálogo.
    return 'Otros'


def _normalize_ticket_payload(ticket: dict) -> dict:
    """Convierte payload libre en esquema consistente para clasificación e inserción."""
    if not isinstance(ticket, dict):
        return {}

    subject = _clean_text(ticket.get('subject') or ticket.get('title') or ticket.get('summary') or ticket.get('asunto'))
    body_text = _clean_text(
        ticket.get('body')
        or ticket.get('description')
        or ticket.get('message')
        or ticket.get('text')
        or ticket.get('content')
        or ticket.get('mensaje')
    )

    # Si solo llega subject, usarlo también como base de body
    if not body_text and subject:
        body_text = subject

    # Si no llega subject, generar uno automáticamente
    if not subject:
        subject = _build_subject_from_body(body_text)

    # Si subject y body llegan iguales (común en integraciones), resumir subject.
    if subject and body_text and _normalize_for_match(subject) == _normalize_for_match(body_text):
        subject = _build_subject_from_body(body_text)

    # Si body queda vacío tras todo, usar subject para no perder contexto
    if not body_text:
        body_text = subject

    normalized = dict(ticket)
    normalized['subject'] = subject
    normalized['body'] = body_text
    normalized['priority'] = _clean_text(ticket.get('priority') or ticket.get('prioridad') or 'normal').lower()
    normalized['queue'] = _clean_text(ticket.get('queue') or ticket.get('department') or ticket.get('category') or ticket.get('departamento'))
    return normalized


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

    normalized_tickets = [_normalize_ticket_payload(t) for t in tickets]
    normalized_tickets = [t for t in normalized_tickets if t]
    if not normalized_tickets:
        return jsonify({"error": "Formato de tickets inválido"}), 400

    level = _detect_level(file_row[2])  # filename

    # Clasificar con ML para obtener pred_type y pred_language
    try:
        import pandas as pd
        df_in = pd.DataFrame(normalized_tickets)
        df_classified = MLService.get_instance().classify_dataframe(df_in)

        # Enriquecimiento automático post-ML para routing interno
        if 'pred_type' in df_classified.columns:
            # Normalización al catálogo fijo de 8 tipos.
            def _override_type(row):
                subj = _clean_text(row.get('subject'))
                body = _clean_text(row.get('body'))
                return _canonicalize_ticket_type(str(row.get('pred_type', '')), subj, body)

            df_classified['pred_type'] = df_classified.apply(_override_type, axis=1)
            df_classified['pred_topic'] = df_classified['pred_type'].astype(str)
            if 'queue' not in df_classified.columns:
                df_classified['queue'] = ''
            df_classified['queue'] = df_classified.apply(
                lambda r: _clean_text(r.get('queue')) or _infer_queue_from_type(str(r.get('pred_type', ''))),
                axis=1
            )

        # Garantizar subject/body válidos incluso si llega entrada mínima
        df_classified['subject'] = df_classified.apply(
            lambda r: _clean_text(r.get('subject')) or _build_subject_from_body(_clean_text(r.get('body'))),
            axis=1
        )
        df_classified['body'] = df_classified.apply(
            lambda r: _clean_text(r.get('body')) or _clean_text(r.get('subject')),
            axis=1
        )
    except Exception as exc:
        return jsonify({"error": f"Error en clasificación ML: {exc}"}), 500

    conn, tmp = _open_db(file_row)
    inserted_ids = []

    try:
        for _, row in df_classified.iterrows():
            pred_type = str(row.get('pred_type', ''))
            pred_lang = str(row.get('pred_language', ''))
            subj = _clean_text(row.get('subject', row.get('title', '')))
            body_text = _clean_text(row.get('body', row.get('description', row.get('message', row.get('text', '')))))
            if not subj:
                subj = _build_subject_from_body(body_text)
            if not body_text:
                body_text = subj

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
                queue_val = _clean_text(row.get('queue', row.get('department', ''))) or _infer_queue_from_type(pred_type)
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

    preview = []
    for idx, tid in enumerate(inserted_ids):
        row = df_classified.iloc[idx]
        preview.append({
            'ticket_id': tid,
            'subject': _clean_text(row.get('subject')),
            'pred_language': str(row.get('pred_language', '')),
            'pred_type': str(row.get('pred_type', '')),
            'pred_topic': str(row.get('pred_topic', row.get('pred_type', ''))),
            'pred_level': str(row.get('pred_level', level)),
            'queue': _clean_text(row.get('queue')),
        })

    return jsonify({
        "inserted": len(inserted_ids),
        "ticket_ids": inserted_ids,
        "enriched_preview": preview,
    }), 201


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
