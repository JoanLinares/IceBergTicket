"""
DWService — Crea UNA base de datos SQLite con los tickets clasificados.

Analiza las predicciones del modelo ML para determinar el nivel óptimo
(BASIC / MEDIUM / PRO) para todo el dataset y crea un solo SQLite con
ese esquema, incluyendo TODOS los tickets.

Estrategia de selección:
  - Se elige el nivel con más tickets (mayoría).
  - En caso de empate, se elige el nivel más alto (PRO > MEDIUM > BASIC).

Esquema según nivel:
  1. Crea un SQLite en memoria con el esquema del nivel correspondiente.
  2. Inserta dims (dim_date, dim_customer, dim_agent, dim_type, dim_language,
     dim_priority, dim_status) con lógica INSERT OR IGNORE.
  3. Inserta fact_tickets y ticket_text referenciando las dims.
  4. En PRO, además inserta dim_tag + bridge_ticket_tags.
  5. Serializa el .db a bytes (vía fichero temporal).

Returns:
    dict { nivel_óptimo: bytes }  (siempre un solo elemento)
"""
import os
import sqlite3
import tempfile
import hashlib
import lzma
import zlib
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict

from src.services.ml_service import _find_col, _COL_ALIASES

LANG_NAMES = {
    'en': 'English', 'es': 'Español', 'de': 'Deutsch',
    'fr': 'Français', 'pt': 'Português',
}

# Longitud máxima de texto en ticket_text (el DW es analítico, no operacional)
_MAX_BODY_LEN    = 1000
_MAX_ANSWER_LEN  = 500
_MAX_SUBJECT_LEN = 200


def _truncate(text: str, max_len: int) -> str:
    if not text or len(text) <= max_len:
        return text
    return text[:max_len - 1] + '…'


def _clean_text_value(value, default: str = '') -> str:
    """Normaliza valores de texto evitando None/NaN/None-like en dimensiones."""
    if value is None:
        return default
    try:
        if pd.isnull(value):
            return default
    except Exception:
        pass
    text = str(value).strip()
    if not text or text.lower() in {'nan', 'none', 'null', 'nat'}:
        return default
    return text


def _to_epoch(val) -> int:
    """Convierte un valor de fecha a Unix epoch (int). Compacto en SQLite."""
    if val is None:
        return int(datetime.now().timestamp())
    if isinstance(val, (int, float)):
        return int(val)
    try:
        return int(pd.Timestamp(str(val)).timestamp())
    except Exception:
        return int(datetime.now().timestamp())


def _apply_pragmas(conn: sqlite3.Connection):
    """Optimizaciones SQLite para reducir espacio en disco y acelerar inserción."""
    conn.executescript("""
        PRAGMA page_size     = 4096;
        PRAGMA journal_mode  = MEMORY;
        PRAGMA synchronous   = OFF;
        PRAGMA temp_store    = MEMORY;
        PRAGMA cache_size    = -65536;
    """)


# ──────────────────────────────────────────────────────────────────────
# Creación de esquemas
# ──────────────────────────────────────────────────────────────────────

def _basic_schema(conn):
    _apply_pragmas(conn)
    conn.executescript("""
        PRAGMA foreign_keys = OFF;
        CREATE TABLE IF NOT EXISTS dim_date (
            date_key INTEGER PRIMARY KEY,
            date TEXT, year INTEGER, month INTEGER,
            month_name TEXT, day INTEGER, day_name TEXT, is_weekend INTEGER
        );
        CREATE TABLE IF NOT EXISTS dim_customer (
            customer_key INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT, email TEXT UNIQUE
        );
        CREATE TABLE IF NOT EXISTS dim_agent (
            agent_key INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_name TEXT UNIQUE, team TEXT
        );
        CREATE TABLE IF NOT EXISTS dim_priority (
            priority_key INTEGER PRIMARY KEY AUTOINCREMENT,
            priority_name TEXT UNIQUE
        );
        CREATE TABLE IF NOT EXISTS dim_status (
            status_key INTEGER PRIMARY KEY AUTOINCREMENT,
            status_name TEXT UNIQUE
        );
        CREATE TABLE IF NOT EXISTS fact_tickets (
            ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_key INTEGER, customer_key INTEGER, agent_key INTEGER,
            priority_key INTEGER, status_key INTEGER,
            created_at INTEGER, pred_type TEXT, pred_language TEXT
        );
        CREATE TABLE IF NOT EXISTS ticket_text (
            ticket_id INTEGER PRIMARY KEY,
            subject TEXT, description TEXT
        );
    """)


def _medium_schema(conn):
    _apply_pragmas(conn)
    conn.executescript("""
        PRAGMA foreign_keys = OFF;
        CREATE TABLE IF NOT EXISTS dim_date (
            date_key INTEGER PRIMARY KEY,
            date TEXT, year INTEGER, quarter INTEGER,
            month INTEGER, month_name TEXT, day INTEGER,
            day_name TEXT, is_weekend INTEGER
        );
        CREATE TABLE IF NOT EXISTS dim_customer (
            customer_key INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT, email TEXT UNIQUE
        );
        CREATE TABLE IF NOT EXISTS dim_agent (
            agent_key INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_name TEXT UNIQUE, team TEXT
        );
        CREATE TABLE IF NOT EXISTS dim_type (
            type_key INTEGER PRIMARY KEY AUTOINCREMENT,
            type_name TEXT UNIQUE
        );
        CREATE TABLE IF NOT EXISTS dim_priority (
            priority_key INTEGER PRIMARY KEY AUTOINCREMENT,
            priority_name TEXT UNIQUE
        );
        CREATE TABLE IF NOT EXISTS dim_status (
            status_key INTEGER PRIMARY KEY AUTOINCREMENT,
            status_name TEXT UNIQUE
        );
        CREATE TABLE IF NOT EXISTS dim_language (
            language_key INTEGER PRIMARY KEY AUTOINCREMENT,
            language_code TEXT UNIQUE, language_name TEXT
        );
        CREATE TABLE IF NOT EXISTS fact_tickets (
            ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_key INTEGER, customer_key INTEGER, agent_key INTEGER,
            type_key INTEGER, priority_key INTEGER, status_key INTEGER,
            language_key INTEGER,
            created_at INTEGER
        );
        CREATE TABLE IF NOT EXISTS ticket_text (
            ticket_id INTEGER PRIMARY KEY,
            subject TEXT, description TEXT
        );
    """)


def _pro_schema(conn):
    _apply_pragmas(conn)
    conn.executescript("""
        PRAGMA foreign_keys = OFF;
        CREATE TABLE IF NOT EXISTS dim_date (
            date_key INTEGER PRIMARY KEY,
            date TEXT, year INTEGER, quarter INTEGER,
            month INTEGER, month_name TEXT, day INTEGER,
            day_of_week INTEGER, day_name TEXT,
            is_weekend INTEGER, fiscal_year INTEGER
        );
        CREATE TABLE IF NOT EXISTS dim_customer (
            customer_key INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT, email TEXT UNIQUE
        );
        CREATE TABLE IF NOT EXISTS dim_agent (
            agent_key INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_name TEXT UNIQUE, team TEXT
        );
        CREATE TABLE IF NOT EXISTS dim_ticket_type (
            type_key INTEGER PRIMARY KEY AUTOINCREMENT,
            type_name TEXT UNIQUE
        );
        CREATE TABLE IF NOT EXISTS dim_priority (
            priority_key INTEGER PRIMARY KEY AUTOINCREMENT,
            priority_name TEXT UNIQUE
        );
        CREATE TABLE IF NOT EXISTS dim_queue (
            queue_key INTEGER PRIMARY KEY AUTOINCREMENT,
            queue_name TEXT UNIQUE
        );
        CREATE TABLE IF NOT EXISTS dim_language (
            language_key INTEGER PRIMARY KEY AUTOINCREMENT,
            language_code TEXT UNIQUE, language_name TEXT
        );
        CREATE TABLE IF NOT EXISTS dim_status (
            status_key INTEGER PRIMARY KEY AUTOINCREMENT,
            status_name TEXT UNIQUE
        );
        CREATE TABLE IF NOT EXISTS dim_tag (
            tag_key INTEGER PRIMARY KEY AUTOINCREMENT,
            tag_name TEXT UNIQUE
        );
        CREATE TABLE IF NOT EXISTS fact_tickets (
            ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_key INTEGER, customer_key INTEGER, agent_key INTEGER,
            type_key INTEGER, priority_key INTEGER, queue_key INTEGER,
            language_key INTEGER, status_key INTEGER,
            created_at INTEGER, word_count_subject INTEGER, word_count_body INTEGER
        );
        CREATE TABLE IF NOT EXISTS bridge_ticket_tags (
            ticket_id INTEGER, tag_key INTEGER, tag_order INTEGER,
            PRIMARY KEY (ticket_id, tag_key)
        ) WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS ticket_text (
            ticket_id INTEGER PRIMARY KEY,
            subject TEXT, body TEXT, answer TEXT
        );
    """)


_SCHEMA_MAP = {'BASIC': _basic_schema, 'MEDIUM': _medium_schema, 'PRO': _pro_schema}

# ──────────────────────────────────────────────────────────────────────
# Extracción de datos para upgrade de nivel
# ──────────────────────────────────────────────────────────────────────

def _extract_dataframe(conn: sqlite3.Connection, level: str) -> pd.DataFrame:
    """Reconstruye un DataFrame desde un SQLite DW ya existente según su nivel."""
    if level == 'BASIC':
        rows = conn.execute("""
            SELECT COALESCE(tt.subject, '') AS subject,
                   COALESCE(tt.description, '') AS body,
                   COALESCE(NULLIF(TRIM(f.pred_type), ''), 'unknown') AS pred_type,
                   COALESCE(NULLIF(TRIM(f.pred_language), ''), 'unknown') AS pred_language,
                   COALESCE(p.priority_name, 'normal') AS priority,
                   COALESCE(s.status_name, 'open') AS status,
                   COALESCE(c.customer_name, 'Unknown') AS submitter_name,
                   COALESCE(c.email, 'unknown@unknown.com') AS submitter_email,
                   a.agent_name, f.created_at
            FROM fact_tickets f
            LEFT JOIN ticket_text tt ON f.ticket_id = tt.ticket_id
            LEFT JOIN dim_priority p ON f.priority_key = p.priority_key
            LEFT JOIN dim_status   s ON f.status_key   = s.status_key
            LEFT JOIN dim_customer c ON f.customer_key = c.customer_key
            LEFT JOIN dim_agent a ON f.agent_key  = a.agent_key
        """).fetchall()
        cols = ['subject', 'body', 'pred_type', 'pred_language',
                'priority', 'status', 'submitter_name', 'submitter_email',
                'agent_name', 'created_at']

    elif level == 'MEDIUM':
        rows = conn.execute("""
             SELECT COALESCE(tt.subject, '') AS subject,
                 COALESCE(tt.description, '') AS body,
                 COALESCE(NULLIF(TRIM(dt.type_name), ''), 'unknown') AS pred_type,
                 COALESCE(NULLIF(TRIM(dl.language_code), ''), 'unknown') AS pred_language,
                 COALESCE(p.priority_name, 'normal') AS priority,
                 COALESCE(s.status_name, 'open') AS status,
                 COALESCE(c.customer_name, 'Unknown') AS submitter_name,
                 COALESCE(c.email, 'unknown@unknown.com') AS submitter_email,
                   a.agent_name, f.created_at
            FROM fact_tickets f
             LEFT JOIN ticket_text  tt ON f.ticket_id    = tt.ticket_id
             LEFT JOIN dim_type     dt ON f.type_key     = dt.type_key
             LEFT JOIN dim_language dl ON f.language_key = dl.language_key
             LEFT JOIN dim_priority  p ON f.priority_key = p.priority_key
             LEFT JOIN dim_status    s ON f.status_key   = s.status_key
             LEFT JOIN dim_customer  c ON f.customer_key = c.customer_key
            LEFT JOIN dim_agent a ON f.agent_key   = a.agent_key
        """).fetchall()
        cols = ['subject', 'body', 'pred_type', 'pred_language',
                'priority', 'status', 'submitter_name', 'submitter_email',
                'agent_name', 'created_at']

    else:  # PRO — extrae todo por completitud
        rows = conn.execute("""
             SELECT COALESCE(tt.subject, '') AS subject,
                 COALESCE(tt.body, '') AS body,
                 COALESCE(NULLIF(TRIM(dt.type_name), ''), 'unknown') AS pred_type,
                 COALESCE(NULLIF(TRIM(dl.language_code), ''), 'unknown') AS pred_language,
                 COALESCE(p.priority_name, 'normal') AS priority,
                 COALESCE(s.status_name, 'open') AS status,
                 COALESCE(q.queue_name, 'general') AS queue,
                 COALESCE(c.customer_name, 'Unknown') AS submitter_name,
                 COALESCE(c.email, 'unknown@unknown.com') AS submitter_email,
                   a.agent_name, f.created_at, tt.answer
            FROM fact_tickets f
             LEFT JOIN ticket_text     tt ON f.ticket_id    = tt.ticket_id
             LEFT JOIN dim_ticket_type dt ON f.type_key     = dt.type_key
             LEFT JOIN dim_language    dl ON f.language_key = dl.language_key
             LEFT JOIN dim_priority     p ON f.priority_key = p.priority_key
             LEFT JOIN dim_status       s ON f.status_key   = s.status_key
             LEFT JOIN dim_queue        q ON f.queue_key    = q.queue_key
             LEFT JOIN dim_customer     c ON f.customer_key = c.customer_key
            LEFT JOIN dim_agent   a ON f.agent_key    = a.agent_key
        """).fetchall()
        cols = ['subject', 'body', 'pred_type', 'pred_language',
                'priority', 'status', 'queue',
                'submitter_name', 'submitter_email', 'agent_name',
                'created_at', 'answer']

    return pd.DataFrame(rows, columns=cols)


def _count_fact_tickets(conn: sqlite3.Connection) -> int:
    """Cuenta filas en fact_tickets si existe, si no devuelve 0."""
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='fact_tickets'"
    ).fetchone()
    if not exists:
        return 0
    row = conn.execute("SELECT COUNT(*) FROM fact_tickets").fetchone()
    return int(row[0] if row else 0)


def extract_for_upgrade(db_bytes: bytes, include_stats: bool = False):
    """
    Detecta el nivel actual del SQLite DW y extrae sus datos como DataFrame.
    Devuelve (current_level: str, df: pd.DataFrame)
    o (current_level, df, stats) si include_stats=True.
    Útil para construir un nuevo DW en un nivel superior sin perder información.
    """
    fd, tmp = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    try:
        with open(tmp, 'wb') as fh:
            fh.write(db_bytes)
        conn = sqlite3.connect(tmp)
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        if 'dim_queue' in tables:
            level = 'PRO'
        elif 'dim_type' in tables:
            level = 'MEDIUM'
        else:
            level = 'BASIC'
        source_ticket_count = _count_fact_tickets(conn)
        df = _extract_dataframe(conn, level)
        conn.close()
    finally:
        os.unlink(tmp)
    if include_stats:
        stats = {
            'source_ticket_count': source_ticket_count,
            'extracted_ticket_count': int(len(df)),
            'dropped_ticket_count': int(max(source_ticket_count - len(df), 0)),
        }
        return level, df, stats
    return level, df


# ──────────────────────────────────────────────────────────────────────
# Helpers de dimensiones
# ──────────────────────────────────────────────────────────────────────

def _upsert_date(conn, dt_val) -> int:
    """Inserta o recupera date_key (YYYYMMDD) para una fecha."""
    try:
        d = pd.to_datetime(dt_val)
    except Exception:
        d = pd.Timestamp.now()
    # pd.to_datetime(None/NaN) returns NaT without raising — guard here
    if pd.isnull(d):
        d = pd.Timestamp.now()
    key = int(d.strftime('%Y%m%d'))
    month_names = ['January','February','March','April','May','June',
                   'July','August','September','October','November','December']
    day_names   = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
    conn.execute("""
        INSERT OR IGNORE INTO dim_date
        (date_key, date, year, month, month_name, day, day_name, is_weekend)
        VALUES (?,?,?,?,?,?,?,?)
    """, (key, d.strftime('%Y-%m-%d'), d.year, d.month,
          month_names[d.month - 1], d.day,
          day_names[d.dayofweek], 1 if d.dayofweek >= 5 else 0))
    return key


def _upsert_customer(conn, name, email) -> int:
    conn.execute(
        "INSERT OR IGNORE INTO dim_customer (customer_name, email) VALUES (?,?)",
        (name or 'Unknown', email or 'unknown@unknown.com')
    )
    row = conn.execute(
        "SELECT customer_key FROM dim_customer WHERE email=?",
        (email or 'unknown@unknown.com',)
    ).fetchone()
    return row[0]


def _upsert_agent(conn, agent_name, team=None) -> int | None:
    if not agent_name:
        return None
    conn.execute(
        "INSERT OR IGNORE INTO dim_agent (agent_name, team) VALUES (?,?)",
        (agent_name, team or 'General')
    )
    row = conn.execute(
        "SELECT agent_key FROM dim_agent WHERE agent_name=?", (agent_name,)
    ).fetchone()
    return row[0] if row else None


