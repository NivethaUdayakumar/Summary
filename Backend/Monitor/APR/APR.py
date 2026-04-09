import signal
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

from APR_Add_Record import Add_record
from APR_Get_File_Status import Get_file_status
from APR_Get_Monitor_Files import Get_monitor_files
from APR_Get_Record_ID import Get_record_id
from APR_Get_Values_For_Record import Get_values_for_record
from APR_Update_Record import Update_record
from APR_Config import (
    DATA_TABLE,
    STATE_TABLE,
    STATE_TABLE_COLUMNS,
    LOG_RETENTION_DAYS,
    POLL_INTERVAL_SECONDS,
    get_project_paths,
)
from APR_Data_Processing_Code import data_processing_code
from APR_DB_Common import get_conn, utc_now_str
from APR_Init_Databases import init_databases


STOP = False


def stop_handler(signum, frame):
    global STOP
    STOP = True


signal.signal(signal.SIGINT, stop_handler)
signal.signal(signal.SIGTERM, stop_handler)


def ensure_log_dir(log_dir: Path):
    log_dir.mkdir(parents=True, exist_ok=True)


def cleanup_old_logs(log_dir: Path):
    ensure_log_dir(log_dir)
    cutoff = datetime.now() - timedelta(days=LOG_RETENTION_DAYS)

    for path in log_dir.glob("monitor_*.log"):
        try:
            stem_date = path.stem.replace("monitor_", "")
            file_date = datetime.strptime(stem_date, "%Y%m%d")
            if file_date < cutoff:
                path.unlink(missing_ok=True)
        except Exception:
            continue


def write_log_line(log_dir: Path, processed: int, completed: int, remaining: int):
    ensure_log_dir(log_dir)
    today = datetime.now().strftime("%Y%m%d")
    log_file = log_dir / f"monitor_{today}.log"
    line = (
        f"{utc_now_str()} | Runs processed: {processed} | "
        f"Runs Completed: {completed} | Runs remaining: {remaining}\n"
    )
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(line)


def upsert_state(state_db: str, project_code: str, filepath: str, record_key: str | None, last_status: str, is_hidden: int):
    now = utc_now_str()
    insert_cols = ", ".join(STATE_TABLE_COLUMNS)
    placeholders = ", ".join(["?"] * len(STATE_TABLE_COLUMNS))

    values = (
        filepath,
        record_key,
        project_code,
        0,
        is_hidden,
        last_status,
        now,
        now,
        now,
        None,
    )

    with get_conn(state_db) as conn:
        conn.execute(
            f"""
            INSERT INTO "{STATE_TABLE}" ({insert_cols})
            VALUES ({placeholders})
            ON CONFLICT(filepath) DO UPDATE SET
                record_key = excluded.record_key,
                project_code = excluded.project_code,
                is_hidden = excluded.is_hidden,
                last_status = excluded.last_status,
                last_seen_at = excluded.last_seen_at,
                last_processed_at = excluded.last_processed_at
            """,
            values,
        )
        conn.commit()


def get_existing_record_by_key(data_db: str, record_key: str):
    with get_conn(data_db) as conn:
        row = conn.execute(
            f'''
            SELECT id, record_key, filepath, status, file_size, modified_time, hidden
            FROM "{DATA_TABLE}"
            WHERE record_key = ?
            ''',
            (record_key,),
        ).fetchone()
        return dict(row) if row else None


def build_update_values(project_code: str, filepath: str, status: str, hidden: int):
    columns_tuple, values_tuple = Get_values_for_record(project_code, filepath, status=status, hidden=hidden)

    update_columns = (
        "filepath",
        "filename",
        "project_code",
        "status",
        "file_size",
        "modified_time",
        "updated_at",
        "hidden",
        "metadata_json",
    )

    value_map = dict(zip(columns_tuple, values_tuple))
    update_values = tuple(value_map[col] for col in update_columns)

    return update_columns, update_values


def mark_missing_failed(data_db: str, filepath: str):
    with get_conn(data_db) as conn:
        row = conn.execute(
            f'''
            SELECT id, hidden
            FROM "{DATA_TABLE}"
            WHERE filepath = ?
            ''',
            (filepath,),
        ).fetchone()

        if not row:
            return

        if row["hidden"] == 1:
            return

        conn.execute(
            f'''
            UPDATE "{DATA_TABLE}"
            SET status = ?, updated_at = ?
            WHERE id = ?
            ''',
            ("failed", utc_now_str(), row["id"]),
        )
        conn.commit()


def main():
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python APR.py <project_code>")

    project_code = sys.argv[1]
    paths = get_project_paths(project_code)

    data_db = str(paths["data_db"])
    state_db = str(paths["state_db"])
    log_dir = paths["monitor_log_dir"]

    init_databases(project_code)
    ensure_log_dir(log_dir)

    executor = ThreadPoolExecutor(max_workers=4)

    try:
        while not STOP:
            cleanup_old_logs(log_dir)

            files = Get_monitor_files(project_code)
            current_files_set = set(files)

            processed = 0
            completed = 0

            with get_conn(data_db) as conn:
                rows = conn.execute(
                    f'''
                    SELECT filepath
                    FROM "{DATA_TABLE}"
                    WHERE hidden = 0
                    '''
                ).fetchall()
                visible_db_filepaths = {row["filepath"] for row in rows}

            for filepath in files:
                record_key = str(Path(filepath).resolve())
                existing = get_existing_record_by_key(data_db, record_key)

                if existing and existing.get("hidden") == 1:
                    continue

                processed += 1

                new_status = Get_file_status(filepath)

                if new_status == "complete":
                    completed += 1

                if existing is None:
                    columns_tuple, values_tuple = Get_values_for_record(
                        project_code=project_code,
                        filepath=filepath,
                        status=new_status,
                        hidden=0,
                    )
                    Add_record(data_db, DATA_TABLE, columns_tuple, values_tuple)
                    upsert_state(state_db, project_code, filepath, record_key, new_status, 0)
                    executor.submit(data_processing_code, filepath)
                    continue

                old_status = existing["status"]

                update_cols, update_vals = build_update_values(
                    project_code=project_code,
                    filepath=filepath,
                    status=new_status,
                    hidden=existing.get("hidden", 0),
                )
                Update_record(existing["id"], data_db, DATA_TABLE, update_cols, update_vals)
                upsert_state(state_db, project_code, filepath, record_key, new_status, existing.get("hidden", 0))

                if old_status != new_status:
                    executor.submit(data_processing_code, filepath)

            missing_filepaths = visible_db_filepaths - current_files_set
            for filepath in missing_filepaths:
                mark_missing_failed(data_db, filepath)

            remaining = processed - completed
            write_log_line(log_dir, processed, completed, remaining)

            for _ in range(POLL_INTERVAL_SECONDS):
                if STOP:
                    break
                time.sleep(1)

    finally:
        executor.shutdown(wait=False, cancel_futures=True)


if __name__ == "__main__":
    main()