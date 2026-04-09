from APR_Config import STATE_TABLE, STATE_TABLE_COLUMNS, get_project_paths
from APR_DB_Common import get_conn, utc_now_str


def Exclude_monitor_files(project_code: str, FilestoExclude: list[str]) -> None:
    paths = get_project_paths(project_code)
    state_db = paths["state_db"]
    now = utc_now_str()

    insert_cols = ", ".join(STATE_TABLE_COLUMNS)
    placeholders = ", ".join(["?"] * len(STATE_TABLE_COLUMNS))

    with get_conn(state_db) as conn:
        for filepath in FilestoExclude:
            values = (
                filepath,
                filepath,
                project_code,
                1,
                1,
                "hidden",
                now,
                now,
                now,
                None,
            )
            conn.execute(
                f"""
                INSERT INTO "{STATE_TABLE}" ({insert_cols})
                VALUES ({placeholders})
                ON CONFLICT(filepath) DO UPDATE SET
                    record_key = excluded.record_key,
                    project_code = excluded.project_code,
                    is_excluded = 1,
                    is_hidden = 1,
                    last_status = 'hidden',
                    last_seen_at = excluded.last_seen_at,
                    last_processed_at = excluded.last_processed_at
                """,
                values,
            )
        conn.commit()


def Include_monitor_files(project_code: str, FilesToInclude: list[str]) -> None:
    paths = get_project_paths(project_code)
    state_db = paths["state_db"]
    now = utc_now_str()

    with get_conn(state_db) as conn:
        for filepath in FilesToInclude:
            conn.execute(
                f"""
                UPDATE "{STATE_TABLE}"
                SET
                    is_excluded = 0,
                    is_hidden = 0,
                    last_status = 'visible',
                    last_seen_at = ?,
                    last_processed_at = ?
                WHERE filepath = ?
                """,
                (now, now, filepath),
            )
        conn.commit()