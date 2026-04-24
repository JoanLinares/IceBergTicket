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
from src.services.ml_service import (
    MLService,
    _detect_language_from_text,
    _normalize_language_code,
)
from src.services.dw_service import (
    _upsert_date, _upsert_customer, _upsert_agent,
    _upsert_dim_text, _upsert_language, _insert_tags,
    _conn_to_bytes, decompress_db, compress_db_fast, _to_epoch, LANG_NAMES,
)

import os
import tempfile
import re
import unicodedata

try:
    from sumy.parsers.plaintext import PlaintextParser
    from sumy.nlp.tokenizers import Tokenizer
    from sumy.summarizers.lsa import LsaSummarizer
except Exception:
    PlaintextParser = None
    Tokenizer = None
    LsaSummarizer = None

try:
    from langdetect import detect_langs, LangDetectException
except Exception:
    detect_langs = None
    LangDetectException = Exception


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

_MAX_SUBJECT_WORDS = 6
_MAX_SUBJECT_LEN = 72

_GENERIC_INTRO_PREFIXES = (
    'me pongo en contacto',
    'les escribo',
    'quiero reportar',
    'quisiera reportar',
    'buenas',
    'hola',
    'estimado',
)

_LANG_PAYLOAD_KEYS = (
    'language',
    'lang',
    'idioma',
    'language_code',
    'ticket_language',
    'locale',
    'language_hint',
)

_ES_LANGUAGE_MARKERS = {
    'hola', 'necesito', 'herramienta', 'sincronizacion', 'algunos',
    'despues', 'hemos', 'revisado', 'configuracion', 'podrian',
    'gracias', 'problema', 'credenciales', 'aparacen', 'aparecen',
}
_PT_LANGUAGE_MARKERS = {
    'ola', 'preciso', 'ferramenta', 'sincronizacao', 'alguns',
    'depois', 'revisamos', 'configuracao', 'poderiam',
    'obrigado', 'problema', 'credenciais', 'aparecem',
}
_LANG_TOKEN_RE = re.compile(r'[a-z]{2,}')


