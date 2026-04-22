import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from Backend.Routers.PageRoutes import session as session_routes


ROOT = Path(__file__).resolve().parents[3]
DB_PATH = ROOT / 'AppData' / 'App.db'
TABLE_NAME = 'apr_watchlist'
WEEKLY_ARCHIVE_TABLE = 'apr_weekly'
DEFAULT_WATCHLIST = 'APR Weekly'
WATCHLIST_RECORD = 'watchlist'
RUN_RECORD = 'run'
DEFAULT_BLOCK_LIMIT = 3
CUSTOM_BLOCK_LIMIT = 10
RUN_ID_FIELDS = ['Job', 'Milestone', 'Block', 'Stage']
TRACKER_TABLE = 'apr-tracker'
TIMING_SUMMARY_TABLE = 'APR_TIMING_SUMMARY'
TIMING_STAGE_ORDER = ('place', 'clock', 'route')
TIMING_STAGE_LABELS = {'place': 'PLACE', 'clock': 'CLOCK', 'route': 'ROUTE'}
TIMING_TCHECKS = ('setup', 'hold')
TIMING_PATHGROUPS = ('all', 'crit_r2out', 'from_mem', 'leaf_icg', 'reg2reg')
TIMING_MODE = 'FUNC'
TIMING_CORNER = 'SS_125C'
TIMING_VOLTAGE = '0p72v'
TIMING_SOURCE_LABEL = f'{DB_PATH.name} / {TIMING_SUMMARY_TABLE}'
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


def _ensure_timing_summary_table(conn):
    conn.executescript(
        f'''
        CREATE TABLE IF NOT EXISTS "{TIMING_SUMMARY_TABLE}" (
            "Job" TEXT,
            "Milestone" TEXT,
            "Block" TEXT,
            "Stage" TEXT,
            "Source_mtime" INTEGER,
            "Mode" TEXT,
            "TCheck" TEXT,
            "TCorner" TEXT,
            "Voltage" TEXT,
            "Pathgroup" TEXT,
            "WNS" REAL,
            "TNS" REAL,
            "NVP" INTEGER
        );
        CREATE INDEX IF NOT EXISTS "idx_apr_watchlist_timing_scope"
            ON "{TIMING_SUMMARY_TABLE}" ("Job", "Milestone", "Block", "Stage");
        CREATE INDEX IF NOT EXISTS "idx_apr_watchlist_timing_filters"
            ON "{TIMING_SUMMARY_TABLE}" ("TCheck", "Pathgroup", "Stage");
        '''
    )
    conn.commit()


def _ensure_weekly_archive_table(conn):
    conn.executescript(
        f'''
        CREATE TABLE IF NOT EXISTS "{WEEKLY_ARCHIVE_TABLE}" (
            "id" INTEGER PRIMARY KEY AUTOINCREMENT,
            "user_id" TEXT NOT NULL,
            "week_key" TEXT NOT NULL,
            "week_label" TEXT NOT NULL,
            "week_start" TEXT NOT NULL,
            "week_end" TEXT NOT NULL,
            "source_watchlist" TEXT NOT NULL,
            "run_key" TEXT NOT NULL,
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
            "archived_at" TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS "idx_{WEEKLY_ARCHIVE_TABLE}_lookup"
            ON "{WEEKLY_ARCHIVE_TABLE}" ("user_id", "source_watchlist", "week_key");
        CREATE UNIQUE INDEX IF NOT EXISTS "idx_{WEEKLY_ARCHIVE_TABLE}_unique_run"
            ON "{WEEKLY_ARCHIVE_TABLE}" ("user_id", "source_watchlist", "week_key", "run_key");
        '''
    )
    conn.commit()


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


def _safe_json_loads(payload_text, fallback):
    text = str(payload_text or '').strip()
    if not text:
        return fallback

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return fallback


def _format_iso_datetime(value):
    return value.strftime('%Y-%m-%dT%H:%M:%SZ')


