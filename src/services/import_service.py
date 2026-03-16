import io
import json
import os
import re
import sqlite3
import tempfile

import pandas as pd


_TEXT_EXTENSIONS = {'.txt', '.log'}
_DELIMITED_EXTENSIONS = {'.csv', '.tsv'}
_JSON_EXTENSIONS = {'.json', '.jsonl', '.ndjson'}
_SQLITE_EXTENSIONS = {'.db', '.sqlite', '.sqlite3'}
_EXCEL_EXTENSIONS = {'.xlsx', '.xls'}

SUPPORTED_EXTENSIONS = (
    _DELIMITED_EXTENSIONS
    | _JSON_EXTENSIONS
    | _TEXT_EXTENSIONS
    | _SQLITE_EXTENSIONS
    | _EXCEL_EXTENSIONS
    | {'.parquet', '.sql'}
)

SUPPORTED_EXTENSIONS_TEXT = ', '.join(sorted(SUPPORTED_EXTENSIONS))


def _ext(filename: str) -> str:
    return '.' + filename.rsplit('.', 1)[-1].lower() if filename and '.' in filename else ''


def _decode_text(file_bytes: bytes) -> str:
    for enc in ('utf-8-sig', 'utf-8', 'latin-1'):
        try:
            return file_bytes.decode(enc)
        except Exception:
            continue
    return file_bytes.decode('utf-8', errors='ignore')


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    cols = []
    for c in df.columns:
        name = str(c).strip().lower()
        name = re.sub(r'[\s\-]+', '_', name)
        name = re.sub(r'[^\w]+', '_', name)
        name = re.sub(r'_+', '_', name).strip('_')
        cols.append(name or 'col')

    # Evita colisiones tras normalizar (col, col_2, col_3...)
    seen = {}
    unique_cols = []
    for c in cols:
        seen[c] = seen.get(c, 0) + 1
        unique_cols.append(c if seen[c] == 1 else f'{c}_{seen[c]}')

    out = df.copy()
    out.columns = unique_cols
    return out


def _ensure_text_columns(df: pd.DataFrame) -> pd.DataFrame:
    cols = set(df.columns)
    has_subject = any(c in cols for c in ('subject', 'title', 'summary', 'asunto'))
    has_body = any(c in cols for c in ('body', 'description', 'message', 'content', 'descripcion', 'mensaje'))

    if has_subject and has_body:
        return df

    text_cols = [
        c for c in df.columns
        if pd.api.types.is_string_dtype(df[c]) or df[c].dtype == object
    ]

    if text_cols:
        primary = text_cols[0]
        if not has_body:
            df = df.copy()
            df['body'] = df[primary].fillna('').astype(str)
            has_body = True
        if not has_subject:
            if 'body' in df.columns:
                source = df['body']
            else:
                source = df[primary].fillna('').astype(str)
            df = df.copy()
            df['subject'] = source.str.slice(0, 80)
        return df

    # Sin columnas textuales: genera columnas mínimas para pasar por ML
    out = df.copy()
    out['subject'] = ''
    out['body'] = ''
    return out


def _read_json(file_bytes: bytes) -> pd.DataFrame:
    text = _decode_text(file_bytes).strip()
    if not text:
        return pd.DataFrame()

    obj = json.loads(text)
    if isinstance(obj, list):
        return pd.json_normalize(obj)

    if isinstance(obj, dict):
        if isinstance(obj.get('tickets'), list):
            return pd.json_normalize(obj['tickets'])

        for value in obj.values():
            if isinstance(value, list) and value and isinstance(value[0], dict):
                return pd.json_normalize(value)

        return pd.json_normalize([obj])

    raise ValueError('Formato JSON no soportado: se esperaba objeto o lista')


def _read_json_lines(file_bytes: bytes) -> pd.DataFrame:
    text = _decode_text(file_bytes)
    rows = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return pd.json_normalize(rows)


def _read_txt(file_bytes: bytes) -> pd.DataFrame:
    text = _decode_text(file_bytes)

    # Intento 1: detectar delimitador automáticamente
    try:
        df_guess = pd.read_csv(io.StringIO(text), sep=None, engine='python')
        if not df_guess.empty and df_guess.shape[1] > 1:
            return df_guess
    except Exception:
        pass

    # Intento 2: cada línea no vacía es un ticket
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return pd.DataFrame()

    return pd.DataFrame({
        'subject': [ln[:80] for ln in lines],
        'body': lines,
    })


