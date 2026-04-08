import sqlite3
from pathlib import Path
from datetime import datetime


PROJECTS_BASE_DIR = Path("/proj")


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_db_path(project_code: str) -> Path:
    db_dir = PROJECTS_BASE_DIR / project_code / "DB"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / f"{project_code}_DB.db"


def connect_db(project_code: str):
    db_path = get_db_path(project_code)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_apr_tables(project_code: str):
    conn = connect_db(project_code)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS APR_Tracker (
            run_id TEXT PRIMARY KEY,
            project_code TEXT,
            block TEXT,
            run_name TEXT,
            run_path TEXT,
            status TEXT,
            hidden INTEGER DEFAULT 0,
            last_seen_ts TEXT,
            last_modified_ts TEXT,
            manual_update_ts TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS APR_LOG (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            level TEXT DEFAULT 'INFO',
            message TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def log_message(project_code: str, message: str, level: str = "INFO"):
    conn = connect_db(project_code)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO APR_LOG (timestamp, level, message)
        VALUES (?, ?, ?)
    """, (now_str(), level, message))
    conn.commit()
    conn.close()


def get_existing_tracker_rows(project_code: str):
    conn = connect_db(project_code)
    cur = conn.cursor()
    cur.execute('SELECT * FROM "APR_Tracker"')
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_tracker_row_by_id(project_code: str, run_id: str):
    conn = connect_db(project_code)
    cur = conn.cursor()
    cur.execute('SELECT * FROM "APR_Tracker" WHERE run_id = ?', (run_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def upsert_tracker_row(project_code: str, row: dict):
    conn = connect_db(project_code)
    cur = conn.cursor()

    existing = get_tracker_row_by_id(project_code, row["run_id"])
    hidden = existing["hidden"] if existing and "hidden" in existing else row.get("hidden", 0)
    created_at = existing["created_at"] if existing and existing.get("created_at") else row.get("created_at", now_str())

    cur.execute("""
        INSERT INTO APR_Tracker (
            run_id, project_code, block, run_name, run_path, status,
            hidden, last_seen_ts, last_modified_ts, manual_update_ts,
            created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_id) DO UPDATE SET
            project_code=excluded.project_code,
            block=excluded.block,
            run_name=excluded.run_name,
            run_path=excluded.run_path,
            status=excluded.status,
            hidden=?,
            last_seen_ts=excluded.last_seen_ts,
            last_modified_ts=excluded.last_modified_ts,
            manual_update_ts=excluded.manual_update_ts,
            updated_at=excluded.updated_at
    """, (
        row["run_id"],
        row.get("project_code", ""),
        row.get("block", ""),
        row.get("run_name", ""),
        row.get("run_path", ""),
        row.get("status", ""),
        hidden,
        row.get("last_seen_ts", ""),
        row.get("last_modified_ts", ""),
        row.get("manual_update_ts", ""),
        created_at,
        row.get("updated_at", now_str()),
        hidden
    ))

    conn.commit()
    conn.close()


def mark_missing_runs_failed(project_code: str, active_run_ids: set):
    conn = connect_db(project_code)
    cur = conn.cursor()

    cur.execute('SELECT run_id, hidden FROM "APR_Tracker"')
    rows = cur.fetchall()

    for run_id, hidden in rows:
        if hidden == 1:
            continue
        if run_id not in active_run_ids:
            cur.execute("""
                UPDATE APR_Tracker
                SET status = ?, updated_at = ?
                WHERE run_id = ?
            """, ("failed", now_str(), run_id))

    conn.commit()
    conn.close()


def get_visible_runs(project_code: str):
    conn = connect_db(project_code)
    cur = conn.cursor()
    cur.execute('SELECT * FROM "APR_Tracker" WHERE hidden = 0')
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows