from flask import jsonify, request
from Backend.Routers.PageRoutes.database_routes import handle_database_route
from Backend.Routers.PageRoutes import auth, manage_tab, python_exec, session as session_routes, table


def register_routes(app):

    # =========================
    # ROOT
    # =========================
    @app.route('/')
    def root():
        return app.send_static_file('Pages/Login/Login.html')

    # =========================
    # AUTH
    # =========================
    @app.route('/api/register', methods=['POST'])
    def register():
        data = request.get_json(silent=True) or {}
        result = auth.register_user(data)
        return jsonify(result), (201 if result.get('success') else 400)

    @app.route('/api/login', methods=['POST'])
    def login():
        data = request.get_json(silent=True) or {}
        result = auth.login_user(data)
        return jsonify(result), (200 if result.get('success') else 401)

    # =========================
    # SESSION
    # =========================
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
            **session_info
        )

    @app.route('/api/validate-session', methods=['GET'])
    def validate_session():
        if session_routes.is_session_active():
            return jsonify(success=True, active=True)

        session_routes.logout_user()
        return jsonify(success=True, active=False)

    @app.route('/api/session-pcode', methods=['POST'])
    def session_project_code():
        data = request.get_json(silent=True) or {}
        result = session_routes.update_project_code(data.get('project_code', ''))
        return jsonify(result), (200 if result.get('success') else 400)

    # =========================
    # TABLE GENERIC APIs
    # =========================
    @app.route('/api/create-table', methods=['POST'])
    def create_table_route():
        return jsonify(table.create_table(request.get_json(silent=True) or {}))

    @app.route('/api/delete-table', methods=['POST'])
    def delete_table_route():
        return jsonify(table.delete_table(request.get_json(silent=True) or {}))

    @app.route('/api/query-table', methods=['POST'])
    def query_table_route():
        return jsonify(table.query_table(request.get_json(silent=True) or {}))

    @app.route('/api/read-table', methods=['POST'])
    def read_table_route():
        return jsonify(table.read_table(request.get_json(silent=True) or {}))

    @app.route('/api/insert-record', methods=['POST'])
    def insert_record_route():
        return jsonify(table.insert_record(request.get_json(silent=True) or {}))

    @app.route('/api/update_record', methods=['POST'])
    def update_record_route():
        return jsonify(table.update_record(request.get_json(silent=True) or {}))

    @app.route('/api/delete-record', methods=['POST'])
    def delete_record_route():
        return jsonify(table.delete_record(request.get_json(silent=True) or {}))

    # =========================
    # PYTHON EXEC
    # =========================
    @app.route('/api/execute-python', methods=['POST'])
    def execute_python_route():
        return jsonify(python_exec.execute_python(request.get_json(silent=True) or {}))

    # =========================
    # DASHBOARD
    # =========================
    @app.route('/api/dashboard', methods=['GET'])
    def dashboard_route():
        return manage_tab.load_tab(request.args.get('tab', ''))

    @app.route('/api/project-name', methods=['GET'])
    def project_name_route():
        project_code = request.args.get('project_code', '')
        if not project_code:
            return jsonify(success=False, error='project_code required'), 400
        return session_routes.project_name_route(project_code)

    # =========================
    # DATABASE APIs
    # =========================
    def get_db_data():
        return request.get_json(silent=True) or {}

    def get_db_args():
        return request.args.to_dict()

    @app.route('/api/database/<action>', methods=['GET', 'POST'])
    def database_routes(action):

        data = get_db_data() if request.method == 'POST' else get_db_args()

        return jsonify(handle_database_route(action, data))