import re
from flask import jsonify, request
from Backend.Routers.PageRoutes import database as user_db, session as session_routes

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

def get_users():
    admin_error = require_admin_session()
    if admin_error:
        return admin_error
    return jsonify(success=True, users=user_db.get_all_users())


def create_user():
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


def update_user_role(user_id):
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


def update_user_password(user_id):
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


def delete_user(user_id):
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
