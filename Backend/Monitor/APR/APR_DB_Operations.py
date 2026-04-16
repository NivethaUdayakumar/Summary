import os
import sqlite3
from datetime import datetime, timedelta

from APR_Definitions import DB_NAME, KPI_COLUMNS, TRACKER_COLUMNS, TRACKER_TABLE


def get_db_path(base_dir):
    return os.path.join(base_dir, DB_NAME)


def connect_db(base_dir):
    os.makedirs(base_dir, exist_ok=True)
    conn = sqlite3.connect(get_db_path(base_dir), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def connect_db_file(db_file):
    os.makedirs(os.path.dirname(os.path.abspath(db_file)), exist_ok=True)
    conn = sqlite3.connect(db_file, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db(base_dir):
    conn = connect_db(base_dir)
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
    conn.commit()
    return conn


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


def remove_old_logs(log_dir, keep_days=14):
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
