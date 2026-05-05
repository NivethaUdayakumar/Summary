import os
import queue
import sqlite3
import threading

import APR_VARS


def get_db_path(base_dir):
    """
    Function Name: get_db_path
    Purpose: Build the absolute tracker database path inside the APR DashAI directory.
    Input Params: base_dir (str)
    Output: db_path (str)
    """
    return os.path.abspath(os.path.join(base_dir, APR_VARS.get_setting("DB_NAME")))


def connect_db_file(db_file):
    """
    Function Name: connect_db_file
    Purpose: Open the APR tracker SQLite database with the configured timeout and WAL settings.
    Input Params: db_file (str)
    Output: conn (sqlite3.Connection)
    """
    absolute_db_file = os.path.abspath(db_file)
    os.makedirs(os.path.dirname(absolute_db_file), exist_ok=True)
    conn = sqlite3.connect(
        absolute_db_file,
        timeout=APR_VARS.get_setting("SQLITE_TIMEOUT_SECONDS"),
    )
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout={APR_VARS.get_setting('SQLITE_BUSY_TIMEOUT_MS')}")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")
    return conn


def ensure_columns(conn, table_name, column_defs):
    """
    Function Name: ensure_columns
    Purpose: Add any missing tracker columns and backfill blank text values so old rows stay compatible with new KPI fields.
    Input Params: conn (sqlite3.Connection), table_name (str), column_defs (list[tuple[str, str]])
    Output: outputs (None)
    """
    existing = {row["name"] for row in conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()}
    for column_name, column_type in column_defs:
        if column_name not in existing:
            conn.execute(f'ALTER TABLE "{table_name}" ADD COLUMN "{column_name}" {column_type}')
            existing.add(column_name)
        if "TEXT" in str(column_type).upper():
            conn.execute(f'UPDATE "{table_name}" SET "{column_name}" = \'\' WHERE "{column_name}" IS NULL')


def ensure_tracker_table(conn):
    """
    Function Name: ensure_tracker_table
    Purpose: Create the APR tracker table and dynamically extend it with any new configured tracker or KPI columns.
    Input Params: conn (sqlite3.Connection)
    Output: outputs (None)
    """
    tracker_table = APR_VARS.get_setting("TRACKER_TABLE")
    tracker_columns = list(APR_VARS.get_setting("TRACKER_COLUMNS"))
    kpi_columns = list(APR_VARS.get_setting("KPI_COLUMNS"))
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {tracker_table} (
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
        """
    )
    ensure_columns(conn, tracker_table, [(column_name, "TEXT") for column_name in tracker_columns + kpi_columns])
    conn.execute(f'CREATE INDEX IF NOT EXISTS idx_tracker_status ON "{tracker_table}"("Status")')
    conn.execute(f'CREATE INDEX IF NOT EXISTS idx_tracker_stage ON "{tracker_table}"("Stage")')


def upsert_tracker(conn, tracker_record):
    """
    Function Name: upsert_tracker
    Purpose: Insert or update one APR tracker row using the latest configured tracker and KPI column list.
    Input Params: conn (sqlite3.Connection), tracker_record (dict)
    Output: outputs (None)
    """
    tracker_table = APR_VARS.get_setting("TRACKER_TABLE")
    columns = list(APR_VARS.get_setting("TRACKER_COLUMNS")) + list(APR_VARS.get_setting("KPI_COLUMNS"))
    insert_columns = ", ".join([f'"{column_name}"' for column_name in columns])
    insert_values = ", ".join(["?"] * len(columns))
    update_columns = [
        column_name
        for column_name in columns
        if column_name not in {"Job", "Milestone", "Block", "Stage", "Created"}
    ]
    update_sql = ", ".join([f'"{column_name}"=excluded."{column_name}"' for column_name in update_columns])
    conn.execute(
        f"""
        INSERT INTO {tracker_table} ({insert_columns})
        VALUES ({insert_values})
        ON CONFLICT(Job, Milestone, Block, Stage) DO UPDATE SET
            {update_sql}
        """,
        [tracker_record.get(column_name, "") for column_name in columns],
    )


def cleanup_tracker_db_schema(conn):
    """
    Function Name: cleanup_tracker_db_schema
    Purpose: Remove APR timing tables from the shared tracker database so only tracker records remain there.
    Input Params: conn (sqlite3.Connection)
    Output: outputs (None)
    """
    for table_name in (
        APR_VARS.get_setting("TIMING_DETAIL_TABLE"),
        APR_VARS.get_setting("TIMING_SUMMARY_TABLE"),
    ):
        conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')


def process_tracker_update(conn, tracker_record):
    """
    Function Name: process_tracker_update
    Purpose: Refresh the tracker schema on demand and commit a single APR tracker update transaction.
    Input Params: conn (sqlite3.Connection), tracker_record (dict)
    Output: outputs (None)
    """
    conn.execute("BEGIN IMMEDIATE")
    try:
        ensure_tracker_table(conn)
        upsert_tracker(conn, tracker_record)
        conn.commit()
    except Exception:
        conn.rollback()
        raise


class SQLiteWriter:
    def __init__(self, db_path):
        """
        Function Name: __init__
        Purpose: Initialize the background SQLite writer used by the APR monitor runtime.
        Input Params: self (SQLiteWriter), db_path (str)
        Output: outputs (None)
        """
        self._db_path = os.path.abspath(db_path)
        self._failed = None
        self._failure_lock = threading.Lock()
        self._requests = queue.Queue()
        self._thread = threading.Thread(target=self._run, name="apr-sqlite-writer")

    def start(self):
        """
        Function Name: start
        Purpose: Start the background SQLite writer thread and return the writer for chaining.
        Input Params: self (SQLiteWriter)
        Output: writer (SQLiteWriter)
        """
        self._thread.start()
        return self

    def submit_tracker(self, tracker_record):
        """
        Function Name: submit_tracker
        Purpose: Queue one APR tracker row for asynchronous SQLite persistence.
        Input Params: self (SQLiteWriter), tracker_record (dict)
        Output: outputs (None)
        """
        self.check()
        self._requests.put((APR_VARS.get_setting("WRITER_TRACKER"), dict(tracker_record), None))

    def close(self):
        """
        Function Name: close
        Purpose: Stop the writer thread after all queued APR tracker work has been handled.
        Input Params: self (SQLiteWriter)
        Output: outputs (None)
        """
        reply = queue.Queue(maxsize=1)
        self._requests.put((APR_VARS.get_setting("WRITER_STOP"), None, reply))
        result = reply.get()
        self._thread.join()
        if isinstance(result, Exception):
            raise result
        self.check()

    def check(self):
        """
        Function Name: check
        Purpose: Raise the stored writer failure so the APR monitor can stop using a broken SQLite worker.
        Input Params: self (SQLiteWriter)
        Output: outputs (None)
        """
        with self._failure_lock:
            if self._failed is not None:
                raise RuntimeError("SQLite writer thread failed") from self._failed

    def _run(self):
        """
        Function Name: _run
        Purpose: Process queued tracker writes on the dedicated SQLite writer thread until a stop request arrives.
        Input Params: self (SQLiteWriter)
        Output: outputs (None)
        """
        conn = connect_db_file(self._db_path)
        ensure_tracker_table(conn)
        cleanup_tracker_db_schema(conn)
        conn.commit()
        try:
            while True:
                kind, request_data, reply = self._requests.get()
                result = True
                try:
                    if kind == APR_VARS.get_setting("WRITER_TRACKER"):
                        process_tracker_update(conn, request_data)
                    elif kind == APR_VARS.get_setting("WRITER_STOP"):
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
