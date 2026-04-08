import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime


PROJECTS_BASE_DIR = Path("/proj")


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_db_path(project_code: str) -> Path:
    return PROJECTS_BASE_DIR / project_code / "DB" / f"{project_code}_DB.db"


def main():
    if len(sys.argv) < 3:
        raise SystemExit("Usage: python APR_Update_Run.py <project_code> <json_run_ids>")

    project_code = sys.argv[1]
    run_ids = json.loads(sys.argv[2])

    conn = sqlite3.connect(get_db_path(project_code))
    cur = conn.cursor()

    now = now_str()
    for run_id in run_ids:
        cur.execute("""
            UPDATE APR_Tracker
            SET manual_update_ts = ?, updated_at = ?
            WHERE run_id = ?
        """, (now, now, run_id))

    conn.commit()
    conn.close()

    print(f"update completed for {len(run_ids)} run(s)")


if __name__ == "__main__":
    main()