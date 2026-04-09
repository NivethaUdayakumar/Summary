from APR_Config import DATA_TABLE, STATE_TABLE, get_project_paths
from APR_DB_Common import get_conn


def init_databases(project_code: str) -> None:
    paths = get_project_paths(project_code)
    data_db = paths["data_db"]
    state_db = paths["state_db"]

    with get_conn(data_db) as conn:
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {DATA_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_key TEXT NOT NULL UNIQUE,
                filepath TEXT NOT NULL UNIQUE,
                filename TEXT,
                project_code TEXT,
                status TEXT,
                file_size INTEGER,
                modified_time REAL,
                created_at TEXT,
                updated_at TEXT,
                hidden INTEGER DEFAULT 0,
                metadata_json TEXT
            )
            """
        )
        conn.execute(f'CREATE INDEX IF NOT EXISTS idx_{DATA_TABLE}_record_key ON "{DATA_TABLE}"(record_key)')
        conn.execute(f'CREATE INDEX IF NOT EXISTS idx_{DATA_TABLE}_filepath ON "{DATA_TABLE}"(filepath)')
        conn.execute(f'CREATE INDEX IF NOT EXISTS idx_{DATA_TABLE}_hidden ON "{DATA_TABLE}"(hidden)')
        conn.commit()

    with get_conn(state_db) as conn:
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {STATE_TABLE} (
                filepath TEXT PRIMARY KEY,
                record_key TEXT,
                project_code TEXT,
                is_excluded INTEGER DEFAULT 0,
                is_hidden INTEGER DEFAULT 0,
                last_status TEXT,
                first_seen_at TEXT,
                last_seen_at TEXT,
                last_processed_at TEXT,
                notes TEXT
            )
            """
        )
        conn.execute(f'CREATE INDEX IF NOT EXISTS idx_{STATE_TABLE}_record_key ON "{STATE_TABLE}"(record_key)')
        conn.commit()