def _get_week_info(date_input=None):
    current_time = date_input or datetime.now()
    current_day = datetime(current_time.year, current_time.month, current_time.day)
    week_start = current_day - timedelta(days=current_day.weekday())
    week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
    iso_year, iso_week, _ = current_day.isocalendar()

    return {
        'key': f'{iso_year}-W{iso_week:02d}',
        'label': f'Week of {week_start.strftime("%b")} {week_start.day}, {week_start.year}',
        'start': _format_iso_datetime(week_start),
        'end': _format_iso_datetime(week_end),
    }


def _metadata_payload_for_week(week_info):
    return json.dumps(
        {
            'week_key': week_info['key'],
            'week_label': week_info['label'],
            'week_start': week_info['start'],
            'week_end': week_info['end'],
        },
        sort_keys=True,
    )


def _get_week_info_from_watchlist_row(row):
    payload = _safe_json_loads((row or {}).get('run_payload') if isinstance(row, dict) else (row['run_payload'] if row else ''), {})

    if not payload.get('week_key'):
        return None

    return {
        'key': str(payload.get('week_key', '')).strip(),
        'label': str(payload.get('week_label', '')).strip(),
        'start': str(payload.get('week_start', '')).strip(),
        'end': str(payload.get('week_end', '')).strip(),
    }


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
    week_info = _get_week_info()
    row = _get_watchlist_row(conn, user_id, DEFAULT_WATCHLIST)

    if row:
        stored_week_info = _get_week_info_from_watchlist_row(row)
        if not row['is_default'] or row['watchlist_name'] != DEFAULT_WATCHLIST or not stored_week_info:
            conn.execute(
                f'''
                UPDATE "{TABLE_NAME}"
                SET "watchlist_name" = ?,
                    "is_default" = 1,
                    "run_payload" = ?,
                    "updated_at" = ?
                WHERE "id" = ?
                ''',
                (DEFAULT_WATCHLIST, _metadata_payload_for_week(week_info), now, row['id']),
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
        ) VALUES (?, ?, ?, 1, '', ?, ?, ?)
        ''',
        (WATCHLIST_RECORD, user_id, DEFAULT_WATCHLIST, _metadata_payload_for_week(week_info), now, now),
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


def _fetch_default_watchlist_run_rows(conn, user_id):
    return conn.execute(
        f'''
        SELECT *
        FROM "{TABLE_NAME}"
        WHERE "user_id" = ?
          AND "record_type" = ?
          AND lower("watchlist_name") = lower(?)
        ORDER BY lower("block") ASC, lower("job") ASC, lower("stage") ASC
        ''',
        (user_id, RUN_RECORD, DEFAULT_WATCHLIST),
    ).fetchall()


def _archive_default_watchlist_runs(conn, user_id, week_info, run_rows):
    if not week_info or not week_info.get('key') or not run_rows:
        return

    conn.execute(
        f'''
        DELETE FROM "{WEEKLY_ARCHIVE_TABLE}"
        WHERE "user_id" = ?
          AND "week_key" = ?
          AND lower("source_watchlist") = lower(?)
        ''',
        (user_id, week_info['key'], DEFAULT_WATCHLIST),
    )

    archived_at = _now_str()
    archive_rows = [
        (
            user_id,
            week_info['key'],
            week_info['label'],
            week_info['start'],
            week_info['end'],
            DEFAULT_WATCHLIST,
            row['run_key'] or '',
            row['job'] or '',
            row['milestone'] or '',
            row['block'] or '',
            row['stage'] or '',
            row['tracker_user'] or '',
            row['dft_release'] or '',
            row['run_status'] or '',
            row['comments'] or '',
            row['promote'] or '',
            row['run_payload'] or '{}',
            archived_at,
        )
        for row in run_rows
    ]

    conn.executemany(
        f'''
        INSERT INTO "{WEEKLY_ARCHIVE_TABLE}" (
            "user_id",
            "week_key",
            "week_label",
            "week_start",
            "week_end",
            "source_watchlist",
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
            "archived_at"
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        archive_rows,
    )


def _clear_default_watchlist_runs(conn, user_id):
    conn.execute(
        f'''
        DELETE FROM "{TABLE_NAME}"
        WHERE "user_id" = ?
          AND "record_type" = ?
          AND lower("watchlist_name") = lower(?)
        ''',
        (user_id, RUN_RECORD, DEFAULT_WATCHLIST),
    )