def _read_sqlite_bytes(file_bytes: bytes) -> pd.DataFrame:
    tmp_path = None
    conn = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        conn = sqlite3.connect(tmp_path)
        table = _pick_best_table(conn)
        if not table:
            raise ValueError('No se encontró ninguna tabla usable en la base SQLite')

        quoted = table.replace('"', '""')
        return pd.read_sql_query(f'SELECT * FROM "{quoted}"', conn)
    finally:
        if conn is not None:
            conn.close()
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _read_sql(file_bytes: bytes) -> pd.DataFrame:
    script = _decode_text(file_bytes)
    conn = sqlite3.connect(':memory:')
    try:
        conn.executescript(script)
        table = _pick_best_table(conn)
        if not table:
            raise ValueError('El SQL no creó tablas con datos')
        quoted = table.replace('"', '""')
        return pd.read_sql_query(f'SELECT * FROM "{quoted}"', conn)
    except sqlite3.DatabaseError as exc:
        raise ValueError(
            'No se pudo interpretar el SQL. Usa SQL compatible con SQLite o exporta a CSV/JSON.'
        ) from exc
    finally:
        conn.close()


def _pick_best_table(conn: sqlite3.Connection) -> str | None:
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [r[0] for r in cur.fetchall()]
    if not tables:
        return None

    aliases_subject = {'subject', 'title', 'summary', 'asunto'}
    aliases_body = {'body', 'description', 'message', 'content', 'descripcion', 'mensaje'}
    bonus_cols = {'priority', 'queue', 'language', 'status', 'created_at', 'ticket_type', 'tags'}

    best = None
    best_score = -1
    for t in tables:
        quoted = t.replace('"', '""')
        cols = []
        for r in conn.execute(f'PRAGMA table_info("{quoted}")').fetchall():
            cols.append(str(r[1]).strip().lower())

        score = 0
        if any(c in aliases_subject for c in cols):
            score += 5
        if any(c in aliases_body for c in cols):
            score += 5
        score += sum(1 for c in cols if c in bonus_cols)

        try:
            row_count = conn.execute(f'SELECT COUNT(1) FROM "{quoted}"').fetchone()[0]
        except Exception:
            row_count = 0
        if row_count > 0:
            score += 2

        if score > best_score:
            best = t
            best_score = score

    return best


class ImportService:

    @staticmethod
    def extension(filename: str) -> str:
        return _ext(filename)

    @staticmethod
    def is_supported(filename: str) -> bool:
        return _ext(filename) in SUPPORTED_EXTENSIONS

    @staticmethod
    def parse_to_dataframe(file_bytes: bytes, filename: str) -> pd.DataFrame:
        if not file_bytes:
            raise ValueError('El archivo está vacío')

        ext = _ext(filename)
        if ext not in SUPPORTED_EXTENSIONS:
            raise ValueError(f'Formato no soportado ({ext or "sin extensión"}). Admitidos: {SUPPORTED_EXTENSIONS_TEXT}')

        if ext == '.csv':
            df = pd.read_csv(io.BytesIO(file_bytes))
        elif ext == '.tsv':
            df = pd.read_csv(io.BytesIO(file_bytes), sep='\t')
        elif ext == '.parquet':
            try:
                df = pd.read_parquet(io.BytesIO(file_bytes))
            except ImportError as exc:
                raise ValueError('Soporte Parquet no disponible. Instala pyarrow.') from exc
            except Exception as exc:
                raise ValueError(f'No se pudo leer el Parquet: {exc}') from exc
        elif ext == '.xlsx':
            try:
                df = pd.read_excel(io.BytesIO(file_bytes), engine='openpyxl')
            except ImportError as exc:
                raise ValueError('Soporte Excel no disponible. Instala openpyxl y xlrd.') from exc
            except Exception as exc:
                raise ValueError(f'No se pudo leer el Excel (.xlsx): {exc}') from exc
        elif ext == '.xls':
            try:
                df = pd.read_excel(io.BytesIO(file_bytes), engine='xlrd')
            except ImportError as exc:
                raise ValueError('Soporte Excel no disponible. Instala openpyxl y xlrd.') from exc
            except Exception as exc:
                raise ValueError(f'No se pudo leer el Excel (.xls): {exc}') from exc
        elif ext == '.json':
            df = _read_json(file_bytes)
        elif ext in {'.jsonl', '.ndjson'}:
            df = _read_json_lines(file_bytes)
        elif ext in _TEXT_EXTENSIONS:
            df = _read_txt(file_bytes)
        elif ext in _SQLITE_EXTENSIONS:
            df = _read_sqlite_bytes(file_bytes)
        elif ext == '.sql':
            df = _read_sql(file_bytes)
        else:
            raise ValueError(f'Formato no soportado: {ext}')

        if df is None or df.empty:
            raise ValueError('El archivo no contiene filas de tickets')

        df = _normalize_columns(df)
        df = _ensure_text_columns(df)
        return df