def _has_value(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _dict_get_ci(data: dict, *keys):
    """Busca una clave en dict de forma case-insensitive y devuelve primer valor no vacío."""
    for key in keys:
        value = data.get(key)
        if _has_value(value):
            return value

    lowered = {str(k).lower(): v for k, v in data.items()}
    for key in keys:
        value = lowered.get(str(key).lower())
        if _has_value(value):
            return value

    return None


def _row_get_ci(row, *keys):
    """Busca una clave en pandas.Series (index) de forma case-insensitive."""
    for key in keys:
        value = row.get(key)
        if _has_value(value):
            return value

    wanted = {str(k).lower() for k in keys}
    for col in row.index:
        if str(col).lower() in wanted:
            value = row.get(col)
            if _has_value(value):
                return value

    return None


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


def _short_subject(text: str, max_words: int = _MAX_SUBJECT_WORDS, max_len: int = _MAX_SUBJECT_LEN) -> str:
    """Compacta un texto a un asunto muy corto sin copiar el cuerpo literal."""
    clean = _clean_text(text)
    if not clean:
        return 'Nuevo ticket'

    words = clean.split()
    reduced = ' '.join(words[:max_words]).strip()
    if len(reduced) > max_len:
        reduced = reduced[:max_len].rstrip()
    reduced = reduced.strip(' .,:;')

    return reduced or 'Nuevo ticket'


def _strip_intro_phrases(text: str) -> str:
    """Elimina aperturas de cortesía que no aportan valor al asunto."""
    clean = _clean_text(text)
    if not clean:
        return ''

    patterns = [
        r'^(hola|buenas(?:\s+dias|\s+tardes|\s+noches)?|estimad[oa]s?)\s*[:,\-]?\s*',
        r'^(me\s+pongo\s+en\s+contacto(?:\s+con\s+ustedes)?(?:\s+porque)?|'
        r'les\s+escribo(?:\s+porque)?|'
        r'quiero\s+reportar(?:\s+que)?|'
        r'quisiera\s+reportar(?:\s+que)?)\s*[:,\-]?\s*',
    ]

    out = clean
    for pattern in patterns:
        out = re.sub(pattern, '', out, flags=re.IGNORECASE)
        out = _clean_text(out)

    return out or clean


def _intent_subject(body_text: str) -> str:
    """Genera un asunto corto orientado a negocio según señales del texto."""
    norm = _normalize_for_match(body_text)
    if not norm:
        return ''

    inferred_type = _score_type_from_text('', body_text)

    if inferred_type == 'Facturación y Pagos':
        if any(k in norm for k in ('reembolso', 'devolucion', 'refund')):
            return 'Solicitud de reembolso'
        if any(k in norm for k in ('microtransaccion', 'microtransaccion extra')):
            return 'Fallo en microtransaccion'
        if any(k in norm for k in ('pendiente', 'proceso', 'no confirmado', 'sin confirmar', 'liquidacion')):
            return 'Pago pendiente de confirmacion'
        if any(k in norm for k in ('debitado', 'cobrado', 'cobro', 'cargo')):
            return 'Cobro no reflejado en plataforma'
        return 'Incidencia de facturacion'

    if inferred_type == 'Acceso y Cuenta':
        return 'Problema de acceso a cuenta'
    if inferred_type == 'Seguridad y Privacidad':
        return 'Incidencia de seguridad'
    if inferred_type == 'Hardware y Red':
        return 'Incidencia de red o conectividad'
    if inferred_type == 'Integración y Software':
        return 'Fallo de integracion o software'
    if inferred_type == 'Error de Sistema / Rendimiento':
        return 'Error de sistema en plataforma'

    return ''


def _sumy_sentence(text: str) -> str:
    """Intenta resumir con Sumy (LSA) y devuelve una sola frase."""
    if not (PlaintextParser and Tokenizer and LsaSummarizer):
        return ''

    content = _strip_intro_phrases(text)
    if not content:
        return ''

    for language in ('spanish', 'english'):
        try:
            parser = PlaintextParser.from_string(content, Tokenizer(language))
            summarizer = LsaSummarizer()
            sentence = next(iter(summarizer(parser.document, 1)), None)
            if sentence:
                return _clean_text(str(sentence))
        except Exception:
            continue

    return ''


def _build_subject_from_body(body_text: str) -> str:
    """Genera un asunto muy corto a partir del cuerpo del ticket."""
    body_text = _clean_text(body_text)
    if not body_text:
        return 'Nuevo ticket'

    refined_body = _strip_intro_phrases(body_text)

    # Primero, intentamos asunto orientado a intención de negocio.
    candidate = _intent_subject(refined_body)

    if not candidate:
        # Segundo intento: Sumy (extractivo) sobre texto refinado.
        candidate = _sumy_sentence(refined_body)

    if not candidate:
        # Fallback final: primera frase útil del texto refinado.
        candidate = re.split(r'[\.!?\n]+', refined_body, maxsplit=1)[0].strip() or refined_body

    if _normalize_for_match(candidate).startswith(_GENERIC_INTRO_PREFIXES):
        intent_fallback = _intent_subject(refined_body)
        if intent_fallback:
            candidate = intent_fallback

    subject = _short_subject(candidate)

    # Nunca guardar subject idéntico al body.
    if _normalize_for_match(subject) == _normalize_for_match(body_text):
        words = refined_body.split()
        fallback = ' '.join(words[:max(1, min(4, len(words)))])
        subject = _short_subject(fallback)

    return subject[:_MAX_SUBJECT_LEN]


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

    subject = _clean_text(_dict_get_ci(ticket, 'subject', 'title', 'summary', 'asunto'))
    body_text = _clean_text(
        _dict_get_ci(ticket, 'body', 'description', 'message', 'text', 'content', 'mensaje')
    )

    # Si solo llega subject, usarlo también como base de body
    if not body_text and subject:
        body_text = subject

    # Si no llega subject, generar uno automáticamente
    if not subject:
        subject = _build_subject_from_body(body_text)

    # Mantener el asunto muy corto, aunque venga informado por integración.
    if subject:
        subject = _short_subject(subject)

    # Si subject y body llegan iguales (común en integraciones), resumir subject.
    if subject and body_text and _normalize_for_match(subject) == _normalize_for_match(body_text):
        subject = _build_subject_from_body(body_text)

    # Si body queda vacío tras todo, usar subject para no perder contexto
    if not body_text:
        body_text = subject

    normalized = dict(ticket)
    normalized['subject'] = subject
    normalized['body'] = body_text
    normalized['priority'] = _clean_text(_dict_get_ci(ticket, 'priority', 'prioridad') or 'normal').lower()
    normalized['queue'] = _clean_text(_dict_get_ci(ticket, 'queue', 'department', 'category', 'departamento'))
    return normalized


def _verify_language_from_text(subject: str, body: str) -> str:
    """Verifica el idioma final desde el texto antes de persistirlo."""
    text = _clean_text(f"{subject} {body}".strip()).lower()
    if len(text) < 15:
        return ''

    # Marcas exclusivas de espanol muy fiables.
    if any(ch in text for ch in ('¿', '¡', 'ñ')):
        return 'es'

    normalized = _normalize_for_match(text)
    tokens = _LANG_TOKEN_RE.findall(normalized)
    if len(tokens) < 4:
        return ''

    es_score = sum(1 for tok in tokens if tok in _ES_LANGUAGE_MARKERS)
    pt_score = sum(1 for tok in tokens if tok in _PT_LANGUAGE_MARKERS)

    # Tildes frecuentes en portugues; no aparecen en el ejemplo del usuario,
    # pero ayudan cuando el texto si las contiene.
    if any(ch in text for ch in ('ã', 'õ', 'ç')):
        pt_score += 2

    if es_score >= pt_score + 1:
        return 'es'
    if pt_score >= es_score + 2:
        return 'pt'
    return ''


def _detect_language_with_library(subject: str, body: str) -> str:
    """Usa langdetect directamente y normaliza la salida a los codigos soportados."""
    if detect_langs is None:
        return ''

    text = _clean_text(f"{subject} {body}".strip())
    if len(text) < 15:
        return ''

    try:
        candidates = detect_langs(text)
    except LangDetectException:
        return ''
    except Exception:
        return ''

    if not candidates:
        return ''

    top = candidates[0]
    lang = _normalize_language_code(getattr(top, 'lang', None)) or ''
    prob = float(getattr(top, 'prob', 0.0))
    if not lang:
        return ''

    if prob < 0.70 and len(text) < 120:
        return ''
    return lang


def _resolve_ingest_language_details(row) -> tuple[str, str, str]:
    """Resuelve idioma para ingest y devuelve (payload_lang, verified_lang, final_lang)."""
    subject = _clean_text(_row_get_ci(row, 'subject', 'title', 'summary'))
    body = _clean_text(
        _row_get_ci(row, 'body', 'description', 'message', 'text', 'content', 'mensaje')
    )
    verified_lang = _verify_language_from_text(subject, body)
    library_lang = _detect_language_with_library(subject, body)
    detected = _detect_language_from_text(f"{subject} {body}".strip())
    detected_payload = _normalize_language_code(_row_get_ci(row, 'detected_language')) or ''
    detected_lang = verified_lang or library_lang or detected or detected_payload or ''

    # Fallback: si la detección por texto no puede decidir (textos muy cortos,
    # mezcla de idiomas), usar hint explícito de la integración.
    payload_lang = _normalize_language_code(_row_get_ci(row, *_LANG_PAYLOAD_KEYS)) or ''

    model_pred = _normalize_language_code(_row_get_ci(row, 'pred_language')) or ''
    final_lang = verified_lang or library_lang or detected_lang or model_pred or payload_lang or 'unknown'
    return payload_lang, detected_lang, final_lang

def _resolve_ingest_language(row) -> str:
    """Compatibilidad: devuelve solo el idioma final."""
    return _resolve_ingest_language_details(row)[2]


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

        # Resolver idioma antes de escribir en DB. Guardamos trazabilidad para depuración:
        # - payload_language: hint recibido de la integración
        # - detected_language: idioma detectado por texto
        # - pred_language: idioma final persistido
        language_resolution = df_classified.apply(
            _resolve_ingest_language_details,
            axis=1,
            result_type='expand',
        )
        language_resolution.columns = ['payload_language', 'detected_language', 'pred_language']
        df_classified[['payload_language', 'detected_language', 'pred_language']] = language_resolution
    except Exception as exc:
        return jsonify({"error": f"Error en clasificación ML: {exc}"}), 500

    conn, tmp = _open_db(file_row)
    inserted_ids = []

    try:
        for _, row in df_classified.iterrows():
            pred_type = str(row.get('pred_type', ''))
            subj = _clean_text(row.get('subject', row.get('title', '')))
            body_text = _clean_text(row.get('body', row.get('description', row.get('message', row.get('text', '')))))
            if not subj:
                subj = _build_subject_from_body(body_text)
            else:
                subj = _short_subject(subj)
            if subj and body_text and _normalize_for_match(subj) == _normalize_for_match(body_text):
                subj = _build_subject_from_body(body_text)
            if not body_text:
                body_text = subj

            # Verificacion final justo antes de persistir en DB.
            pred_lang = (
                _verify_language_from_text(subj, body_text)
                or _detect_language_with_library(subj, body_text)
                or _detect_language_from_text(f"{subj} {body_text}".strip())
                or _normalize_language_code(row.get('pred_language'))
                or _normalize_language_code(row.get('detected_language'))
                or _normalize_language_code(row.get('payload_language'))
                or 'unknown'
            )

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
            'pred_language': str(_normalize_language_code(row.get('pred_language')) or 'unknown'),
            'detected_language': str(_normalize_language_code(row.get('detected_language')) or ''),
            'payload_language': str(_normalize_language_code(row.get('payload_language')) or ''),
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
