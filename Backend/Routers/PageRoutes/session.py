import uuid
from datetime import datetime, timedelta
from flask import current_app, session, request, jsonify
import json
import os

SESSION_KEY = 'user_id'
CREATED_AT_KEY = 'created_at'
ROLE_KEY = 'role'
SESSION_ID_KEY = 'session_id'
PROJECT_CODE_KEY = 'project_code'

def _now():
    return datetime.utcnow()

def login_user(user_id: str, role: str):
    session.clear()
    session[SESSION_KEY] = user_id
    session[ROLE_KEY] = role
    session[SESSION_ID_KEY] = str(uuid.uuid4())
    session[CREATED_AT_KEY] = _now().isoformat() + 'Z'
    session[PROJECT_CODE_KEY] = 'Unknown'
    session.permanent = True

def get_session_info():
    if not is_session_active():
        return {}
    return {
        'user_id': session.get(SESSION_KEY),
        'role': session.get(ROLE_KEY),
        'session_id': session.get(SESSION_ID_KEY),
        'created_at': session.get(CREATED_AT_KEY),
        'project_code': session.get(PROJECT_CODE_KEY, 'Unknown'),
    }

def update_project_code(project_code: str):
    if not project_code:
        return {'success': False, 'error': 'project_code is required'}
    if not is_session_active():
        return {'success': False, 'error': 'session inactive'}
    session[PROJECT_CODE_KEY] = project_code
    return {'success': True, 'project_code': project_code}

def is_session_active():
    user_id = session.get(SESSION_KEY)
    created_at = session.get(CREATED_AT_KEY)
    if not user_id or not created_at:
        return False
    try:
        started = datetime.fromisoformat(created_at.rstrip('Z'))
    except ValueError:
        return False
    lifetime = current_app.config.get('PERMANENT_SESSION_LIFETIME', timedelta(hours=8))
    return _now() - started < lifetime

def logout_user():
    session.clear()

def project_name_route(project_code):
    config_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'Configurations', 'app.project.json')
    print("Config_path:", config_path)  # Debugging line
    try:
        with open(config_path, 'r') as f:
            projects = json.load(f)
        project_name = projects.get(project_code)
        print("Project name found:", project_name)  # Debugging line
        if project_name:
            return jsonify(success=True, project_name=project_name)
        else:
            return jsonify(success=False, error=f'Project code "{project_code}" not found'), 404
    except FileNotFoundError:
        return jsonify(success=False, error='Project configuration file not found'), 500
    except json.JSONDecodeError:
        return jsonify(success=False, error='Invalid project configuration file'), 500
