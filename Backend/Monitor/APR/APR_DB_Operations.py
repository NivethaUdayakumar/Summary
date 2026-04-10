import os
import sqlite3
from datetime import datetime, timedelta

from APR_Definitions import (
    DB_NAME,
    TRACKER_TABLE,
    STATE_TABLE,
    ACTION_TABLE,
    TRACKER_COLUMNS,
    KPI_COLUMNS,
    ACTION_REUPDATE,
    ACTION_REMOVE,
    ACTION_ADD_BACK,
    now_str,
)


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
            Project TEXT,
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
            Hidden INTEGER DEFAULT 0,
            UNIQUE(Job, Milestone, Block, Stage)
        )
    """)

    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {STATE_TABLE} (
            State_key TEXT PRIMARY KEY,
            Log_path TEXT,
            Job TEXT,
            Project TEXT,
            Milestone TEXT,
            Block TEXT,
            Stage TEXT,
            Dft_release TEXT,
            User TEXT,
            Created TEXT,
            Modified TEXT,
            Last_seen_mtime INTEGER,
            Last_seen_size INTEGER,
            Last_change_time INTEGER,
            Last_extracted_mtime INTEGER,
            Last_status TEXT,
            Rerun INTEGER DEFAULT 0,
            Removed INTEGER DEFAULT 0,
            Force_extract INTEGER DEFAULT 0,
            Updated_at TEXT
        )
    """)

    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {ACTION_TABLE} (
            Id INTEGER PRIMARY KEY AUTOINCREMENT,
            State_key TEXT NOT NULL,
            Action TEXT NOT NULL,
            Status TEXT DEFAULT 'Pending',
            Created_at TEXT,
            Updated_at TEXT
        )
    """)

    tracker_cols = {
        r["name"] for r in conn.execute(f'PRAGMA table_info("{TRACKER_TABLE}")').fetchall()
    }

    if "Hidden" not in tracker_cols:
        conn.execute(f'ALTER TABLE "{TRACKER_TABLE}" ADD COLUMN "Hidden" INTEGER DEFAULT 0')

    for col in KPI_COLUMNS:
        if col not in tracker_cols:
            conn.execute(f'ALTER TABLE "{TRACKER_TABLE}" ADD COLUMN "{col}" TEXT')

    conn.execute(f'CREATE INDEX IF NOT EXISTS idx_tracker_status ON "{TRACKER_TABLE}"("Status")')
    conn.execute(f'CREATE INDEX IF NOT EXISTS idx_tracker_stage ON "{TRACKER_TABLE}"("Stage")')
    conn.execute(f'CREATE INDEX IF NOT EXISTS idx_tracker_hidden ON "{TRACKER_TABLE}"("Hidden")')
    conn.execute(f'CREATE INDEX IF NOT EXISTS idx_state_removed ON "{STATE_TABLE}"("Removed")')
    conn.execute(f'CREATE INDEX IF NOT EXISTS idx_action_status ON "{ACTION_TABLE}"("Status")')
    conn.commit()
    return conn


def get_states(conn):
    rows = conn.execute(f'SELECT * FROM "{STATE_TABLE}"').fetchall()
    return {row["State_key"]: dict(row) for row in rows}


def upsert_state(conn, state):
    conn.execute(f"""
        INSERT INTO {STATE_TABLE} (
            State_key, Log_path, Job, Project, Milestone, Block, Stage, Dft_release, User,
            Created, Modified, Last_seen_mtime, Last_seen_size, Last_change_time,
            Last_extracted_mtime, Last_status, Rerun, Removed, Force_extract, Updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(State_key) DO UPDATE SET
            Log_path=excluded.Log_path,
            Job=excluded.Job,
            Project=excluded.Project,
            Milestone=excluded.Milestone,
            Block=excluded.Block,
            Stage=excluded.Stage,
            Dft_release=excluded.Dft_release,
            User=excluded.User,
            Created=excluded.Created,
            Modified=excluded.Modified,
            Last_seen_mtime=excluded.Last_seen_mtime,
            Last_seen_size=excluded.Last_seen_size,
            Last_change_time=excluded.Last_change_time,
            Last_extracted_mtime=excluded.Last_extracted_mtime,
            Last_status=excluded.Last_status,
            Rerun=excluded.Rerun,
            Removed=excluded.Removed,
            Force_extract=excluded.Force_extract,
            Updated_at=excluded.Updated_at
    """, (
        state["State_key"],
        state.get("Log_path"),
        state.get("Job"),
        state.get("Project"),
        state.get("Milestone"),
        state.get("Block"),
        state.get("Stage"),
        state.get("Dft_release"),
        state.get("User"),
        state.get("Created"),
        state.get("Modified"),
        state.get("Last_seen_mtime"),
        state.get("Last_seen_size"),
        state.get("Last_change_time"),
        state.get("Last_extracted_mtime"),
        state.get("Last_status"),
        state.get("Rerun", 0),
        state.get("Removed", 0),
        state.get("Force_extract", 0),
        now_str(),
    ))
    conn.commit()


def upsert_tracker(conn, rec):
    cols = TRACKER_COLUMNS + ["Hidden"] + KPI_COLUMNS
    insert_cols = ", ".join([f'"{c}"' for c in cols])
    insert_vals = ", ".join(["?"] * len(cols))
    update_cols = [c for c in cols if c not in {"Job", "Milestone", "Block", "Stage", "Created"}]
    update_sql = ", ".join([f'"{c}"=excluded."{c}"' for c in update_cols])

    conn.execute(f"""
        INSERT INTO {TRACKER_TABLE} ({insert_cols})
        VALUES ({insert_vals})
        ON CONFLICT(Job, Milestone, Block, Stage) DO UPDATE SET
            {update_sql}
    """, [rec.get(c, 0 if c == "Hidden" else None) for c in cols])
    conn.commit()


def delete_tracker_row(conn, job, milestone, block, stage):
    conn.execute(
        f'DELETE FROM "{TRACKER_TABLE}" WHERE Job=? AND Milestone=? AND Block=? AND Stage=?',
        (job, milestone, block, stage)
    )
    conn.commit()


def update_tracker_status(conn, rec, status, comments=None, promote=None, rerun=None):
    fields = ['"Status"=?']
    values = [status]

    if comments is not None:
        fields.append('"Comments"=?')
        values.append(comments)

    if promote is not None:
        fields.append('"Promote"=?')
        values.append(promote)

    if rerun is not None:
        fields.append('"Rerun"=?')
        values.append(rerun)

    values.extend([rec["Job"], rec["Milestone"], rec["Block"], rec["Stage"]])

    conn.execute(
        f'''
        UPDATE "{TRACKER_TABLE}"
        SET {", ".join(fields)}
        WHERE Job=? AND Milestone=? AND Block=? AND Stage=?
        ''',
        values
    )
    conn.commit()


def queue_action(conn, state_key, action):
    conn.execute(
        f'''
        INSERT INTO "{ACTION_TABLE}" (State_key, Action, Status, Created_at, Updated_at)
        VALUES (?, ?, 'Pending', ?, ?)
        ''',
        (state_key, action, now_str(), now_str())
    )
    conn.commit()


def request_reupdate(conn, state_key):
    queue_action(conn, state_key, ACTION_REUPDATE)


def request_remove(conn, state_key):
    queue_action(conn, state_key, ACTION_REMOVE)


def request_add_back(conn, state_key):
    queue_action(conn, state_key, ACTION_ADD_BACK)


def get_pending_actions(conn):
    return conn.execute(
        f'SELECT * FROM "{ACTION_TABLE}" WHERE Status="Pending" ORDER BY Id'
    ).fetchall()


def complete_action(conn, action_id):
    conn.execute(
        f'UPDATE "{ACTION_TABLE}" SET Status="Done", Updated_at=? WHERE Id=?',
        (now_str(), action_id)
    )
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