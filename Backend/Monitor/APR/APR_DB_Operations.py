import os
import queue
import sqlite3
import threading
from datetime import datetime, timedelta

from APR_Definitions import (
    DB_NAME,
    KPI_COLUMNS,
    LOG_KEEP_DAYS,
    SQLITE_BUSY_TIMEOUT_MS,
    SQLITE_TIMEOUT_SECONDS,
    TIMING_DETAIL_TABLE,
    TIMING_SUMMARY_COLUMNS,
    TIMING_SUMMARY_TABLE,
    TRACKER_COLUMNS,
    TRACKER_ID_COLUMNS,
    TRACKER_TABLE,
    WRITER_STOP,
    WRITER_TIMING,
    WRITER_TRACKER,
)


def get_db_path(base_dir):
    return os.path.join(base_dir, DB_NAME)


def connect_db_file(db_file):
    os.makedirs(os.path.dirname(os.path.abspath(db_file)), exist_ok=True)
    conn = sqlite3.connect(db_file, timeout=SQLITE_TIMEOUT_SECONDS)
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")
    return conn


def ensure_columns(conn, table_name, column_defs):
    existing = {row["name"] for row in conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()}
    for column_name, column_type in column_defs:
        if column_name not in existing:
            conn.execute(f'ALTER TABLE "{table_name}" ADD COLUMN "{column_name}" {column_type}')


def ensure_tracker_table(conn):
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {TRACKER_TABLE} (
            Job TEXT,
            Milestone TEXT,
            Block TEXT,
            Stage TEXT,
            Dft_release TEXT,
            User TEXT,
            Created TEXT,
            Modified TEXT,
            Rerun INTEGER DEFAULT 0,
            Status TEXT,
            Comments TEXT,
            Promote TEXT,
            UNIQUE(Job, Milestone, Block, Stage)
        )
    """)
    tracker_cols = {
        row["name"] for row in conn.execute(f'PRAGMA table_info("{TRACKER_TABLE}")').fetchall()
    }
    for col in TRACKER_COLUMNS + KPI_COLUMNS:
        if col not in tracker_cols:
            conn.execute(f'ALTER TABLE "{TRACKER_TABLE}" ADD COLUMN "{col}" TEXT')
    conn.execute(f'CREATE INDEX IF NOT EXISTS idx_tracker_status ON "{TRACKER_TABLE}"("Status")')
    conn.execute(f'CREATE INDEX IF NOT EXISTS idx_tracker_stage ON "{TRACKER_TABLE}"("Stage")')


def upsert_tracker(conn, rec):
    cols = TRACKER_COLUMNS + KPI_COLUMNS
    insert_cols = ", ".join([f'"{col}"' for col in cols])
    insert_vals = ", ".join(["?"] * len(cols))
    update_cols = [col for col in cols if col not in {"Job", "Milestone", "Block", "Stage", "Created"}]
    update_sql = ", ".join([f'"{col}"=excluded."{col}"' for col in update_cols])
    conn.execute(f"""
        INSERT INTO {TRACKER_TABLE} ({insert_cols})
        VALUES ({insert_vals})
        ON CONFLICT(Job, Milestone, Block, Stage) DO UPDATE SET
            {update_sql}
    """, [rec.get(col, "") for col in cols])
    conn.commit()


def ensure_timing_tables(conn):
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {TIMING_SUMMARY_TABLE} (
            Job TEXT,
            Milestone TEXT,
            Block TEXT,
            Stage TEXT,
            Source_mtime INTEGER,
            Mode TEXT,
            TCheck TEXT,
            TCorner TEXT,
            Voltage TEXT,
            Pathgroup TEXT,
            WNS REAL,
            TNS REAL,
            NVP INTEGER
        )
    """)
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {TIMING_DETAIL_TABLE} (
            Job TEXT,
            Milestone TEXT,
            Block TEXT,
            Stage TEXT,
            Source_mtime INTEGER,
            Mode TEXT,
            TCheck TEXT,
            TCorner TEXT,
            Voltage TEXT,
            Pathgroup TEXT,
            Slack REAL,
            Endpoint TEXT,
            Startpoint TEXT,
            Timing TEXT,
            Report TEXT
        )
    """)

    ensure_columns(conn, TIMING_SUMMARY_TABLE, [
        ("Job", "TEXT"),
        ("Milestone", "TEXT"),
        ("Block", "TEXT"),
        ("Stage", "TEXT"),
        ("Source_mtime", "INTEGER"),
        ("Mode", "TEXT"),
        ("TCheck", "TEXT"),
        ("TCorner", "TEXT"),
        ("Voltage", "TEXT"),
        ("Pathgroup", "TEXT"),
        ("WNS", "REAL"),
        ("TNS", "REAL"),
        ("NVP", "INTEGER"),
    ])
    ensure_columns(conn, TIMING_DETAIL_TABLE, [
        ("Job", "TEXT"),
        ("Milestone", "TEXT"),
        ("Block", "TEXT"),
        ("Stage", "TEXT"),
        ("Source_mtime", "INTEGER"),
        ("Mode", "TEXT"),
        ("TCheck", "TEXT"),
        ("TCorner", "TEXT"),
        ("Voltage", "TEXT"),
        ("Pathgroup", "TEXT"),
        ("Slack", "REAL"),
        ("Endpoint", "TEXT"),
        ("Startpoint", "TEXT"),
        ("Timing", "TEXT"),
        ("Report", "TEXT"),
    ])

    conn.execute(f"""
        CREATE INDEX IF NOT EXISTS idx_apr_timing_detail_scope
        ON {TIMING_DETAIL_TABLE}("Job", "Milestone", "Block", "Stage")
    """)
    conn.execute(f"""
        CREATE INDEX IF NOT EXISTS idx_apr_timing_detail_filters
        ON {TIMING_DETAIL_TABLE}(
            "Job", "Milestone", "Block", "Stage",
            "Mode", "TCheck", "TCorner", "Voltage", "Pathgroup", "Timing"
        )
    """)
    conn.execute(f"""
        CREATE INDEX IF NOT EXISTS idx_apr_timing_detail_endpoint
        ON {TIMING_DETAIL_TABLE}("Endpoint")
    """)
    conn.execute(f"""
        CREATE INDEX IF NOT EXISTS idx_apr_timing_summary_scope
        ON {TIMING_SUMMARY_TABLE}("Job", "Milestone", "Block", "Stage")
    """)


def get_scope_values(scope):
    return [scope[column] for column in TRACKER_ID_COLUMNS]


def delete_timing_stage_rows(conn, scope):
    where_sql = " AND ".join([f'"{column}" = ?' for column in TRACKER_ID_COLUMNS])
    params = get_scope_values(scope)
    conn.execute(f'DELETE FROM {TIMING_DETAIL_TABLE} WHERE {where_sql}', params)
    conn.execute(f'DELETE FROM {TIMING_SUMMARY_TABLE} WHERE {where_sql}', params)


def insert_timing_detail(conn, payload):
    timing_rows = payload.get("timing_rows", [])
    if not timing_rows:
        return

    scope_values = get_scope_values(payload["scope"])
    source_mtime = payload.get("source_mtime")
    rows = [tuple(scope_values + [source_mtime] + list(row)) for row in timing_rows]
    conn.executemany(f"""
        INSERT INTO {TIMING_DETAIL_TABLE} (
            "Job", "Milestone", "Block", "Stage", "Source_mtime",
            "Mode", "TCheck", "TCorner", "Voltage", "Pathgroup",
            "Slack", "Endpoint", "Startpoint", "Timing", "Report"
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)


