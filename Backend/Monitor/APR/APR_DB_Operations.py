import csv
import os
import queue
import sqlite3
import threading
from datetime import datetime, timedelta

from APR_Definitions import (
    DB_NAME,
    KPI_COLUMNS,
    LOG_KEEP_DAYS,
    STATE_DONE,
    SQLITE_BUSY_TIMEOUT_MS,
    SQLITE_TIMEOUT_SECONDS,
    TIMING_DETAIL_TABLE,
    TIMING_SUMMARY_COLUMNS,
    TIMING_SUMMARY_TABLE,
    TRACKER_COLUMNS,
    TRACKER_ID_COLUMNS,
    TRACKER_TABLE,
    WRITER_STOP,
    WRITER_TRACKER,
)


TIMING_CSV_STATE_TABLE = "APR_TIMING_CSV_STATE"


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
    ensure_columns(conn, TRACKER_TABLE, [(col, "TEXT") for col in TRACKER_COLUMNS + KPI_COLUMNS])
    drop_tracker_timing_sync_columns(conn)
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


def ensure_timing_tables(conn):
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {TIMING_SUMMARY_TABLE} (
            Job TEXT,
            Milestone TEXT,
            Block TEXT,
            Stage TEXT,
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


def drop_legacy_timing_csv_state_table(conn):
    conn.execute(f'DROP TABLE IF EXISTS "{TIMING_CSV_STATE_TABLE}"')


def drop_tracker_timing_sync_columns(conn):
    existing = {row["name"] for row in conn.execute(f'PRAGMA table_info("{TRACKER_TABLE}")').fetchall()}
    for column_name in ("Timing_csv_mtime", "Timing_csv_size"):
        if column_name not in existing:
            continue

        try:
            conn.execute(f'ALTER TABLE "{TRACKER_TABLE}" DROP COLUMN "{column_name}"')
        except sqlite3.Error:
            # Leave legacy columns in place if the SQLite runtime does not support DROP COLUMN.
            pass


def drop_timing_write_indexes(conn):
    for index_name in (
        "idx_apr_timing_detail_scope",
        "idx_apr_timing_detail_filters",
        "idx_apr_timing_detail_endpoint",
    ):
        conn.execute(f'DROP INDEX IF EXISTS "{index_name}"')


def drop_timing_source_mtime_columns(conn):
    for table_name in (TIMING_SUMMARY_TABLE, TIMING_DETAIL_TABLE):
        existing = {row["name"] for row in conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()}
        if "Source_mtime" not in existing:
            continue

        try:
            conn.execute(f'ALTER TABLE "{table_name}" DROP COLUMN "Source_mtime"')
        except sqlite3.Error:
            # Leave legacy columns in place if the SQLite runtime does not support DROP COLUMN.
            pass


def ensure_timing_schema(conn):
    ensure_timing_tables(conn)
    drop_timing_write_indexes(conn)
    drop_timing_source_mtime_columns(conn)
    drop_legacy_timing_csv_state_table(conn)


def parse_optional_float(value):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def get_timing_scope_from_csv_path(csv_path):
    normalized_path = os.path.normpath(csv_path).replace("\\", "/").strip()
    parts = normalized_path.split("/")
    if len(parts) < 5 or parts[-5] != "APR_RUNS":
        raise ValueError(f"Invalid timing CSV path: {csv_path}")

    return {
        "Job": parts[-2],
        "Milestone": parts[-3],
        "Block": parts[-4],
        "Stage": os.path.splitext(parts[-1])[0],
    }


def read_timing_stage_csv(csv_path):
    scope = get_timing_scope_from_csv_path(csv_path)
    timing_rows = []
    report_combos = set()
    report_paths = set()

    with open(csv_path, "r", encoding="utf-8", newline="") as infile:
        reader = csv.DictReader(infile)
        if reader.fieldnames is None:
            raise ValueError(f"Timing CSV missing header: {csv_path}")

        for row in reader:
            if not any(str(value or "").strip() for value in row.values()):
                continue

            mode = str(row.get("Mode", "")).strip()
            tcheck = str(row.get("TCheck", "")).strip()
            tcorner = str(row.get("TCorner", "")).strip()
            voltage = str(row.get("Voltage", "")).strip()
            pathgroup = str(row.get("Pathgroup", "")).strip()
            combo = (mode, tcheck, tcorner, voltage, pathgroup)
            if all(combo):
                report_combos.add(combo)

            report_path = str(row.get("Report", "")).strip()
            if report_path:
                report_paths.add(report_path)

            timing_rows.append((
                mode,
                tcheck,
                tcorner,
                voltage,
                pathgroup,
                parse_optional_float(row.get("Slack")),
                str(row.get("Endpoint", "")).strip(),
                str(row.get("Startpoint", "")).strip(),
                str(row.get("Timing", "")).strip(),
                report_path,
            ))

    return {
        "error_count": 0,
        "report_combos": report_combos,
        "report_count": len(report_paths),
        "scope": scope,
        "timing_rows": timing_rows,
    }


def build_tracker_scope(rec):
    return {column: str(rec.get(column, "")).strip() for column in TRACKER_ID_COLUMNS}


def get_timing_csv_path_for_scope(db_path, scope):
    if not all(scope.get(column) for column in TRACKER_ID_COLUMNS):
        return None

    dashai_dir = os.path.dirname(os.path.abspath(db_path))
    return os.path.join(
        dashai_dir,
        "APR_RUNS",
        scope["Block"],
        scope["Milestone"],
        scope["Job"],
        f'{scope["Stage"]}.csv',
    )


def get_tracker_status_record(conn, scope):
    where_sql = " AND ".join([f'"{column}" = ?' for column in TRACKER_ID_COLUMNS])
    row = conn.execute(
        f'''
        SELECT "Status", "Comments"
        FROM "{TRACKER_TABLE}"
        WHERE {where_sql}
        LIMIT 1
        ''',
        get_scope_values(scope),
    ).fetchone()
    return dict(row) if row is not None else None


def should_sync_timing_csv(tracker_record):
    status = str(tracker_record.get("Status", "")).strip()
    return status == STATE_DONE


def get_scope_values(scope):
    return [scope[column] for column in TRACKER_ID_COLUMNS]


def delete_timing_stage_rows(conn, scope):
    where_sql = " AND ".join([f'"{column}" = ?' for column in TRACKER_ID_COLUMNS])
    params = get_scope_values(scope)
    conn.execute(f'DELETE FROM {TIMING_DETAIL_TABLE} WHERE {where_sql}', params)
    conn.execute(f'DELETE FROM {TIMING_SUMMARY_TABLE} WHERE {where_sql}', params)


def insert_timing_detail(conn, timing_data):
    timing_rows = timing_data.get("timing_rows", [])
    if not timing_rows:
        return

    scope_values = get_scope_values(timing_data["scope"])
    rows = [tuple(scope_values + list(row)) for row in timing_rows]
    conn.executemany(f"""
        INSERT INTO {TIMING_DETAIL_TABLE} (
            "Job", "Milestone", "Block", "Stage",
            "Mode", "TCheck", "TCorner", "Voltage", "Pathgroup",
            "Slack", "Endpoint", "Startpoint", "Timing", "Report"
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)


def get_summary_options(report_combos):
    options = {}
    for index, column in enumerate(TIMING_SUMMARY_COLUMNS):
        values = sorted({combo[index] for combo in report_combos if combo[index] is not None})
        if column != "TCheck" and values:
            values.append("all")
        options[column] = values
    return options


def build_timing_summary_rows(timing_data):
    report_combos = {tuple(combo) for combo in timing_data.get("report_combos", set())}
    options = get_summary_options(report_combos)
    if not all(options.get(column) for column in TIMING_SUMMARY_COLUMNS):
        return []

    combos = [[]]
    for column in TIMING_SUMMARY_COLUMNS:
        next_combos = []
        for combo in combos:
            for value in options[column]:
                next_combos.append(combo + [value])
        combos = next_combos

    violated_rows = [row for row in timing_data.get("timing_rows", []) if row[8] == "VIOLATED"]
    summary_rows = []
    scope = timing_data["scope"]
    scope_values = get_scope_values(scope)
    for combo in combos:
        combo_key = tuple(combo)
        if "all" not in combo_key and combo_key not in report_combos:
            continue

        filters = dict(zip(TIMING_SUMMARY_COLUMNS, combo))
        endpoint_slacks = {}
        for row in violated_rows:
            row_values = {
                "Mode": row[0],
                "TCheck": row[1],
                "TCorner": row[2],
                "Voltage": row[3],
                "Pathgroup": row[4],
            }
            if any(filters[column] != "all" and row_values[column] != filters[column] for column in TIMING_SUMMARY_COLUMNS):
                continue

            endpoint = row[6]
            slack = row[5]
            previous_slack = endpoint_slacks.get(endpoint)
            if previous_slack is None or slack < previous_slack:
                endpoint_slacks[endpoint] = slack

        if endpoint_slacks:
            slack_values = list(endpoint_slacks.values())
            wns = round(min(slack_values), 3)
            tns = round(sum(slack_values), 3)
            nvp = len(slack_values)
            if wns == 0.0:
                tns = 0.0
        else:
            wns, tns, nvp = 0.0, 0.0, 0

        summary_rows.append((
            *scope_values,
            filters["Mode"],
            filters["TCheck"],
            filters["TCorner"],
            filters["Voltage"],
            filters["Pathgroup"],
            wns,
            tns,
            nvp,
        ))

    return summary_rows


def insert_timing_summary(conn, timing_data):
    summary_rows = build_timing_summary_rows(timing_data)
    if not summary_rows:
        return

    conn.executemany(f"""
        INSERT INTO {TIMING_SUMMARY_TABLE} (
            "Job", "Milestone", "Block", "Stage",
            "Mode", "TCheck", "TCorner", "Voltage", "Pathgroup",
            "WNS", "TNS", "NVP"
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, summary_rows)


def write_timing_stage(conn, timing_data):
    delete_timing_stage_rows(conn, timing_data["scope"])
    insert_timing_detail(conn, timing_data)
    insert_timing_summary(conn, timing_data)
    return {
        "scope": timing_data["scope"],
        "report_count": timing_data.get("report_count", 0),
        "row_count": len(timing_data.get("timing_rows", [])),
        "error_count": timing_data.get("error_count", 0),
    }


def sync_timing_csv_file(conn, csv_path):
    timing_data = read_timing_stage_csv(csv_path)
    result = write_timing_stage(conn, timing_data)
    return result, timing_data["scope"]


def sync_tracker_timing_csv(conn, db_path, tracker_record):
    if not should_sync_timing_csv(tracker_record):
        return None

    scope = build_tracker_scope(tracker_record)
    csv_path = get_timing_csv_path_for_scope(db_path, scope)
    if not csv_path or not os.path.exists(csv_path):
        return None

    result, _timing_scope = sync_timing_csv_file(conn, csv_path)
    return result


def process_tracker_update(conn, db_path, tracker_record):
    scope = build_tracker_scope(tracker_record)
    previous_tracker_record = get_tracker_status_record(conn, scope)
    was_sync_ready = should_sync_timing_csv(previous_tracker_record or {})

    conn.execute("BEGIN IMMEDIATE")
    try:
        upsert_tracker(conn, tracker_record)
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    if not should_sync_timing_csv(tracker_record) or was_sync_ready:
        return

    conn.execute("BEGIN IMMEDIATE")
    try:
        sync_tracker_timing_csv(conn, db_path, tracker_record)
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def write_timing_stage_file(db_path, csv_path):
    conn = connect_db_file(db_path)
    try:
        ensure_tracker_table(conn)
        ensure_timing_schema(conn)
        conn.execute("BEGIN IMMEDIATE")
        try:
            result, _scope = sync_timing_csv_file(conn, csv_path)
            conn.commit()
            return result
        except Exception:
            conn.rollback()
            raise
    finally:
        conn.close()


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
        ensure_timing_schema(conn)
        conn.commit()
        try:
            while True:
                kind, request_data, reply = self._requests.get()
                result = True
                try:
                    if kind == WRITER_TRACKER:
                        process_tracker_update(conn, self._db_path, request_data)
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