def _update_default_watchlist_metadata(conn, user_id, metadata_id, week_info):
    conn.execute(
        f'''
        UPDATE "{TABLE_NAME}"
        SET "watchlist_name" = ?,
            "is_default" = 1,
            "run_payload" = ?,
            "updated_at" = ?
        WHERE "id" = ?
          AND "user_id" = ?
          AND "record_type" = ?
        ''',
        (
            DEFAULT_WATCHLIST,
            _metadata_payload_for_week(week_info),
            _now_str(),
            metadata_id,
            user_id,
            WATCHLIST_RECORD,
        ),
    )


def _rollover_default_watchlist_if_needed(conn, user_id):
    metadata_row = _get_watchlist_row(conn, user_id, DEFAULT_WATCHLIST)
    if not metadata_row:
        return _get_week_info()

    stored_week_info = _get_week_info_from_watchlist_row(metadata_row)
    current_week_info = _get_week_info()
    needs_metadata_refresh = (
        not stored_week_info
        or stored_week_info.get('key') != current_week_info['key']
        or stored_week_info.get('label') != current_week_info['label']
        or stored_week_info.get('start') != current_week_info['start']
        or stored_week_info.get('end') != current_week_info['end']
    )

    if not stored_week_info:
        _update_default_watchlist_metadata(conn, user_id, metadata_row['id'], current_week_info)
        conn.commit()
        return current_week_info

    if stored_week_info['key'] != current_week_info['key']:
        run_rows = _fetch_default_watchlist_run_rows(conn, user_id)
        _archive_default_watchlist_runs(conn, user_id, stored_week_info, run_rows)
        _clear_default_watchlist_runs(conn, user_id)
        _update_default_watchlist_metadata(conn, user_id, metadata_row['id'], current_week_info)
        conn.commit()
        return current_week_info

    if needs_metadata_refresh:
        _update_default_watchlist_metadata(conn, user_id, metadata_row['id'], current_week_info)
        conn.commit()

    return current_week_info


def _prepare_watchlist_state(conn, user_id):
    _ensure_table(conn)
    _ensure_weekly_archive_table(conn)
    _ensure_default_watchlist(conn, user_id)
    return _rollover_default_watchlist_if_needed(conn, user_id)


