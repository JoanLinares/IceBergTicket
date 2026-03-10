"""
DWService — Crea bases de datos SQLite con los tickets clasificados.

Para cada nivel (BASIC / MEDIUM / PRO) que tenga tickets:
  1. Crea un SQLite en memoria con el esquema del nivel correspondiente.
  2. Inserta dims (dim_date, dim_customer, dim_agent, dim_type, dim_language,
     dim_priority, dim_status) con lógica INSERT OR IGNORE.
  3. Inserta fact_tickets y ticket_text referenciando las dims.
  4. En PRO, además inserta dim_tag + bridge_ticket_tags.
  5. Serializa el .db a bytes (vía fichero temporal).

Returns:
    dict { 'BASIC': bytes, 'MEDIUM': bytes, 'PRO': bytes }  (solo niveles con datos)
"""
import os
import sqlite3
import tempfile
import pandas as pd
from datetime import datetime
from typing import Dict

from src.services.ml_service import _find_col, _COL_ALIASES

LANG_NAMES = {
    'en': 'English', 'es': 'Español', 'de': 'Deutsch',
    'fr': 'Français', 'pt': 'Português',
}


# ──────────────────────────────────────────────────────────────────────
# Creación de esquemas
# ──────────────────────────────────────────────────────────────────────

def _basic_schema(conn):
    conn.executescript("""
        PRAGMA foreign_keys = OFF;
        CREATE TABLE IF NOT EXISTS dim_date (
            date_key INTEGER PRIMARY KEY,
            date TEXT, year INTEGER, month INTEGER,
            month_name TEXT, day INTEGER, day_name TEXT, is_weekend INTEGER
        );
        CREATE TABLE IF NOT EXISTS dim_customer (
            customer_key INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT, email TEXT UNIQUE, created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS dim_agent (
            agent_key INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_name TEXT, email TEXT, team TEXT
        );
        CREATE TABLE IF NOT EXISTS dim_priority (
            priority_key INTEGER PRIMARY KEY AUTOINCREMENT,
            priority_name TEXT UNIQUE, level INTEGER
        );
        CREATE TABLE IF NOT EXISTS dim_status (
            status_key INTEGER PRIMARY KEY AUTOINCREMENT,
            status_name TEXT UNIQUE, category TEXT
        );
        CREATE TABLE IF NOT EXISTS fact_tickets (
            ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_key INTEGER, customer_key INTEGER, agent_key INTEGER,
            priority_key INTEGER, status_key INTEGER,
            submitter_email TEXT, submitter_name TEXT,
            created_at TEXT, pred_type TEXT, pred_language TEXT
        );
        CREATE TABLE IF NOT EXISTS ticket_text (
            ticket_id INTEGER PRIMARY KEY,
            subject TEXT, description TEXT
        );
    """)


def _medium_schema(conn):
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
            agent_name TEXT, email TEXT, team TEXT
        );
        CREATE TABLE IF NOT EXISTS dim_type (
            type_key INTEGER PRIMARY KEY AUTOINCREMENT,
            type_name TEXT UNIQUE, type_description TEXT
        );
        CREATE TABLE IF NOT EXISTS dim_priority (
            priority_key INTEGER PRIMARY KEY AUTOINCREMENT,
            priority_name TEXT UNIQUE, level INTEGER, sla_hours INTEGER
        );
        CREATE TABLE IF NOT EXISTS dim_status (
            status_key INTEGER PRIMARY KEY AUTOINCREMENT,
            status_name TEXT UNIQUE, category TEXT, is_final INTEGER
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
            submitter_email TEXT, submitter_name TEXT,
            created_at TEXT, sla_breached INTEGER,
            pred_type TEXT, pred_language TEXT
        );
        CREATE TABLE IF NOT EXISTS ticket_text (
            ticket_id INTEGER PRIMARY KEY,
            subject TEXT, description TEXT, internal_notes TEXT
        );
    """)


def _pro_schema(conn):
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
            customer_name TEXT, email TEXT UNIQUE,
            company_name TEXT, account_type TEXT
        );
        CREATE TABLE IF NOT EXISTS dim_agent (
            agent_key INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_name TEXT, email TEXT, team TEXT, skill_level TEXT
        );
        CREATE TABLE IF NOT EXISTS dim_ticket_type (
            type_key INTEGER PRIMARY KEY AUTOINCREMENT,
            type_name TEXT UNIQUE, type_description TEXT
        );
        CREATE TABLE IF NOT EXISTS dim_priority (
            priority_key INTEGER PRIMARY KEY AUTOINCREMENT,
            priority_name TEXT UNIQUE, priority_level INTEGER
        );
        CREATE TABLE IF NOT EXISTS dim_queue (
            queue_key INTEGER PRIMARY KEY AUTOINCREMENT,
            queue_name TEXT UNIQUE, department TEXT, active_flag INTEGER
        );
        CREATE TABLE IF NOT EXISTS dim_language (
            language_key INTEGER PRIMARY KEY AUTOINCREMENT,
            language_code TEXT UNIQUE, language_name TEXT
        );
        CREATE TABLE IF NOT EXISTS dim_status (
            status_key INTEGER PRIMARY KEY AUTOINCREMENT,
            status_name TEXT UNIQUE, is_open INTEGER, is_final INTEGER
        );
        CREATE TABLE IF NOT EXISTS dim_tag (
            tag_key INTEGER PRIMARY KEY AUTOINCREMENT,
            tag_name TEXT UNIQUE, tag_category TEXT
        );
        CREATE TABLE IF NOT EXISTS fact_tickets (
            ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_key INTEGER, customer_key INTEGER, agent_key INTEGER,
            type_key INTEGER, priority_key INTEGER, queue_key INTEGER,
            language_key INTEGER, status_key INTEGER,
            submitter_email TEXT, submitter_name TEXT,
            created_at TEXT, response_count INTEGER,
            escalated_flag INTEGER, sla_breached_flag INTEGER,
            word_count_subject INTEGER, word_count_body INTEGER,
            pred_type TEXT, pred_language TEXT
        );
        CREATE TABLE IF NOT EXISTS bridge_ticket_tags (
            ticket_id INTEGER, tag_key INTEGER, tag_order INTEGER,
            PRIMARY KEY (ticket_id, tag_key)
        );
        CREATE TABLE IF NOT EXISTS ticket_text (
            ticket_id INTEGER PRIMARY KEY,
            subject TEXT, body TEXT, answer TEXT, internal_notes TEXT
        );
    """)


