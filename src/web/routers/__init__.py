import re
import secrets
from functools import wraps

from flask import (
    Blueprint, render_template, redirect, url_for,
    request, session, flash, jsonify,
)
from werkzeug.security import generate_password_hash
import jwt

from src.api.models.file_model import FileModel, UserFileModel
from src.api.models.saved_query_model import SavedQueryModel
from src.api.models.user_model import UserModel
from src.services.auth_service import AuthService
from src.services.JWT_service import JWT_SECRET
from src.services.ml_service import MLService
from src.services.dw_service import DWService, extract_for_upgrade, count_tickets_in_db_bytes
from src.services.file_service import FileService
from src.services.db_session_service import DBSessionService, _fetch_db
from src.services.import_service import ImportService, SUPPORTED_EXTENSIONS_TEXT

web_blueprint = Blueprint('web', __name__)


# ── Helpers ────────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return redirect(url_for('web.login_page'))
        return f(*args, **kwargs)
    return decorated


def _extract_level(filename: str):
    m = re.search(r'_(BASIC|MEDIUM|PRO)\.db$', filename or '', re.IGNORECASE)
    return m.group(1).upper() if m else None


def _display_name(filename: str) -> str:
    """Quita la extensión .db y el sufijo _LEVEL para mostrar en el frontend."""
    name = re.sub(r'\.db$', '', filename or '', flags=re.IGNORECASE)
    name = re.sub(r'_(BASIC|MEDIUM|PRO)$', '', name, flags=re.IGNORECASE)
    return name or filename


def _fmt_bytes(n):
    if n < 1024:      return f"{n} B"
    if n < 1_048_576: return f"{n/1024:.1f} KB"
    return f"{n/1_048_576:.1f} MB"


def _check_access(file_id):
    return FileModel.check_user_access(file_id, session['user_id'])


# ── Auth ───────────────────────────────────────────────────────────────────

@web_blueprint.route('/')
def index():
    if session.get('user_id'):
        return redirect(url_for('web.dashboard'))
    return redirect(url_for('web.login_page'))


@web_blueprint.route('/login', methods=['GET', 'POST'])
def login_page():
    if session.get('user_id'):
        return redirect(url_for('web.dashboard'))

    if request.method == 'POST':
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        if not email or not password:
            flash('Rellena todos los campos', 'error')
            return render_template('auth/login.html')

        result, error = AuthService.login(email, password)
        if error:
            flash('Credenciales incorrectas', 'error')
            return render_template('auth/login.html')

        payload  = jwt.decode(result['access_token'], JWT_SECRET, algorithms=['HS256'])
        user_id  = payload['user_id']
        username = UserModel.get_username_by_id(user_id) or email.split('@')[0]

        session['user_id']  = user_id
        session['username'] = username
        return redirect(url_for('web.dashboard'))

    return render_template('auth/login.html')


