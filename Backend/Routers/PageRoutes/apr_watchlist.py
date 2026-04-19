import json
import sqlite3
from datetime import datetime
from pathlib import Path

from Backend.Routers.PageRoutes import session as session_routes


ROOT = Path(__file__).resolve().parents[3]
DB_PATH = ROOT / 'AppData' / 'App.db'
TABLE_NAME = 'apr_watchlist'
DEFAULT_WATCHLIST = 'APR Weekly'
WATCHLIST_RECORD = 'watchlist'
RUN_RECORD = 'run'
DEFAULT_BLOCK_LIMIT = 3
CUSTOM_BLOCK_LIMIT = 5
RUN_ID_FIELDS = ['Job', 'Milestone', 'Block', 'Stage']
TRACKER_FIELDS = [
    'Job',
    'Milestone',
    'Block',
    'Stage',
    'Dft_release',
    'User',
    'Created',
    'Modified',
    'Rerun',
    'Status',
    'Comments',
    'Promote',
]


def _now_str():
    return datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')


def _session_user():
    if not session_routes.is_session_active():
        return None, {'success': False, 'error': 'session inactive'}, 401

    session_info = session_routes.get_session_info()
    user_id = str(session_info.get('user_id', '')).strip().lower()
    if not user_id:
        return None, {'success': False, 'error': 'user_id missing from session'}, 401

    return user_id, None, None


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_table(conn):
    conn.executescript(
        f'''
        CREATE TABLE IF NOT EXISTS "{TABLE_NAME}" (
            "id" INTEGER PRIMARY KEY AUTOINCREMENT,
            "record_type" TEXT NOT NULL,
            "user_id" TEXT NOT NULL,
            "watchlist_name" TEXT NOT NULL,
            "is_default" INTEGER NOT NULL DEFAULT 0,
            "run_key" TEXT NOT NULL DEFAULT '',
            "job" TEXT,
            "milestone" TEXT,
            "block" TEXT,
            "stage" TEXT,
            "tracker_user" TEXT,
            "dft_release" TEXT,
            "run_status" TEXT,
            "comments" TEXT,
            "promote" TEXT,
            "run_payload" TEXT NOT NULL DEFAULT '{{}}',
            "created_at" TEXT NOT NULL,
            "updated_at" TEXT NOT NULL,
            CHECK("record_type" IN ('{WATCHLIST_RECORD}', '{RUN_RECORD}'))
        );
        CREATE UNIQUE INDEX IF NOT EXISTS "idx_{TABLE_NAME}_unique_entry"
            ON "{TABLE_NAME}" ("user_id", "watchlist_name", "record_type", "run_key");
        CREATE INDEX IF NOT EXISTS "idx_{TABLE_NAME}_lookup"
            ON "{TABLE_NAME}" ("user_id", "watchlist_name", "record_type", "block");
        '''
    )
    conn.commit()


def _get_watchlist_row(conn, user_id, watchlist_name):
    return conn.execute(
        f'''
        SELECT *
        FROM "{TABLE_NAME}"
        WHERE "user_id" = ?
          AND "record_type" = ?
          AND lower("watchlist_name") = lower(?)
        LIMIT 1
        ''',
        (user_id, WATCHLIST_RECORD, watchlist_name),
    ).fetchone()


def _ensure_default_watchlist(conn, user_id):
    now = _now_str()
    row = _get_watchlist_row(conn, user_id, DEFAULT_WATCHLIST)

    if row:
        if not row['is_default'] or row['watchlist_name'] != DEFAULT_WATCHLIST:
            conn.execute(
                f'''
                UPDATE "{TABLE_NAME}"
                SET "watchlist_name" = ?,
                    "is_default" = 1,
                    "updated_at" = ?
                WHERE "id" = ?
                ''',
                (DEFAULT_WATCHLIST, now, row['id']),
            )
            conn.commit()
        return

    conn.execute(
        f'''
        INSERT INTO "{TABLE_NAME}" (
            "record_type",
            "user_id",
            "watchlist_name",
            "is_default",
            "run_key",
            "run_payload",
            "created_at",
            "updated_at"
        ) VALUES (?, ?, ?, 1, '', '{{}}', ?, ?)
        ''',
        (WATCHLIST_RECORD, user_id, DEFAULT_WATCHLIST, now, now),
    )
    conn.commit()


def _watchlist_limit(watchlist_name):
    return DEFAULT_BLOCK_LIMIT if watchlist_name == DEFAULT_WATCHLIST else CUSTOM_BLOCK_LIMIT


def _normalize_watchlist_name(raw_name):
    return str(raw_name or '').strip()


def _normalize_run(run):
    if not isinstance(run, dict):
        raise ValueError('run is required')

    normalized = {}
    for field_name in TRACKER_FIELDS:
        value = run.get(field_name, '')
        normalized[field_name] = '' if value is None else str(value).strip()

    missing_fields = [field_name for field_name in RUN_ID_FIELDS if not normalized[field_name]]
    if missing_fields:
        raise ValueError('run must include Job, Milestone, Block, and Stage')

    normalized['run_key'] = '||'.join(normalized[field_name] for field_name in RUN_ID_FIELDS)
    return normalized