def _build_state(conn, user_id):
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
        row_payload = _safe_json_loads(row['run_payload'], {})
        week_info = _get_week_info_from_watchlist_row(row) if row['watchlist_name'] == DEFAULT_WATCHLIST else None
        watchlist = {
            'id': row['id'],
            'name': row['watchlist_name'],
            'is_default': bool(row['is_default']),
            'per_block_limit': _watchlist_limit(row['watchlist_name']),
            'created_at': row['created_at'],
            'updated_at': row['updated_at'],
            'week_key': week_info['key'] if week_info else '',
            'week_label': week_info['label'] if week_info else '',
            'metadata': row_payload,
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
            _prepare_watchlist_state(conn, user_id)
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
            _prepare_watchlist_state(conn, user_id)

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
            _prepare_watchlist_state(conn, user_id)

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
            _prepare_watchlist_state(conn, user_id)

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
            _prepare_watchlist_state(conn, user_id)

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


def _parse_float(value):
    text = str(value or '').strip()
    if not text:
        return None

    try:
        return round(float(text), 3)
    except (TypeError, ValueError):
        return None


def _parse_int(value):
    text = str(value or '').strip()
    if not text:
        return None

    try:
        return int(round(float(text)))
    except (TypeError, ValueError):
        return None


def _modified_to_epoch(timestamp_text):
    text = str(timestamp_text or '').strip()
    if not text:
        return int(datetime.utcnow().timestamp())

    for fmt in ('%Y%m%d %H:%M:%S', '%Y-%m-%dT%H:%M:%SZ'):
        try:
            return int(datetime.strptime(text, fmt).timestamp())
        except ValueError:
            continue

    return int(datetime.utcnow().timestamp())


def _fallback_timing_metrics(row, tcheck):
    stage_name = str(row['Stage'] or '').strip().lower()
    status_name = str(row['Status'] or '').strip().lower()
    promote_name = str(row['Promote'] or '').strip().lower()
    defaults = {
        'setup': {
            'place': (-0.020, -2.600, 26),
            'clock': (-0.015, -1.850, 20),
            'route': (-0.011, -1.250, 16),
        },
        'hold': {
            'place': (-0.006, -0.900, 6),
            'clock': (-0.004, -0.650, 5),
            'route': (-0.003, -0.420, 4),
        },
    }
    status_factors = {
        'completed': 0.72,
        'await extraction': 1.08,
        'extracting': 1.02,
        'job running': 0.96,
        'job failed': 1.55,
        'extraction failed': 1.85,
    }
    base_wns, base_tns, base_nvp = defaults.get(tcheck, {}).get(stage_name, (-0.010, -1.000, 10))
    factor = status_factors.get(status_name, 1.0)

    if promote_name == 'yes':
        factor *= 0.88

    return {
        'WNS': round(base_wns * factor, 3),
        'TNS': round(base_tns * factor, 3),
        'NVP': max(int(round(base_nvp * max(factor, 0.6))), 0),
    }


def _build_base_timing_metrics(row, tcheck):
    prefix = 'Setup' if tcheck == 'setup' else 'Hold'
    fallback = _fallback_timing_metrics(row, tcheck)
    metrics = {
        'WNS': _parse_float(row[f'{prefix}_WNS_seq']),
        'TNS': _parse_float(row[f'{prefix}_TNS_seq']),
        'NVP': _parse_int(row[f'{prefix}_NVP_seq']),
    }

    if all(metric is None for metric in metrics.values()):
        return fallback

    for metric_name, fallback_value in fallback.items():
        if metrics[metric_name] is None:
            metrics[metric_name] = fallback_value

    return metrics


def _scale_wns_for_pathgroup(base_value, pathgroup):
    negative_scales = {
        'all': 1.00,
        'crit_r2out': 1.35,
        'from_mem': 0.58,
        'leaf_icg': 0.34,
        'reg2reg': 0.78,
    }
    positive_scales = {
        'all': 1.00,
        'crit_r2out': 0.68,
        'from_mem': 0.46,
        'leaf_icg': 0.28,
        'reg2reg': 0.56,
    }

    if base_value is None:
        return None

    if base_value < 0:
        return round(base_value * negative_scales.get(pathgroup, 1.0), 3)

    return round(base_value * positive_scales.get(pathgroup, 1.0), 3)


def _scale_tns_for_pathgroup(base_value, pathgroup):
    scales = {
        'all': 1.00,
        'crit_r2out': 0.44,
        'from_mem': 0.22,
        'leaf_icg': 0.13,
        'reg2reg': 0.29,
    }

    if base_value is None:
        return None

    return round(base_value * scales.get(pathgroup, 1.0), 3)


def _scale_nvp_for_pathgroup(base_value, pathgroup):
    scales = {
        'all': 1.00,
        'crit_r2out': 0.38,
        'from_mem': 0.17,
        'leaf_icg': 0.10,
        'reg2reg': 0.25,
    }

    if base_value is None:
        return None

    return max(int(round(base_value * scales.get(pathgroup, 1.0))), 0)


def _build_timing_seed_rows_for_tracker_row(row):
    stage_name = str(row['Stage'] or '').strip().lower()
    if stage_name not in TIMING_STAGE_ORDER:
        return []

    source_mtime = _modified_to_epoch(row['Modified'])
    seed_rows = []

    for tcheck in TIMING_TCHECKS:
        base_metrics = _build_base_timing_metrics(row, tcheck)

        for pathgroup in TIMING_PATHGROUPS:
            seed_rows.append((
                row['Job'],
                row['Milestone'],
                row['Block'],
                stage_name,
                source_mtime,
                TIMING_MODE,
                tcheck,
                TIMING_CORNER,
                TIMING_VOLTAGE,
                pathgroup,
                _scale_wns_for_pathgroup(base_metrics['WNS'], pathgroup),
                _scale_tns_for_pathgroup(base_metrics['TNS'], pathgroup),
                _scale_nvp_for_pathgroup(base_metrics['NVP'], pathgroup),
            ))

    return seed_rows


def _seed_timing_summary_from_tracker(conn, force=False):
    _ensure_timing_summary_table(conn)
    existing_count = conn.execute(
        f'SELECT COUNT(*) FROM "{TIMING_SUMMARY_TABLE}"'
    ).fetchone()[0]

    if existing_count and not force:
        return {
            'existing_count': existing_count,
            'inserted_count': 0,
        }

    if force:
        conn.execute(f'DELETE FROM "{TIMING_SUMMARY_TABLE}"')

    tracker_rows = conn.execute(
        f'''
        SELECT
            "Job",
            "Milestone",
            "Block",
            "Stage",
            "Modified",
            "Status",
            "Promote",
            "Setup_WNS_seq",
            "Setup_TNS_seq",
            "Setup_NVP_seq",
            "Hold_WNS_seq",
            "Hold_TNS_seq",
            "Hold_NVP_seq"
        FROM "{TRACKER_TABLE}"
        '''
    ).fetchall()

    seed_rows = []
    for row in tracker_rows:
        seed_rows.extend(_build_timing_seed_rows_for_tracker_row(row))

    if seed_rows:
        conn.executemany(
            f'''
            INSERT INTO "{TIMING_SUMMARY_TABLE}" (
                "Job",
                "Milestone",
                "Block",
                "Stage",
                "Source_mtime",
                "Mode",
                "TCheck",
                "TCorner",
                "Voltage",
                "Pathgroup",
                "WNS",
                "TNS",
                "NVP"
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            seed_rows,
        )

    conn.commit()
    return {
        'existing_count': existing_count,
        'inserted_count': len(seed_rows),
    }


def seed_timing_summary(force=False):
    with _connect() as conn:
        _ensure_table(conn)
        return _seed_timing_summary_from_tracker(conn, force=force)


def _timing_series_key(job_name, milestone_name, block_name):
    return '||'.join([
        str(job_name or '').strip(),
        str(milestone_name or '').strip(),
        str(block_name or '').strip(),
    ])


def _empty_sequential_metric_series():
    return {
        'WNS': [None, None, None],
        'TNS': [None, None, None],
        'NVP': [None, None, None],
    }


def _build_timing_run_groups(run_rows):
    groups = {}

    for row in run_rows:
        group_key = _timing_series_key(row['job'], row['milestone'], row['block'])
        stage_name = str(row['stage'] or '').strip().lower()
        stage_label = TIMING_STAGE_LABELS.get(stage_name)
        group = groups.setdefault(
            group_key,
            {
                'series_key': group_key,
                'Job': row['job'] or '',
                'Milestone': row['milestone'] or '',
                'Block': row['block'] or '',
                'Dft_release': row['dft_release'] or '',
                'User': row['tracker_user'] or '',
                'Promote': row['promote'] or '',
                'latest_updated_at': row['updated_at'] or row['created_at'] or '',
                'statuses': {},
                'watchlist_stages': [],
                'stage_metrics': {label: {} for label in TIMING_STAGE_LABELS.values()},
                'hold_stage_metrics': {label: {} for label in TIMING_STAGE_LABELS.values()},
                'sequential_setup': _empty_sequential_metric_series(),
                'sequential_hold': _empty_sequential_metric_series(),
            },
        )

        if row['dft_release'] and not group['Dft_release']:
            group['Dft_release'] = row['dft_release']
        if row['tracker_user'] and not group['User']:
            group['User'] = row['tracker_user']
        if row['promote'] and row['promote'].strip().lower() == 'yes':
            group['Promote'] = row['promote']
        if (row['updated_at'] or row['created_at'] or '') > group['latest_updated_at']:
            group['latest_updated_at'] = row['updated_at'] or row['created_at'] or ''

        if stage_label:
            group['watchlist_stages'].append(stage_label)
            if row['run_status']:
                group['statuses'][stage_label] = row['run_status']

    for group in groups.values():
        unique_stage_names = []
        for stage_label in group['watchlist_stages']:
            if stage_label not in unique_stage_names:
                unique_stage_names.append(stage_label)
        group['watchlist_stages'] = unique_stage_names

    return groups


def _apply_tracker_sequential_rows(groups, tracker_rows):
    for row in tracker_rows:
        group_key = _timing_series_key(row['Job'], row['Milestone'], row['Block'])
        group = groups.get(group_key)
        stage_name = str(row['Stage'] or '').strip().lower()

        if not group or stage_name not in TIMING_STAGE_ORDER:
            continue

        stage_index = TIMING_STAGE_ORDER.index(stage_name)
        group['sequential_setup']['WNS'][stage_index] = _parse_float(row['Setup_WNS_seq'])
        group['sequential_setup']['TNS'][stage_index] = _parse_float(row['Setup_TNS_seq'])
        group['sequential_setup']['NVP'][stage_index] = _parse_int(row['Setup_NVP_seq'])


def _apply_timing_summary_rows(groups, summary_rows):
    available_pathgroups = set()

    for row in summary_rows:
        group_key = _timing_series_key(row['Job'], row['Milestone'], row['Block'])
        group = groups.get(group_key)
        stage_name = str(row['Stage'] or '').strip().lower()
        stage_label = TIMING_STAGE_LABELS.get(stage_name)
        tcheck_name = str(row['TCheck'] or '').strip().lower()
        pathgroup_name = str(row['Pathgroup'] or '').strip()

        if not group or not stage_label or not pathgroup_name:
            continue

        metric_payload = {
            'WNS': None if row['WNS'] is None else round(float(row['WNS']), 3),
            'TNS': None if row['TNS'] is None else round(float(row['TNS']), 3),
            'NVP': None if row['NVP'] is None else int(row['NVP']),
        }

        if tcheck_name == 'setup':
            group['stage_metrics'][stage_label][pathgroup_name] = metric_payload
            available_pathgroups.add(pathgroup_name)
        elif tcheck_name == 'hold':
            group['hold_stage_metrics'][stage_label][pathgroup_name] = metric_payload
            if pathgroup_name == 'all':
                stage_index = TIMING_STAGE_ORDER.index(stage_name)
                group['sequential_hold']['WNS'][stage_index] = metric_payload['WNS']
                group['sequential_hold']['TNS'][stage_index] = metric_payload['TNS']
                group['sequential_hold']['NVP'][stage_index] = metric_payload['NVP']

    return sorted(available_pathgroups, key=str.lower)


def _get_watchlist_tracker_setup_rows(conn, user_id, watchlist_name):
    return conn.execute(
        f'''
        SELECT DISTINCT
            tracker."Job",
            tracker."Milestone",
            tracker."Block",
            tracker."Stage",
            tracker."Setup_WNS_seq",
            tracker."Setup_TNS_seq",
            tracker."Setup_NVP_seq"
        FROM "{TRACKER_TABLE}" AS tracker
        JOIN (
            SELECT DISTINCT "job", "milestone", "block", "stage"
            FROM "{TABLE_NAME}"
            WHERE "user_id" = ?
              AND "record_type" = ?
              AND lower("watchlist_name") = lower(?)
        ) AS watchlist_runs
          ON tracker."Job" = watchlist_runs."job"
         AND tracker."Milestone" = watchlist_runs."milestone"
         AND tracker."Block" = watchlist_runs."block"
         AND lower(tracker."Stage") = lower(watchlist_runs."stage")
        WHERE lower(tracker."Stage") IN ('place', 'clock', 'route')
        ORDER BY lower(tracker."Block") ASC,
                 lower(tracker."Job") ASC,
                 lower(tracker."Stage") ASC
        ''',
        (user_id, RUN_RECORD, watchlist_name),
    ).fetchall()


def _get_watchlist_timing_summary_rows(conn, user_id, watchlist_name):
    return conn.execute(
        f'''
        SELECT DISTINCT timing.*
        FROM "{TIMING_SUMMARY_TABLE}" AS timing
        JOIN (
            SELECT DISTINCT "job", "milestone", "block", "stage"
            FROM "{TABLE_NAME}"
            WHERE "user_id" = ?
              AND "record_type" = ?
              AND lower("watchlist_name") = lower(?)
        ) AS watchlist_runs
          ON timing."Job" = watchlist_runs."job"
         AND timing."Milestone" = watchlist_runs."milestone"
         AND timing."Block" = watchlist_runs."block"
         AND lower(timing."Stage") = lower(watchlist_runs."stage")
        WHERE lower(timing."Stage") IN ('place', 'clock', 'route')
          AND lower(timing."TCheck") = 'setup'
        ORDER BY lower(timing."Block") ASC,
                 lower(timing."Job") ASC,
                 lower(timing."Stage") ASC,
                 lower(timing."TCheck") ASC,
                 lower(timing."Pathgroup") ASC
        ''',
        (user_id, RUN_RECORD, watchlist_name),
    ).fetchall()


def _get_watchlist_timing_runs(conn, user_id, watchlist_name):
    run_rows = conn.execute(
        f'''
        SELECT DISTINCT
            "job",
            "milestone",
            "block",
            "stage",
            "tracker_user",
            "dft_release",
            "run_status",
            "comments",
            "promote",
            "created_at",
            "updated_at"
        FROM "{TABLE_NAME}"
        WHERE "user_id" = ?
          AND "record_type" = ?
          AND lower("watchlist_name") = lower(?)
        ORDER BY lower("block") ASC, lower("job") ASC, lower("stage") ASC
        ''',
        (user_id, RUN_RECORD, watchlist_name),
    ).fetchall()

    groups = _build_timing_run_groups(run_rows)
    tracker_rows = _get_watchlist_tracker_setup_rows(conn, user_id, watchlist_name)
    _apply_tracker_sequential_rows(groups, tracker_rows)
    summary_rows = _get_watchlist_timing_summary_rows(conn, user_id, watchlist_name)
    available_pathgroups = _apply_timing_summary_rows(groups, summary_rows)
    runs = sorted(
        groups.values(),
        key=lambda group: (
            str(group['Block']).lower(),
            str(group['Job']).lower(),
            str(group['Milestone']).lower(),
        ),
    )
    blocks = sorted({run['Block'] for run in runs if run['Block']}, key=str.lower)

    return {
        'runs': runs,
        'blocks': blocks,
        'pathgroups': available_pathgroups,
    }


def get_timing_data(data):
    user_id, error_payload, error_status = _session_user()
    if error_payload:
        return error_payload, error_status

    requested_name = _normalize_watchlist_name((data or {}).get('watchlist_name'))

    try:
        with _connect() as conn:
            _prepare_watchlist_state(conn, user_id)
            _seed_timing_summary_from_tracker(conn, force=False)

            watchlist_row = _get_watchlist_row(conn, user_id, requested_name or DEFAULT_WATCHLIST)
            if not watchlist_row and requested_name:
                return {'success': False, 'error': 'watchlist not found'}, 404

            if not watchlist_row:
                watchlist_rows = conn.execute(
                    f'''
                    SELECT *
                    FROM "{TABLE_NAME}"
                    WHERE "user_id" = ?
                      AND "record_type" = ?
                    ORDER BY "is_default" DESC, lower("watchlist_name") ASC
                    LIMIT 1
                    ''',
                    (user_id, WATCHLIST_RECORD),
                ).fetchall()
                watchlist_row = watchlist_rows[0] if watchlist_rows else None

            canonical_name = watchlist_row['watchlist_name'] if watchlist_row else DEFAULT_WATCHLIST
            timing_payload = _get_watchlist_timing_runs(conn, user_id, canonical_name)
            timing_payload.update({
                'success': True,
                'user_id': user_id,
                'watchlist_name': canonical_name,
                'source': TIMING_SOURCE_LABEL,
                'default_block': timing_payload['blocks'][0] if timing_payload['blocks'] else '',
            })
            return timing_payload, 200
    except sqlite3.Error as error:
        return {'success': False, 'error': str(error)}, 500