def get_summary_options(report_combos):
    options = {}
    for index, column in enumerate(TIMING_SUMMARY_COLUMNS):
        values = sorted({combo[index] for combo in report_combos if combo[index] is not None})
        if column != "TCheck" and values:
            values.append("all")
        options[column] = values
    return options


def query_violated_summary(conn, scope, filters):
    where = [f'"{column}" = ?' for column in TRACKER_ID_COLUMNS]
    params = get_scope_values(scope)
    where.append('Timing = "VIOLATED"')

    for column, value in filters.items():
        if value != "all":
            where.append(f'"{column}" = ?')
            params.append(value)

    row = conn.execute(f"""
        WITH ranked AS (
            SELECT
                Slack,
                Endpoint,
                ROW_NUMBER() OVER (
                    PARTITION BY Endpoint
                    ORDER BY Slack ASC, Endpoint ASC
                ) AS rn
            FROM {TIMING_DETAIL_TABLE}
            WHERE {" AND ".join(where)}
        )
        SELECT
            MIN(Slack) AS WNS,
            SUM(Slack) AS TNS,
            COUNT(*) AS NVP
        FROM ranked
        WHERE rn = 1
    """, params).fetchone()

    if not row:
        return 0.0, 0.0, 0

    wns = round(row[0], 3) if row[0] is not None else 0.0
    tns = round(row[1], 3) if row[1] is not None else 0.0
    nvp = int(row[2]) if row[2] is not None else 0
    if wns == 0.0:
        tns = 0.0
    return wns, tns, nvp


