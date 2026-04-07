from pathlib import Path
from flask import Response, jsonify

from Backend.Routers.PageRoutes import session as session_routes

ROOT = Path(__file__).resolve().parents[3]
PAGES_ROOT = ROOT / 'Frontend' / 'Pages'

TAB_DEFINITIONS = {
    'Summary': {'label': 'Summary', 'group': 'primary'},
    'APRTracker': {'label': 'APR Tracker', 'group': 'apr'},
    'APRWeekly': {'label': 'APR Weekly', 'group': 'apr'},
    'APRWatchlist': {'label': 'APR Watchlist', 'group': 'apr'},
    'ProfileManager': {'label': 'Profile Manager', 'group': 'primary'},
    'Database': {'label': 'Database', 'group': 'primary'}
}

ROLE_ALLOWED_TABS = {
    'admin': ['Menu', 'Login', 'Register', 'Dashboard', 'Summary', 'APRTracker', 'APRWeekly', 'APRWatchlist', 'ProfileManager', 'Database'],
    'user': ['Menu', 'Dashboard', 'Summary', 'APRTracker', 'APRWeekly', 'APRWatchlist'],
}

def role_allows_tab(role: str, tab_name: str) -> bool:
    if role not in ROLE_ALLOWED_TABS:
        return False
    normalized = tab_name.strip().replace('.html', '')
    allowed = ROLE_ALLOWED_TABS.get(role, [])
    return normalized in allowed

def get_dashboard_tabs(role: str):
    allowed = ROLE_ALLOWED_TABS.get(role, [])
    return [
        {
            'key': tab_key,
            'label': TAB_DEFINITIONS[tab_key]['label'],
            'group': TAB_DEFINITIONS[tab_key]['group'],
        }
        for tab_key in allowed
        if tab_key in TAB_DEFINITIONS
    ]

def get_default_dashboard_tab(role: str):
    tabs = get_dashboard_tabs(role)
    return tabs[0]['key'] if tabs else ''

def load_tab(tab_name: str = None):
    if not session_routes.is_session_active():
        return jsonify(success=False, error='not_logged_in'), 401
    session_info = session_routes.get_session_info()
    role = session_info.get('role')
    normalized = (tab_name or 'Menu').strip().replace('.html', '')
    if not role_allows_tab(role, normalized):
        return Response('Access Denied', mimetype='text/plain'), 403
    page_path = (PAGES_ROOT / normalized / f'{normalized}.html').resolve()
    if PAGES_ROOT not in page_path.parents:
        return jsonify(success=False, error='invalid tab path'), 400
    if not page_path.exists():
        return jsonify(success=False, error='tab not found'), 404
    return Response(page_path.read_text(encoding='utf-8'), mimetype='text/html')