def _upsert_dim_text(conn, table, name_col, key_col, value) -> int | None:
    if not value:
        return None
    conn.execute(
        f"INSERT OR IGNORE INTO {table} ({name_col}) VALUES (?)", (value,)
    )
    row = conn.execute(
        f"SELECT {key_col} FROM {table} WHERE {name_col}=?", (value,)
    ).fetchone()
    return row[0] if row else None


def _upsert_language(conn, lang_code) -> int | None:
    if not lang_code:
        return None
    name = LANG_NAMES.get(str(lang_code).lower(), lang_code)
    conn.execute(
        "INSERT OR IGNORE INTO dim_language (language_code, language_name) VALUES (?,?)",
        (lang_code, name)
    )
    row = conn.execute(
        "SELECT language_key FROM dim_language WHERE language_code=?", (lang_code,)
    ).fetchone()
    return row[0] if row else None


def _insert_tags(conn, ticket_id: int, tag_cols: list, row: pd.Series,
                 tag_cache: dict | None = None):
    """Inserta tags en dim_tag + bridge. Soporta dos formatos:
    - Columna 'tags' con valores separados por coma: "Bug, Feature, Crash"
    - Columnas individuales tag_* = True/1
    Usa tag_cache para evitar SELECT repetidos (~8 tags únicos, 400k lookups).
    """
    if tag_cache is None:
        tag_cache = {}

    def _tag_key(name: str) -> int | None:
        if name in tag_cache:
            return tag_cache[name]
        conn.execute("INSERT OR IGNORE INTO dim_tag (tag_name) VALUES (?)", (name,))
        r = conn.execute("SELECT tag_key FROM dim_tag WHERE tag_name=?", (name,)).fetchone()
        if r:
            tag_cache[name] = r[0]
            return r[0]
        return None

    # Formato 1: columna única 'tags' con valores separados por coma
    tags_val = row.get('tags', None)
    if tags_val and str(tags_val).strip().lower() not in ('', 'nan', 'none'):
        for order, tag_name in enumerate(str(tags_val).split(',')):
            tag_name = tag_name.strip()
            if not tag_name:
                continue
            tk = _tag_key(tag_name)
            if tk is not None:
                conn.execute(
                    "INSERT OR IGNORE INTO bridge_ticket_tags VALUES (?,?,?)",
                    (ticket_id, tk, order))
        return

    # Formato 2: columnas individuales tag_*
    for order, col in enumerate(tag_cols):
        val = row.get(col)
        if val and str(val).strip().lower() not in ('false', '0', 'nan', ''):
            tag_name = col.replace('tag_', '').replace('_', ' ')
            tk = _tag_key(tag_name)
            if tk is not None:
                conn.execute(
                    "INSERT OR IGNORE INTO bridge_ticket_tags VALUES (?,?,?)",
                    (ticket_id, tk, order))


# ──────────────────────────────────────────────────────────────────────
# Generación de datos sintéticos para columnas ausentes
# ──────────────────────────────────────────────────────────────────────

_SYNTH_AGENTS = [
    ('Carlos García', 'carlos.garcia@support.com', 'Billing'),
    ('Laura Martínez', 'laura.martinez@support.com', 'Technical'),
    ('Alex Johnson', 'alex.johnson@support.com', 'General'),
    ('María López', 'maria.lopez@support.com', 'Sales'),
    ('David Chen', 'david.chen@support.com', 'Technical'),
    ('Sofía Ruiz', 'sofia.ruiz@support.com', 'Billing'),
    ('James Wilson', 'james.wilson@support.com', 'General'),
    ('Ana Torres', 'ana.torres@support.com', 'Sales'),
]

_SYNTH_STATUSES = ['open', 'closed', 'pending', 'resolved', 'escalated']
_STATUS_WEIGHTS = [0.15, 0.45, 0.15, 0.20, 0.05]


