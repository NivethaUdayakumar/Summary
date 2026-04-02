from Backend.Routers.PageRoutes import database as db
from Backend.Routers.PageRoutes import session as session_routes

def register_user(data: dict):
    user_id = str(data.get('user_id', '')).strip()
    role = str(data.get('role', '')).strip().lower()
    password = str(data.get('password', ''))
    if not user_id or not role or not password:
        return {'success': False, 'error': 'user_id, role, and password are required'}
    if not user_id.startswith('mtk') or not user_id[3:].isdigit():
        return {'success': False, 'error': 'user_id must start with mtk followed by digits'}
    if role not in ('admin', 'user'):
        return {'success': False, 'error': 'role must be admin or user'}
    if db.get_user(user_id):
        return {'success': False, 'error': 'user already exists'}
    db.create_user(user_id, role, password)
    return {'success': True, 'user_id': user_id, 'role': role}

def login_user(data: dict):
    user_id = str(data.get('user_id', '')).strip()
    password = str(data.get('password', ''))
    if not user_id or not password:
        return {'success': False, 'error': 'user_id and password are required'}
    user = db.validate_user(user_id, password)
    if not user:
        return {'success': False, 'error': 'invalid credentials'}
    session_routes.login_user(user_id, user['role'])
    return {'success': True, 'user_id': user_id, 'role': user['role']}
