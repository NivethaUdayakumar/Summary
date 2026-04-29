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
    TIMING_SUMMARY_TABLE,
    TRACKER_COLUMNS,
    TRACKER_TABLE,
    WRITER_STOP,
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
    ensure_columns(conn, TRACKER_TABLE, [(col, "TEXT") for col in TRACKER_COLUMNS + KPI_COLUMNS])
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


def cleanup_tracker_db_schema(conn):
    for table_name in (TIMING_DETAIL_TABLE, TIMING_SUMMARY_TABLE):
        conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')


def process_tracker_update(conn, tracker_record):
    conn.execute("BEGIN IMMEDIATE")
    try:
        upsert_tracker(conn, tracker_record)
        conn.commit()
    except Exception:
        conn.rollback()
        raise


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
        cleanup_tracker_db_schema(conn)
        conn.commit()
        try:
            while True:
                kind, request_data, reply = self._requests.get()
                result = True
                try:
                    if kind == WRITER_TRACKER:
                        process_tracker_update(conn, request_data)
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