def _synthesize_missing_columns(subset: pd.DataFrame) -> pd.DataFrame:
    """
    Añade columnas sintéticas realistas al subset si no existen en el
    CSV original, para que las dimensiones del DW no queden vacías.
    Usa un seed determinista basado en el hash de la primera fila para
    que el resultado sea reproducible.
    """
    n = len(subset)
    seed = int(hashlib.md5(str(subset.index[0]).encode()).hexdigest()[:8], 16) % (2**31)
    rng = np.random.RandomState(seed)

    # --- created_at: distribuir en los últimos 180 días ---
    if _find_col(subset, 'created_at') is None:
        today = pd.Timestamp.now().normalize()
        offsets = rng.randint(0, 180, size=n)
        subset = subset.copy()
        subset['created_at'] = [
            (today - pd.Timedelta(days=int(d))).strftime('%Y-%m-%dT%H:%M:%S')
            for d in offsets
        ]

    # --- submitter_email / submitter_name: generar clientes únicos ---
    if _find_col(subset, 'submitter_email') is None:
        customer_ids = rng.randint(1, max(n // 5, 50) + 1, size=n)
        subset = subset.copy() if 'created_at' not in subset.columns else subset
        subset['submitter_email'] = [f'customer{cid}@mail.com' for cid in customer_ids]
        subset['submitter_name'] = [f'Customer {cid}' for cid in customer_ids]

    # --- agent_name: asignar agentes de un pool ---
    if _find_col(subset, 'agent_name') is None:
        agent_indices = rng.randint(0, len(_SYNTH_AGENTS), size=n)
        subset = subset.copy() if not isinstance(subset, pd.DataFrame) else subset
        subset['agent_name'] = [_SYNTH_AGENTS[i][0] for i in agent_indices]
        subset['_agent_team'] = [_SYNTH_AGENTS[i][2] for i in agent_indices]

    # --- status: distribuir con pesos realistas ---
    if _find_col(subset, 'status') is None:
        subset = subset.copy() if not isinstance(subset, pd.DataFrame) else subset
        subset['status'] = rng.choice(_SYNTH_STATUSES, size=n, p=_STATUS_WEIGHTS)

    return subset


# ──────────────────────────────────────────────────────────────────────
# Inserción por nivel
# ──────────────────────────────────────────────────────────────────────

def _insert_tickets(conn, level: str, subset: pd.DataFrame):
    """Inserta todos los tickets de subset en la conexión según el nivel."""
    subset = _synthesize_missing_columns(subset)

    subj_col   = _find_col(subset, 'subject')
    body_col   = _find_col(subset, 'body')
    answer_col = _find_col(subset, 'answer')
    email_col  = _find_col(subset, 'submitter_email')
    name_col   = _find_col(subset, 'submitter_name')
    agent_col  = _find_col(subset, 'agent_name')
    prio_col   = _find_col(subset, 'priority')
    queue_col  = _find_col(subset, 'queue')
    date_col   = _find_col(subset, 'created_at')
    status_col = _find_col(subset, 'status')
    tag_cols   = [c for c in subset.columns if c.startswith('tag_')]
    has_tags_col = 'tags' in subset.columns

    # Pre-cachear dimensiones (incluye clientes) para evitar SELECTs repetidos
    _dim_cache: dict = {}

    def _cached_upsert_dim(table, name_col_db, key_col, value):
        if not value:
            return None
        cache_key = (table, value)
        if cache_key in _dim_cache:
            return _dim_cache[cache_key]
        result = _upsert_dim_text(conn, table, name_col_db, key_col, value)
        _dim_cache[cache_key] = result
        return result

    def _cached_language(lang_code):
        if not lang_code:
            return None
        cache_key = ('dim_language', lang_code)
        if cache_key in _dim_cache:
            return _dim_cache[cache_key]
        result = _upsert_language(conn, lang_code)
        _dim_cache[cache_key] = result
        return result

    def _cached_customer(name, email):
        norm_email = (email or 'unknown@unknown.com').lower()
        cache_key = ('dim_customer', norm_email)
        if cache_key in _dim_cache:
            return _dim_cache[cache_key]
        result = _upsert_customer(conn, name, email)
        _dim_cache[cache_key] = result
        return result

    # Insertar por lotes con transacción explícita
    conn.execute("BEGIN")
    for _, row in subset.iterrows():
        date_key     = _upsert_date(conn, row.get(date_col) if date_col else None)
        customer_key = _cached_customer(
            row.get(name_col) if name_col else None,
            row.get(email_col) if email_col else None)
        agent_key    = _upsert_agent(conn,
                                     row.get(agent_col) if agent_col else None,
                                     row.get('_agent_team') if '_agent_team' in row.index else None)
        prio_val = _clean_text_value(
            row.get(prio_col, 'normal') if prio_col else 'normal',
            default='normal',
        ).lower()
        status_val = _clean_text_value(
            row.get(status_col, 'open') if status_col else 'open',
            default='open',
        ).lower()
        pred_type = _clean_text_value(row.get('pred_type', ''), default='unknown')
        pred_lang = _clean_text_value(row.get('pred_language', ''), default='unknown')
        created_ts = _to_epoch(row.get(date_col) if date_col else None)

        subj_text = _truncate(
            _clean_text_value(row.get(subj_col, '') if subj_col else '', default=''),
            _MAX_SUBJECT_LEN,
        )
        body_text = _truncate(
            _clean_text_value(row.get(body_col, '') if body_col else '', default=''),
            _MAX_BODY_LEN,
        )
        answer_text = _truncate(
            _clean_text_value(row.get(answer_col, '') if answer_col else '', default=''),
            _MAX_ANSWER_LEN,
        )

        if level == 'BASIC':
            priority_key = _cached_upsert_dim('dim_priority', 'priority_name', 'priority_key', prio_val)
            status_key   = _cached_upsert_dim('dim_status',   'status_name',   'status_key',   status_val)
            conn.execute("""
                INSERT INTO fact_tickets
                (date_key, customer_key, agent_key, priority_key, status_key,
                 created_at, pred_type, pred_language)
                VALUES (?,?,?,?,?,?,?,?)
            """, (date_key, customer_key, agent_key, priority_key, status_key,
                  created_ts, pred_type, pred_lang))
            tid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute("INSERT INTO ticket_text VALUES (?,?,?)", (tid, subj_text, body_text))

        elif level == 'MEDIUM':
            type_key     = _cached_upsert_dim('dim_type',     'type_name',     'type_key',     pred_type)
            language_key = _cached_language(pred_lang)
            priority_key = _cached_upsert_dim('dim_priority', 'priority_name', 'priority_key', prio_val)
            status_key   = _cached_upsert_dim('dim_status',   'status_name',   'status_key',   status_val)
            conn.execute("""
                INSERT INTO fact_tickets
                (date_key, customer_key, agent_key, type_key, priority_key,
                 status_key, language_key, created_at)
                VALUES (?,?,?,?,?,?,?,?)
            """, (date_key, customer_key, agent_key, type_key, priority_key,
                  status_key, language_key, created_ts))
            tid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute("INSERT INTO ticket_text VALUES (?,?,?)", (tid, subj_text, body_text))

        elif level == 'PRO':
            type_key     = _cached_upsert_dim('dim_ticket_type', 'type_name',     'type_key',     pred_type)
            language_key = _cached_language(pred_lang)
            priority_key = _cached_upsert_dim('dim_priority',    'priority_name', 'priority_key', prio_val)
            status_key   = _cached_upsert_dim('dim_status',      'status_name',   'status_key',   status_val)
            queue_val = _clean_text_value(
                row.get(queue_col, 'general') if queue_col else 'general',
                default='general',
            )
            queue_key    = _cached_upsert_dim('dim_queue',        'queue_name',    'queue_key',    queue_val)
            wc_subj      = len(subj_text.split())
            wc_body      = len(body_text.split())
            conn.execute("""
                INSERT INTO fact_tickets
                (date_key, customer_key, agent_key, type_key, priority_key, queue_key,
                 language_key, status_key,
                 created_at, word_count_subject, word_count_body)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (date_key, customer_key, agent_key, type_key, priority_key, queue_key,
                  language_key, status_key, created_ts, wc_subj, wc_body))
            tid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute("INSERT INTO ticket_text VALUES (?,?,?,?)",
                         (tid, subj_text, body_text, answer_text))
            if tag_cols or has_tags_col:
                _insert_tags(conn, tid, tag_cols, row, tag_cache=_dim_cache)
    conn.commit()


# ──────────────────────────────────────────────────────────────────────
# Serialización
# ──────────────────────────────────────────────────────────────────────

def _conn_to_bytes(conn: sqlite3.Connection) -> bytes:
    """Vuelca la conexión SQLite en memoria a bytes comprimidos con LZMA.

    LZMA da ~30-40% mejor ratio que zlib en datos textuales.
    Prefijo b'LMDB' indica formato lzma; retrocompatible con ZLDB.
    """
    conn.commit()
    fd, tmp = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    try:
        bk = sqlite3.connect(tmp)
        conn.backup(bk)
        bk.execute("VACUUM")
        bk.close()
        with open(tmp, 'rb') as f:
            raw = f.read()
        return b'LMDB' + lzma.compress(raw, preset=9)
    finally:
        os.unlink(tmp)


def compress_db(raw: bytes) -> bytes:
    """Compress raw SQLite bytes with LZMA (used by all write-back paths)."""
    return b'LMDB' + lzma.compress(raw, preset=9)


def compress_db_fast(raw: bytes) -> bytes:
    """
    Fast compression for frequent incremental updates.

    Uses zlib instead of LZMA to reduce latency when re-writing the whole
    SQLite blob after inserting/updating a small number of tickets.
    Tradeoff: slightly larger payloads than the archival LMDB format.
    """
    return b'ZLDB' + zlib.compress(raw, level=3)


def decompress_db(data: bytes) -> bytes:
    """Descomprime bytes de un .db creado por _conn_to_bytes.
    Soporta LMDB (lzma), ZLDB (zlib), y raw SQLite (retrocompatible).
    """
    prefix = data[:4]
    if prefix == b'LMDB':
        return lzma.decompress(data[4:])
    if prefix == b'ZLDB':
        return zlib.decompress(data[4:])
    return data


def count_tickets_in_db_bytes(db_bytes: bytes) -> int:
    """Cuenta tickets en fact_tickets a partir de bytes comprimidos o raw del DB."""
    raw = decompress_db(db_bytes)
    fd, tmp = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    try:
        with open(tmp, 'wb') as fh:
            fh.write(raw)
        conn = sqlite3.connect(tmp)
        count = _count_fact_tickets(conn)
        conn.close()
        return count
    finally:
        os.unlink(tmp)


# ──────────────────────────────────────────────────────────────────────
# Punto de entrada
# ──────────────────────────────────────────────────────────────────────

# ──────────────────────────────────────────────────────────────────────
# Selección del nivel óptimo por estructura del CSV
# ──────────────────────────────────────────────────────────────────────

# Columnas que solo el esquema PRO puede almacenar
_PRO_ONLY_KEYS = ('queue', 'answer', 'version', 'tags')
# Columnas que requieren al menos MEDIUM
_MEDIUM_KEYS = ('ticket_type', 'language')


def _choose_optimal_level(df: pd.DataFrame) -> str:
    """
    Elige el nivel MÍNIMO de DW que pueda almacenar toda la información
    presente en el CSV, para ocupar el menor espacio posible.

    Lógica:
      - Si el CSV tiene tags (tag_* o columna 'tags'), queue, answer
        o version → PRO (único esquema con dim_queue, dim_tag, ticket_text.answer).
      - Si tiene tipo de ticket o idioma como columna explícita → MEDIUM
        (añade dim_type y dim_language).
      - En caso contrario → BASIC (dimensiones esenciales).
    """
    cols = {c.lower() for c in df.columns}

    # ¿Necesita PRO?
    has_tags = any(c.startswith('tag_') for c in cols) or 'tags' in cols
    needs_pro = has_tags or any(_find_col(df, k) is not None for k in _PRO_ONLY_KEYS)
    if needs_pro:
        return 'PRO'

    # ¿Necesita MEDIUM?
    needs_medium = any(_find_col(df, k) is not None for k in _MEDIUM_KEYS)
    if needs_medium:
        return 'MEDIUM'

    return 'BASIC'


class DWService:

    @staticmethod
    def create_databases(df_classified: pd.DataFrame, force_level: str | None = None) -> Dict[str, bytes]:
        """
        Recibe el DataFrame clasificado por ML.
        Analiza las columnas del CSV para determinar el nivel mínimo de DW
        que puede contener toda la información (BASIC / MEDIUM / PRO) y
        crea UNA sola base de datos con ese esquema y TODOS los tickets.

        Returns:
            dict { nivel_óptimo: bytes_del_db }  (siempre un solo elemento)
        """
        if df_classified.empty:
            return {}

        level = force_level or _choose_optimal_level(df_classified)
        conn = sqlite3.connect(':memory:')
        _SCHEMA_MAP[level](conn)
        _insert_tickets(conn, level, df_classified)
        result = {level: _conn_to_bytes(conn)}
        conn.close()
        return result