def _build_state(conn, user_id):
    _ensure_default_watchlist(conn, user_id)

    watchlist_rows = conn.execute(
        f'''
        SELECT *
        FROM "{TABLE_NAME}"
        WHERE "user_id" = ?
          AND "record_type" = ?
        ORDER BY "is_default" DESC, lower("watchlist_name") ASC
        ''',
        (user_id, WATCHLIST_RECORD),
    ).fetchall()

    run_rows = conn.execute(
        f'''
        SELECT *
        FROM "{TABLE_NAME}"
        WHERE "user_id" = ?
          AND "record_type" = ?
        ORDER BY lower("watchlist_name") ASC, lower("block") ASC, lower("job") ASC, lower("stage") ASC
        ''',
        (user_id, RUN_RECORD),
    ).fetchall()

    watchlists = []
    watchlists_by_name = {}

    for row in watchlist_rows:
        watchlist = {
            'id': row['id'],
            'name': row['watchlist_name'],
            'is_default': bool(row['is_default']),
            'per_block_limit': _watchlist_limit(row['watchlist_name']),
            'created_at': row['created_at'],
            'updated_at': row['updated_at'],
            'item_count': 0,
            'items': [],
        }
        watchlists.append(watchlist)
        watchlists_by_name[row['watchlist_name']] = watchlist

    for row in run_rows:
        payload_text = row['run_payload'] or '{}'
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError:
            payload = {}

        watchlist = watchlists_by_name.get(row['watchlist_name'])
        if not watchlist:
            continue

        watchlist['items'].append(
            {
                'id': row['id'],
                'watchlist_name': row['watchlist_name'],
                'run_key': row['run_key'],
                'Job': row['job'],
                'Milestone': row['milestone'],
                'Block': row['block'],
                'Stage': row['stage'],
                'Dft_release': row['dft_release'],
                'User': row['tracker_user'],
                'Status': row['run_status'],
                'Comments': row['comments'],
                'Promote': row['promote'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at'],
                'payload': payload,
            }
        )

    for watchlist in watchlists:
        watchlist['item_count'] = len(watchlist['items'])

    return {
        'success': True,
        'user_id': user_id,
        'default_watchlist': DEFAULT_WATCHLIST,
        'watchlists': watchlists,
    }


def get_watchlists():
    user_id, error_payload, error_status = _session_user()
    if error_payload:
        return error_payload, error_status

    try:
        with _connect() as conn:
            _ensure_table(conn)
            return _build_state(conn, user_id), 200
    except sqlite3.Error as error:
        return {'success': False, 'error': str(error)}, 500


def create_watchlist(data):
    user_id, error_payload, error_status = _session_user()
    if error_payload:
        return error_payload, error_status

    watchlist_name = _normalize_watchlist_name((data or {}).get('watchlist_name'))
    if not watchlist_name:
        return {'success': False, 'error': 'watchlist_name is required'}, 400

    try:
        with _connect() as conn:
            _ensure_table(conn)
            _ensure_default_watchlist(conn, user_id)

            existing_row = _get_watchlist_row(conn, user_id, watchlist_name)
            if existing_row:
                return {'success': False, 'error': 'watchlist already exists'}, 400

            now = _now_str()
            conn.execute(
                f'''
                INSERT INTO "{TABLE_NAME}" (
                    "record_type",
                    "user_id",
                    "watchlist_name",
                    "is_default",
                    "run_key",
                    "run_payload",
                    "created_at",
                    "updated_at"
                ) VALUES (?, ?, ?, 0, '', '{{}}', ?, ?)
                ''',
                (WATCHLIST_RECORD, user_id, watchlist_name, now, now),
            )
            conn.commit()

            payload = _build_state(conn, user_id)
            payload['message'] = 'watchlist created'
            return payload, 201
    except sqlite3.Error as error:
        return {'success': False, 'error': str(error)}, 500


def delete_watchlist(data):
    user_id, error_payload, error_status = _session_user()
    if error_payload:
        return error_payload, error_status

    watchlist_name = _normalize_watchlist_name((data or {}).get('watchlist_name'))
    if not watchlist_name:
        return {'success': False, 'error': 'watchlist_name is required'}, 400

    try:
        with _connect() as conn:
            _ensure_table(conn)
            _ensure_default_watchlist(conn, user_id)

            row = _get_watchlist_row(conn, user_id, watchlist_name)
            if not row:
                return {'success': False, 'error': 'watchlist not found'}, 404

            if row['watchlist_name'] == DEFAULT_WATCHLIST or row['is_default']:
                return {'success': False, 'error': f'"{DEFAULT_WATCHLIST}" cannot be deleted'}, 400

            conn.execute(
                f'''
                DELETE FROM "{TABLE_NAME}"
                WHERE "user_id" = ?
                  AND lower("watchlist_name") = lower(?)
                ''',
                (user_id, watchlist_name),
            )
            conn.commit()

            payload = _build_state(conn, user_id)
            payload['message'] = 'watchlist deleted'
            return payload, 200
    except sqlite3.Error as error:
        return {'success': False, 'error': str(error)}, 500


def add_run(data):
    user_id, error_payload, error_status = _session_user()
    if error_payload:
        return error_payload, error_status

    watchlist_name = _normalize_watchlist_name((data or {}).get('watchlist_name'))
    if not watchlist_name:
        return {'success': False, 'error': 'watchlist_name is required'}, 400

    try:
        normalized_run = _normalize_run((data or {}).get('run'))
    except ValueError as error:
        return {'success': False, 'error': str(error)}, 400

    try:
        with _connect() as conn:
            _ensure_table(conn)
            _ensure_default_watchlist(conn, user_id)

            watchlist_row = _get_watchlist_row(conn, user_id, watchlist_name)
            if not watchlist_row:
                return {'success': False, 'error': 'watchlist not found'}, 404

            canonical_name = watchlist_row['watchlist_name']
            run_exists = conn.execute(
                f'''
                SELECT 1
                FROM "{TABLE_NAME}"
                WHERE "user_id" = ?
                  AND "watchlist_name" = ?
                  AND "record_type" = ?
                  AND "run_key" = ?
                LIMIT 1
                ''',
                (user_id, canonical_name, RUN_RECORD, normalized_run['run_key']),
            ).fetchone()
            if run_exists:
                return {'success': False, 'error': 'run already exists in this watchlist'}, 400

            block_count = conn.execute(
                f'''
                SELECT COUNT(*)
                FROM "{TABLE_NAME}"
                WHERE "user_id" = ?
                  AND "watchlist_name" = ?
                  AND "record_type" = ?
                  AND "block" = ?
                ''',
                (user_id, canonical_name, RUN_RECORD, normalized_run['Block']),
            ).fetchone()[0]

            block_limit = _watchlist_limit(canonical_name)
            if block_count >= block_limit:
                return {
                    'success': False,
                    'error': f'maximum of {block_limit} runs per block is allowed in "{canonical_name}"',
                }, 400

            now = _now_str()
            conn.execute(
                f'''
                INSERT INTO "{TABLE_NAME}" (
                    "record_type",
                    "user_id",
                    "watchlist_name",
                    "is_default",
                    "run_key",
                    "job",
                    "milestone",
                    "block",
                    "stage",
                    "tracker_user",
                    "dft_release",
                    "run_status",
                    "comments",
                    "promote",
                    "run_payload",
                    "created_at",
                    "updated_at"
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    RUN_RECORD,
                    user_id,
                    canonical_name,
                    1 if canonical_name == DEFAULT_WATCHLIST else 0,
                    normalized_run['run_key'],
                    normalized_run['Job'],
                    normalized_run['Milestone'],
                    normalized_run['Block'],
                    normalized_run['Stage'],
                    normalized_run['User'],
                    normalized_run['Dft_release'],
                    normalized_run['Status'],
                    normalized_run['Comments'],
                    normalized_run['Promote'],
                    json.dumps((data or {}).get('run') or {}, sort_keys=True),
                    now,
                    now,
                ),
            )
            conn.commit()

            payload = _build_state(conn, user_id)
            payload['message'] = 'run added to watchlist'
            return payload, 201
    except sqlite3.Error as error:
        return {'success': False, 'error': str(error)}, 500


def delete_run(data):
    user_id, error_payload, error_status = _session_user()
    if error_payload:
        return error_payload, error_status

    try:
        item_id = int((data or {}).get('item_id', 0))
    except (TypeError, ValueError):
        item_id = 0

    if item_id <= 0:
        return {'success': False, 'error': 'item_id is required'}, 400

    try:
        with _connect() as conn:
            _ensure_table(conn)
            _ensure_default_watchlist(conn, user_id)

            existing_row = conn.execute(
                f'''
                SELECT 1
                FROM "{TABLE_NAME}"
                WHERE "id" = ?
                  AND "user_id" = ?
                  AND "record_type" = ?
                LIMIT 1
                ''',
                (item_id, user_id, RUN_RECORD),
            ).fetchone()
            if not existing_row:
                return {'success': False, 'error': 'watchlist item not found'}, 404

            conn.execute(
                f'''
                DELETE FROM "{TABLE_NAME}"
                WHERE "id" = ?
                  AND "user_id" = ?
                  AND "record_type" = ?
                ''',
                (item_id, user_id, RUN_RECORD),
            )
            conn.commit()

            payload = _build_state(conn, user_id)
            payload['message'] = 'run removed from watchlist'
            return payload, 200
    except sqlite3.Error as error:
        return {'success': False, 'error': str(error)}, 500