def insert_timing_summary(conn, payload):
    report_combos = {tuple(combo) for combo in payload.get("report_combos", set())}
    options = get_summary_options(report_combos)
    if not all(options.get(column) for column in TIMING_SUMMARY_COLUMNS):
        return

    combos = [[]]
    for column in TIMING_SUMMARY_COLUMNS:
        next_combos = []
        for combo in combos:
            for value in options[column]:
                next_combos.append(combo + [value])
        combos = next_combos

    summary_rows = []
    scope = payload["scope"]
    scope_values = get_scope_values(scope)
    source_mtime = payload.get("source_mtime")
    for combo in combos:
        combo_key = tuple(combo)
        if "all" not in combo_key and combo_key not in report_combos:
            continue

        filters = dict(zip(TIMING_SUMMARY_COLUMNS, combo))
        wns, tns, nvp = query_violated_summary(conn, scope, filters)
        summary_rows.append((
            *scope_values,
            source_mtime,
            filters["Mode"],
            filters["TCheck"],
            filters["TCorner"],
            filters["Voltage"],
            filters["Pathgroup"],
            wns,
            tns,
            nvp,
        ))

    if not summary_rows:
        return

    conn.executemany(f"""
        INSERT INTO {TIMING_SUMMARY_TABLE} (
            "Job", "Milestone", "Block", "Stage", "Source_mtime",
            "Mode", "TCheck", "TCorner", "Voltage", "Pathgroup",
            "WNS", "TNS", "NVP"
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, summary_rows)


def write_timing_stage(conn, payload):
    ensure_timing_tables(conn)
    conn.execute("BEGIN IMMEDIATE")
    try:
        delete_timing_stage_rows(conn, payload["scope"])
        insert_timing_detail(conn, payload)
        insert_timing_summary(conn, payload)
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return {
        "scope": payload["scope"],
        "report_count": payload.get("report_count", 0),
        "row_count": len(payload.get("timing_rows", [])),
        "error_count": payload.get("error_count", 0),
    }


def write_timing_stage_file(db_path, payload):
    conn = connect_db_file(db_path)
    try:
        ensure_tracker_table(conn)
        ensure_timing_tables(conn)
        return write_timing_stage(conn, payload)
    finally:
        conn.close()


def get_timing_stage_mtime(db_path, scope):
    if not os.path.exists(db_path):
        return None

    conn = connect_db_file(db_path)
    try:
        params = get_scope_values(scope)
        where_sql = " AND ".join([f'"{column}" = ?' for column in TRACKER_ID_COLUMNS])
        try:
            row = conn.execute(
                f'SELECT MAX("Source_mtime") FROM {TIMING_SUMMARY_TABLE} WHERE {where_sql}',
                params,
            ).fetchone()
        except sqlite3.Error:
            return None
    finally:
        conn.close()

    if not row or row[0] is None:
        return None
    return int(row[0])


class SQLiteWriter:
    def __init__(self, db_path):
        self._db_path = db_path
        self._failed = None
        self._failure_lock = threading.Lock()
        self._requests = queue.Queue()
        self._thread = threading.Thread(target=self._run, name="apr-sqlite-writer")

    def start(self):
        self._thread.start()
        return self

    def submit_tracker(self, tracker_record):
        self.check()
        self._requests.put((WRITER_TRACKER, dict(tracker_record), None))

    def submit_timing(self, payload):
        self.check()
        reply = queue.Queue(maxsize=1)
        self._requests.put((WRITER_TIMING, payload, reply))
        result = reply.get()
        if isinstance(result, Exception):
            raise result
        return result

    def close(self):
        reply = queue.Queue(maxsize=1)
        self._requests.put((WRITER_STOP, None, reply))
        result = reply.get()
        self._thread.join()
        if isinstance(result, Exception):
            raise result
        self.check()

    def check(self):
        with self._failure_lock:
            if self._failed is not None:
                raise RuntimeError("SQLite writer thread failed") from self._failed

    def _run(self):
        conn = connect_db_file(self._db_path)
        ensure_tracker_table(conn)
        ensure_timing_tables(conn)
        conn.commit()
        try:
            while True:
                kind, payload, reply = self._requests.get()
                result = True
                try:
                    if kind == WRITER_TRACKER:
                        upsert_tracker(conn, payload)
                    elif kind == WRITER_TIMING:
                        result = write_timing_stage(conn, payload)
                    elif kind == WRITER_STOP:
                        if reply is not None:
                            reply.put(True)
                        return
                    else:
                        raise ValueError(f"Unknown SQLite writer request: {kind}")
                except Exception as exc:
                    with self._failure_lock:
                        if self._failed is None:
                            self._failed = exc
                    result = exc
                finally:
                    self._requests.task_done()

                if reply is not None:
                    reply.put(result)
        finally:
            conn.close()


def remove_old_logs(log_dir, keep_days=LOG_KEEP_DAYS):
    if not os.path.isdir(log_dir):
        return
    cutoff = datetime.now() - timedelta(days=keep_days)
    for name in os.listdir(log_dir):
        if not name.startswith("APR_") or not name.endswith(".log"):
            continue
        path = os.path.join(log_dir, name)
        try:
            if datetime.fromtimestamp(os.path.getmtime(path)) < cutoff:
                os.remove(path)
        except Exception:
            pass