_SCHEMA_MAP = {'BASIC': _basic_schema, 'MEDIUM': _medium_schema, 'PRO': _pro_schema}


# ──────────────────────────────────────────────────────────────────────
# Helpers de dimensiones
# ──────────────────────────────────────────────────────────────────────

def _upsert_date(conn, dt_val) -> int:
    """Inserta o recupera date_key (YYYYMMDD) para una fecha."""
    try:
        d = pd.to_datetime(dt_val)
    except Exception:
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


def _insert_tags(conn, ticket_id: int, tag_cols: list, row: pd.Series):
    """Inserta tags activas (columnas tag_* = True/1) en dim_tag + bridge."""
    for order, col in enumerate(tag_cols):
        val = row.get(col)
        if val and str(val).strip().lower() not in ('false', '0', 'nan', ''):
            tag_name = col.replace('tag_', '').replace('_', ' ')
            conn.execute(
                "INSERT OR IGNORE INTO dim_tag (tag_name, tag_category) VALUES (?,?)",
                (tag_name, 'auto')
            )
            tag_row = conn.execute(
                "SELECT tag_key FROM dim_tag WHERE tag_name=?", (tag_name,)
            ).fetchone()
            if tag_row:
                conn.execute(
                    "INSERT OR IGNORE INTO bridge_ticket_tags VALUES (?,?,?)",
                    (ticket_id, tag_row[0], order)
                )


# ──────────────────────────────────────────────────────────────────────
# Inserción por nivel
# ──────────────────────────────────────────────────────────────────────