@web_blueprint.route('/register', methods=['GET', 'POST'])
def register_page():
    if session.get('user_id'):
        return redirect(url_for('web.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        if not username or not email or not password:
            flash('Rellena todos los campos', 'error')
            return render_template('auth/register.html')

        user_id, error = AuthService.register(username, email, password)
        if error:
            flash(error, 'error')
            return render_template('auth/register.html')

        session['user_id']  = user_id
        session['username'] = username
        return redirect(url_for('web.dashboard'))

    return render_template('auth/register.html')


@web_blueprint.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('web.login_page'))


# ── Dashboard ──────────────────────────────────────────────────────────────

@web_blueprint.route('/dashboard')
@login_required
def dashboard():
    rows = FileModel.get_accessible_by_user(session['user_id'])
    files = [
        {
            'id':         r[0],
            'filename':   r[1],
            'display_name': _display_name(r[1]),
            'level':      _extract_level(r[1]),
            'file_type':  r[2],
            'size_fmt':   _fmt_bytes(r[3]),
            'status':     r[4],
            'created_at': r[5],
            'is_owner':   r[6],
        }
        for r in rows
    ]
    upload_result = session.pop('upload_result', None)
    return render_template('dashboard.html', files=files, upload_result=upload_result)


@web_blueprint.route('/dashboard/upload', methods=['POST'])
@login_required
def upload():
    if 'file' not in request.files:
        flash('No se encontró el archivo', 'error')
        return redirect(url_for('web.dashboard'))

    f = request.files['file']
    if not f.filename:
        flash('Nombre de archivo vacío', 'error')
        return redirect(url_for('web.dashboard'))

    if not ImportService.is_supported(f.filename):
        flash(f'Formato no soportado. Admitidos: {SUPPORTED_EXTENSIONS_TEXT}', 'error')
        return redirect(url_for('web.dashboard'))

    file_bytes = f.read()
    if not file_bytes:
        flash('El archivo está vacío', 'error')
        return redirect(url_for('web.dashboard'))

    try:
        df_input = ImportService.parse_to_dataframe(file_bytes, f.filename)
    except ValueError as exc:
        flash(str(exc), 'error')
        return redirect(url_for('web.dashboard'))
    except Exception as exc:
        flash(f'Error leyendo archivo: {exc}', 'error')
        return redirect(url_for('web.dashboard'))

    try:
        df = MLService.get_instance().classify_dataframe(df_input)
    except Exception as exc:
        flash(f'Error en clasificación ML: {exc}', 'error')
        return redirect(url_for('web.dashboard'))

    try:
        db_files = DWService.create_databases(df)
    except Exception as exc:
        flash(f'Error creando bases de datos: {exc}', 'error')
        return redirect(url_for('web.dashboard'))

    if not db_files:
        flash('No se generó ninguna base de datos (CSV sin tickets válidos)', 'error')
        return redirect(url_for('web.dashboard'))

    base_name = request.form.get('db_name', '').strip()
    if not base_name:
        base_name = f.filename.rsplit('.', 1)[0]
    # Sanitizar: solo alfanuméricos, espacios, guiones y underscores
    base_name = re.sub(r'[^\w\s\-]', '', base_name).strip()
    if not base_name:
        base_name = 'database'
    created   = []

    for level, db_bytes in db_files.items():
        filename = f"{base_name}_{level}.db"
        try:
            meta = FileService.upload(db_bytes, filename, session['user_id'])
        except Exception as exc:
            flash(f'Error subiendo {level}: {exc}', 'error')
            continue

        plain_api_key = secrets.token_urlsafe(32)
        file_id, _ = FileModel.create(
            owner_user_id=session['user_id'],
            filename=meta['filename'],
            file_type=meta['file_type'],
            storage_path=meta['storage_path'],
            size_bytes=meta['size_bytes'],
            sha256=meta['sha256'],
            enc_nonce=meta['enc_nonce'],
            api_password_hash=generate_password_hash(plain_api_key),
        )
        UserFileModel.create(user_id=session['user_id'], file_id=file_id, is_owner=True)

        created.append({
            'filename': filename,
            'level':    level,
            'n_tickets': len(df),
            'api_key':  plain_api_key,
            'file_id':  file_id,
        })

    if created:
        session['upload_result'] = created
        flash(f'Base de datos {created[0]["level"]} creada con {created[0]["n_tickets"]} tickets', 'success')

    return redirect(url_for('web.dashboard'))


@web_blueprint.route('/explorer/<int:file_id>/rename', methods=['POST'])
@login_required
def rename_db(file_id):
    row = _check_access(file_id)
    if not row or not row[9]:
        return jsonify({'error': 'Solo el propietario puede renombrar'}), 403

    body = request.get_json(silent=True) or {}
    new_name = str(body.get('name', '')).strip()
    if not new_name:
        return jsonify({'error': 'El nombre es obligatorio'}), 400

    # Sanitizar
    new_name = re.sub(r'[^\w\s\-]', '', new_name).strip()
    if not new_name:
        return jsonify({'error': 'Nombre no válido'}), 400

    # Preservar sufijo _LEVEL.db
    old_filename = row[1]
    level = _extract_level(old_filename)
    suffix = f'_{level}.db' if level else '.db'
    new_filename = f'{new_name}{suffix}'

    ok = FileModel.rename(file_id, session['user_id'], new_filename)
    if not ok:
        return jsonify({'error': 'No se pudo renombrar'}), 500

    return jsonify({'filename': new_filename, 'display_name': _display_name(new_filename)})


@web_blueprint.route('/explorer/<int:file_id>/upgrade', methods=['POST'])
@login_required
def upgrade_db(file_id):
    """Actualiza el nivel del DW (BASIC→MEDIUM, BASIC→PRO, MEDIUM→PRO) sin perder datos."""
    row = _check_access(file_id)
    if not row or not row[9]:
        return jsonify({'error': 'Solo el propietario puede actualizar el nivel'}), 403

    data   = request.get_json(silent=True) or {}
    target = data.get('target_level', '').upper()
    if target not in ('MEDIUM', 'PRO'):
        return jsonify({'error': 'Nivel inválido. Solo se admite MEDIUM o PRO'}), 400

    _LEVELS = {'BASIC': 1, 'MEDIUM': 2, 'PRO': 3}

    try:
        db_bytes, meta = _fetch_db(file_id, session['user_id'])
    except PermissionError as exc:
        return jsonify({'error': str(exc)}), 403
    except Exception as exc:
        return jsonify({'error': f'Error accediendo a la base de datos: {exc}'}), 500

    try:
        current_level, df, upgrade_stats = extract_for_upgrade(db_bytes, include_stats=True)
    except Exception as exc:
        return jsonify({'error': f'Error leyendo la base de datos: {exc}'}), 500

    source_tickets = upgrade_stats.get('source_ticket_count', 0)
    extracted_tickets = upgrade_stats.get('extracted_ticket_count', 0)
    dropped_tickets = upgrade_stats.get('dropped_ticket_count', 0)

    if source_tickets > 0 and extracted_tickets != source_tickets:
        return jsonify({
            'error': (
                'Se detectó inconsistencia al extraer tickets para upgrade. '
                'No se aplicaron cambios para evitar pérdida de datos.'
            ),
            'integrity': {
                'source_ticket_count': source_tickets,
                'extracted_ticket_count': extracted_tickets,
                'dropped_ticket_count': dropped_tickets,
            },
        }), 409

    if _LEVELS.get(target, 0) <= _LEVELS.get(current_level, 0):
        return jsonify({
            'error': f'Ya estás en nivel {current_level}. Solo se permiten mejoras, no degradaciones.'
        }), 400

    try:
        # Re-clasifica para reconstruir el DW objetivo con predicciones ML actuales.
        df = MLService.get_instance().classify_dataframe(df)
    except Exception as exc:
        return jsonify({'error': f'Error en clasificación ML durante upgrade: {exc}'}), 500

    try:
        new_db_files = DWService.create_databases(df, force_level=target)
        new_db_bytes = new_db_files.get(target)
        if not new_db_bytes:
            return jsonify({'error': 'No se pudo generar la base de datos de destino'}), 500
        rebuilt_tickets = count_tickets_in_db_bytes(new_db_bytes)
        if rebuilt_tickets != extracted_tickets:
            return jsonify({
                'error': (
                    'La base reconstruida no conserva el mismo número de tickets. '
                    'Upgrade cancelado para proteger la integridad de datos.'
                ),
                'integrity': {
                    'source_ticket_count': source_tickets,
                    'extracted_ticket_count': extracted_tickets,
                    'rebuilt_ticket_count': rebuilt_tickets,
                },
            }), 409
    except Exception as exc:
        return jsonify({'error': f'Error creando la base de datos actualizada: {exc}'}), 500

    try:
        ow = FileService.upload_overwrite(new_db_bytes, meta['storage_path'])
    except Exception as exc:
        return jsonify({'error': f'Error guardando la base de datos: {exc}'}), 500

    FileModel.update_encryption_meta(file_id, ow['sha256'], ow['enc_nonce'], ow['size_bytes'])

    current_filename = row[1]
    new_filename = re.sub(
        r'_(BASIC|MEDIUM|PRO)(\.db)$',
        lambda m: f'_{target}{m.group(2)}',
        current_filename,
        flags=re.IGNORECASE,
    )
    if new_filename != current_filename:
        FileModel.rename(file_id, session['user_id'], new_filename)

    return jsonify({
        'ok':             True,
        'previous_level': current_level,
        'new_level':      target,
        'new_size':       ow['size_bytes'],
        'new_size_fmt':   _fmt_bytes(ow['size_bytes']),
        'new_filename':   _display_name(new_filename),
        'integrity': {
            'source_ticket_count': source_tickets,
            'extracted_ticket_count': extracted_tickets,
            'rebuilt_ticket_count': rebuilt_tickets,
        },
        'preserved_credentials': {
            'api_key_hash': True,
            'share_code': True,
        },
    })


@web_blueprint.route('/dashboard/join', methods=['POST'])
@login_required
def join():
    code = request.form.get('share_code', '').strip().upper()
    if not code:
        flash('Introduce un código', 'error')
        return redirect(url_for('web.dashboard'))

    file_row = FileModel.get_by_share_code(code)
    if not file_row:
        flash('Código no válido o caducado', 'error')
        return redirect(url_for('web.dashboard'))

    file_id, owner_user_id, filename, _ = file_row

    if owner_user_id == session['user_id']:
        flash('Ya eres el propietario de esta base de datos', 'error')
        return redirect(url_for('web.dashboard'))

    if FileModel.check_user_access(file_id, session['user_id']):
        flash('Ya tienes acceso a esta base de datos', 'error')
        return redirect(url_for('web.dashboard'))

    UserFileModel.create(
        user_id=session['user_id'], file_id=file_id,
        is_owner=False, invited_by=owner_user_id,
    )
    flash(f'Te has unido a {filename}', 'success')
    return redirect(url_for('web.dashboard'))


# ── Explorer ───────────────────────────────────────────────────────────────

@web_blueprint.route('/explorer/<int:file_id>')
@login_required
def explorer(file_id):
    row = _check_access(file_id)
    if not row:
        flash('Base de datos no encontrada o sin acceso', 'error')
        return redirect(url_for('web.dashboard'))

    file_info = {
        'id':             row[0],
        'filename':       row[1],
        'display_name':   _display_name(row[1]),
        'level':          _extract_level(row[1]),
        'size_fmt':       _fmt_bytes(row[3]),
        'status':         row[4],
        'created_at':     row[5],
        'has_share_code': row[8] is not None,
        'share_code':     row[8] or '',
        'is_owner':       row[9],
    }

    try:
        tables = DBSessionService.list_tables(file_id, session['user_id'])
    except Exception:
        tables = []

    initial_table = None
    initial_data  = None
    if tables:
        initial_table = tables[0]['name']
        try:
            initial_data = DBSessionService.get_table_data(
                file_id, session['user_id'], initial_table, 1, 50,
            )
        except Exception:
            initial_data = None

    return render_template(
        'explorer.html',
        file=file_info,
        tables=tables,
        initial_table=initial_table,
        initial_data=initial_data,
    )


# ── Explorer — AJAX endpoints ──────────────────────────────────────────────

@web_blueprint.route('/explorer/<int:file_id>/table/<string:table_name>')
@login_required
def table_data(file_id, table_name):
    if not _check_access(file_id):
        return jsonify({'error': 'Sin acceso'}), 403
    page     = max(1, int(request.args.get('page', 1)))
    per_page = max(1, min(200, int(request.args.get('per_page', 50))))
    try:
        data = DBSessionService.get_table_data(
            file_id, session['user_id'], table_name, page, per_page,
        )
        return jsonify(data)
    except PermissionError as e: return jsonify({'error': str(e)}), 403
    except ValueError      as e: return jsonify({'error': str(e)}), 404
    except RuntimeError    as e: return jsonify({'error': str(e)}), 502


@web_blueprint.route('/explorer/<int:file_id>/query', methods=['POST'])
@login_required
def run_query(file_id):
    if not _check_access(file_id):
        return jsonify({'error': 'Sin acceso'}), 403
    body = request.get_json(silent=True) or {}
    sql  = str(body.get('sql', '')).strip()
    if not sql:
        return jsonify({'error': 'El campo sql es obligatorio'}), 400
    try:
        return jsonify(DBSessionService.execute_query(file_id, session['user_id'], sql))
    except PermissionError as e: return jsonify({'error': str(e)}), 403
    except ValueError      as e: return jsonify({'error': str(e)}), 400
    except RuntimeError    as e: return jsonify({'error': str(e)}), 502


@web_blueprint.route('/explorer/<int:file_id>/queries', methods=['GET'])
@login_required
def list_queries(file_id):
    if not _check_access(file_id):
        return jsonify({'error': 'Sin acceso'}), 403
    rows = SavedQueryModel.get_by_file(file_id)
    return jsonify([
        {'id': r[0], 'name': r[2], 'query_json': r[3],
         'created_at': r[4].isoformat()}
        for r in rows
    ])


@web_blueprint.route('/explorer/<int:file_id>/queries', methods=['POST'])
@login_required
def save_query(file_id):
    if not _check_access(file_id):
        return jsonify({'error': 'Sin acceso'}), 403
    body = request.get_json(silent=True) or {}
    name = str(body.get('name', '')).strip()
    sql  = str(body.get('sql', '')).strip()
    if not name or not sql:
        return jsonify({'error': 'name y sql son obligatorios'}), 400
    qid, created_at = SavedQueryModel.create(file_id, session['user_id'], name, {'sql': sql})
    return jsonify({'id': qid, 'name': name, 'created_at': created_at.isoformat()}), 201


@web_blueprint.route('/explorer/<int:file_id>/queries/<int:query_id>', methods=['DELETE'])
@login_required
def delete_query(file_id, query_id):
    if not _check_access(file_id):
        return jsonify({'error': 'Sin acceso'}), 403
    ok = SavedQueryModel.delete(query_id, file_id)
    return jsonify({'ok': ok})


@web_blueprint.route('/explorer/<int:file_id>/share', methods=['POST'])
@login_required
def share(file_id):
    row = _check_access(file_id)
    if not row or not row[9]:
        return jsonify({'error': 'Solo el propietario puede generar códigos'}), 403
    body   = request.get_json(silent=True) or {}
    regen  = bool(body.get('regenerate', False))
    existing = row[8]
    if existing and not regen:
        return jsonify({'share_code': existing})
    code = secrets.token_hex(4).upper()
    FileModel.set_share_code(file_id, session['user_id'], code)
    return jsonify({'share_code': code})


@web_blueprint.route('/explorer/<int:file_id>/api-key', methods=['POST'])
@login_required
def regen_api_key(file_id):
    row = _check_access(file_id)
    if not row or not row[9]:
        return jsonify({'error': 'Solo el propietario puede regenerar la API key'}), 403
    plain_key = secrets.token_urlsafe(32)
    FileModel.set_api_password_hash(
        file_id, session['user_id'], generate_password_hash(plain_key),
    )
    return jsonify({
        'api_key':    plain_key,
        'ingest_url': f'/api/v1/ingest/{file_id}/{plain_key}',
    })


@web_blueprint.route('/explorer/<int:file_id>/delete', methods=['POST'])
@login_required
def delete_db(file_id):
    row = FileModel.get_by_id(file_id)
    if not row or row[1] != session['user_id']:
        flash('No tienes permiso para eliminar esta base de datos', 'error')
        return redirect(url_for('web.explorer', file_id=file_id))
    FileModel.delete(file_id, session['user_id'])
    FileService.delete_from_storage(row[4])
    flash('Base de datos eliminada', 'success')
    return redirect(url_for('web.dashboard'))
