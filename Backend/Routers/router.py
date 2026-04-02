from flask import jsonify, request

from Backend.Routers.PageRoutes import auth, manage_tab, python_exec, session as session_routes, table

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

    @app.route('/api/update_record', methods=['POST'])
    def update_record_route():
        data = request.get_json(silent=True) or {}
        return jsonify(table.update_record(data))

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