def _insert_tickets(conn, level: str, subset: pd.DataFrame):
    """Inserta todos los tickets de subset en la conexión según el nivel."""
    subj_col   = _find_col(subset, 'subject')
    body_col   = _find_col(subset, 'body')
    email_col  = _find_col(subset, 'submitter_email')
    name_col   = _find_col(subset, 'submitter_name')
    agent_col  = _find_col(subset, 'agent_name')
    prio_col   = _find_col(subset, 'priority')
    queue_col  = _find_col(subset, 'queue')
    date_col   = _find_col(subset, 'created_at')
    status_col = _find_col(subset, 'status')
    tag_cols   = [c for c in subset.columns if c.startswith('tag_')]

    for _, row in subset.iterrows():
        date_key     = _upsert_date(conn, row.get(date_col) if date_col else None)
        customer_key = _upsert_customer(conn,
                                        row.get(name_col) if name_col else None,
                                        row.get(email_col) if email_col else None)
        agent_key    = _upsert_agent(conn,
                                     row.get(agent_col) if agent_col else None)
        prio_val     = str(row.get(prio_col, 'normal')).lower() if prio_col else 'normal'
        status_val   = str(row.get(status_col, 'open')).lower() if status_col else 'open'
        pred_type    = str(row.get('pred_type', ''))
        pred_lang    = str(row.get('pred_language', ''))

        subj_text = str(row.get(subj_col, '')) if subj_col else ''
        body_text = str(row.get(body_col, '')) if body_col else ''

        if level == 'BASIC':
            priority_key = _upsert_dim_text(conn, 'dim_priority', 'priority_name', 'priority_key', prio_val)
            status_key   = _upsert_dim_text(conn, 'dim_status',   'status_name',   'status_key',   status_val)
            conn.execute("""
                INSERT INTO fact_tickets
                (date_key, customer_key, agent_key, priority_key, status_key,
                 submitter_email, submitter_name, created_at, pred_type, pred_language)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (date_key, customer_key, agent_key, priority_key, status_key,
                  row.get(email_col) if email_col else None,
                  row.get(name_col) if name_col else None,
                  row.get(date_col) if date_col else datetime.now().isoformat(),
                  pred_type, pred_lang))
            tid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute("INSERT INTO ticket_text VALUES (?,?,?)", (tid, subj_text, body_text))

        elif level == 'MEDIUM':
            type_key     = _upsert_dim_text(conn, 'dim_type',     'type_name',     'type_key',     pred_type)
            language_key = _upsert_language(conn, pred_lang)
            priority_key = _upsert_dim_text(conn, 'dim_priority', 'priority_name', 'priority_key', prio_val)
            status_key   = _upsert_dim_text(conn, 'dim_status',   'status_name',   'status_key',   status_val)
            conn.execute("""
                INSERT INTO fact_tickets
                (date_key, customer_key, agent_key, type_key, priority_key,
                 status_key, language_key, submitter_email, submitter_name,
                 created_at, pred_type, pred_language)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (date_key, customer_key, agent_key, type_key, priority_key,
                  status_key, language_key,
                  row.get(email_col) if email_col else None,
                  row.get(name_col) if name_col else None,
                  row.get(date_col) if date_col else datetime.now().isoformat(),
                  pred_type, pred_lang))
            tid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute("INSERT INTO ticket_text VALUES (?,?,?,?)", (tid, subj_text, body_text, None))

        elif level == 'PRO':
            type_key     = _upsert_dim_text(conn, 'dim_ticket_type', 'type_name',     'type_key',     pred_type)
            language_key = _upsert_language(conn, pred_lang)
            priority_key = _upsert_dim_text(conn, 'dim_priority',    'priority_name', 'priority_key', prio_val)
            status_key   = _upsert_dim_text(conn, 'dim_status',      'status_name',   'status_key',   status_val)
            queue_val    = str(row.get(queue_col, 'general')) if queue_col else 'general'
            queue_key    = _upsert_dim_text(conn, 'dim_queue',        'queue_name',    'queue_key',    queue_val)
            wc_subj      = len(subj_text.split())
            wc_body      = len(body_text.split())
            conn.execute("""
                INSERT INTO fact_tickets
                (date_key, customer_key, agent_key, type_key, priority_key, queue_key,
                 language_key, status_key, submitter_email, submitter_name,
                 created_at, word_count_subject, word_count_body,
                 pred_type, pred_language)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (date_key, customer_key, agent_key, type_key, priority_key, queue_key,
                  language_key, status_key,
                  row.get(email_col) if email_col else None,
                  row.get(name_col) if name_col else None,
                  row.get(date_col) if date_col else datetime.now().isoformat(),
                  wc_subj, wc_body, pred_type, pred_lang))
            tid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute("INSERT INTO ticket_text VALUES (?,?,?,?,?)", (tid, subj_text, body_text, None, None))
            if tag_cols:
                _insert_tags(conn, tid, tag_cols, row)


# ──────────────────────────────────────────────────────────────────────
# Serialización
# ──────────────────────────────────────────────────────────────────────

def _conn_to_bytes(conn: sqlite3.Connection) -> bytes:
    """Vuelca la conexión SQLite en memoria a bytes vía fichero temporal."""
    conn.commit()
    fd, tmp = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    try:
        bk = sqlite3.connect(tmp)
        conn.backup(bk)
        bk.close()
        with open(tmp, 'rb') as f:
            return f.read()
    finally:
        os.unlink(tmp)


# ──────────────────────────────────────────────────────────────────────
# Punto de entrada
# ──────────────────────────────────────────────────────────────────────

class DWService:

    @staticmethod
    def create_databases(df_classified: pd.DataFrame) -> Dict[str, bytes]:
        """
        Recibe el DataFrame con columnas pred_type, pred_language, pred_level
        y devuelve { nivel: bytes_del_db } para cada nivel con al menos un ticket.
        """
        result = {}
        for level in ('BASIC', 'MEDIUM', 'PRO'):
            subset = df_classified[df_classified['pred_level'] == level].copy()
            if subset.empty:
                continue
            conn = sqlite3.connect(':memory:')
            _SCHEMA_MAP[level](conn)
            _insert_tickets(conn, level, subset)
            result[level] = _conn_to_bytes(conn)
            conn.close()
        return result
