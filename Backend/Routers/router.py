import re

from flask import jsonify, request

from Backend.Routers.PageRoutes import auth, database as user_db, manage_tab, python_exec, session as session_routes, table

VALID_ROLES = {'admin', 'user'}
USER_ID_PATTERN = re.compile(r'^mtk\d+$')


def normalize_user_id(value):
    return str(value or '').strip().lower()


def normalize_role(value):
    return str(value or '').strip().lower()


def require_active_session():
    if not session_routes.is_session_active():
        return jsonify(success=False, error='session inactive'), 401
    return None


def require_admin_session():
    session_error = require_active_session()
    if session_error:
        return session_error

    session_info = session_routes.get_session_info()
    if session_info.get('role') != 'admin':
        return jsonify(success=False, error='admin access required'), 403
    return None


def validate_user_payload(user_id, role=None, password=None):
    if not user_id:
        return 'user_id is required'
    if not USER_ID_PATTERN.fullmatch(user_id):
        return 'user_id must start with mtk followed by digits'
    if role is not None and role not in VALID_ROLES:
        return 'role must be admin or user'
    if password is not None and not password:
        return 'password is required'
    return None

def register_routes(app):
    @app.route('/')
    def root():
        return app.send_static_file('Pages/Login/Login.html')

    @app.route('/api/register', methods=['POST'])
    def register():
        data = request.get_json(silent=True) or {}
        result = auth.register_user(data)
        status = 201 if result.get('success') else 400
        return jsonify(result), status

    @app.route('/api/login', methods=['POST'])
    def login():
        data = request.get_json(silent=True) or {}
        result = auth.login_user(data)
        status = 200 if result.get('success') else 401
        return jsonify(result), status

    @app.route('/api/session', methods=['GET'])
    def session_details():
        if not session_routes.is_session_active():
            return jsonify(success=False, error='session inactive'), 401
        session_info = session_routes.get_session_info()
        role = session_info.get('role', '')
        return jsonify(
            success=True,
            allowed_tabs=manage_tab.get_dashboard_tabs(role),
            default_tab=manage_tab.get_default_dashboard_tab(role),
            **session_info,
        )

    @app.route('/api/validate-session', methods=['GET'])
    def validate_session():
        if session_routes.is_session_active():
            return jsonify(success=True, active=True)
        session_routes.logout_user()
        return jsonify(success=True, active=False, message='session expired or invalid')

    @app.route('/api/session-pcode', methods=['POST'])
    def session_project_code():
        data = request.get_json(silent=True) or {}
        project_code = data.get('project_code', '')
        result = session_routes.update_project_code(project_code)
        status = 200 if result.get('success') else 400
        return jsonify(result), status

    @app.route('/api/create-table', methods=['POST'])
    def create_table_route():
        data = request.get_json(silent=True) or {}
        return jsonify(table.create_table(data))

    @app.route('/api/delete-table', methods=['POST'])
    def delete_table_route():
        data = request.get_json(silent=True) or {}
        return jsonify(table.delete_table(data))

    @app.route('/api/query-table', methods=['POST'])
    def query_table_route():
        data = request.get_json(silent=True) or {}
        return jsonify(table.query_table(data))

    @app.route('/api/insert-record', methods=['POST'])
    def insert_record_route():
        data = request.get_json(silent=True) or {}
        return jsonify(table.insert_record(data))

    @app.route('/api/delete-record', methods=['POST'])
    def delete_record_route():
        data = request.get_json(silent=True) or {}
        return jsonify(table.delete_record(data))

    @app.route('/api/execute-python', methods=['POST'])
    def execute_python_route():
        data = request.get_json(silent=True) or {}
        return jsonify(python_exec.execute_python(data))

    @app.route('/api/dashboard', methods=['GET'])
    def dashboard_route():
        tab_name = request.args.get('tab', '')
        return manage_tab.load_tab(tab_name)

    @app.route('/api/project-name', methods=['GET'])
    def project_name_route():
        project_code = request.args.get('project_code', '')
        if not project_code:
            return jsonify(success=False, error='project_code parameter is required'), 400
        return session_routes.project_name_route(project_code)

    @app.route('/api/users', methods=['GET'])
    def get_users_route():
        admin_error = require_admin_session()
        if admin_error:
            return admin_error
        return jsonify(success=True, users=user_db.get_all_users())

    @app.route('/api/users', methods=['POST'])
    def create_user_route():
        admin_error = require_admin_session()
        if admin_error:
            return admin_error

        data = request.get_json(silent=True) or {}
        user_id = normalize_user_id(data.get('user_id', ''))
        role = normalize_role(data.get('role', ''))
        password = str(data.get('password', ''))

        validation_error = validate_user_payload(user_id, role=role, password=password)
        if validation_error:
            return jsonify(success=False, error=validation_error), 400
        if user_db.get_user(user_id):
            return jsonify(success=False, error='user already exists'), 400

        user_db.create_user(user_id, role, password)
        return jsonify(success=True, message='user created', user_id=user_id)

    @app.route('/api/users/<user_id>/role', methods=['PUT'])
    def update_user_role_route(user_id):
        admin_error = require_admin_session()
        if admin_error:
            return admin_error

        normalized_user_id = normalize_user_id(user_id)
        data = request.get_json(silent=True) or {}
        role = normalize_role(data.get('role', ''))

        validation_error = validate_user_payload(normalized_user_id, role=role)
        if validation_error:
            return jsonify(success=False, error=validation_error), 400
        if not user_db.update_user_role(normalized_user_id, role):
            return jsonify(success=False, error='user not found'), 404

        return jsonify(success=True, message='role updated', user_id=normalized_user_id, role=role)

    @app.route('/api/users/<user_id>/password', methods=['PUT'])
    def update_user_password_route(user_id):
        admin_error = require_admin_session()
        if admin_error:
            return admin_error

        normalized_user_id = normalize_user_id(user_id)
        data = request.get_json(silent=True) or {}
        password = str(data.get('password', ''))

        validation_error = validate_user_payload(normalized_user_id, password=password)
        if validation_error:
            return jsonify(success=False, error=validation_error), 400
        if not user_db.update_user_password(normalized_user_id, password):
            return jsonify(success=False, error='user not found'), 404

        return jsonify(success=True, message='password updated', user_id=normalized_user_id)

    @app.route('/api/users/<user_id>', methods=['DELETE'])
    def delete_user_route(user_id):
        admin_error = require_admin_session()
        if admin_error:
            return admin_error

        normalized_user_id = normalize_user_id(user_id)
        session_info = session_routes.get_session_info()
        if normalized_user_id == normalize_user_id(session_info.get('user_id', '')):
            return jsonify(success=False, error='cannot delete the active admin user'), 400
        if not user_db.delete_user(normalized_user_id):
            return jsonify(success=False, error='user not found'), 404

        return jsonify(success=True, message='user deleted', user_id=normalized_user_id)
