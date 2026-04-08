import sys
import json
import sqlite3
from pathlib import Path


PROJECTS_BASE_DIR = Path("/proj")


def get_db_path(project_code: str) -> Path:
    return PROJECTS_BASE_DIR / project_code / "DB" / f"{project_code}_DB.db"


def main():
    if len(sys.argv) < 4:
        raise SystemExit("Usage: python APR_Hide_Runs.py <project_code> <hide|unhide> <json_run_ids>")

    project_code = sys.argv[1]
    action = sys.argv[2].strip().lower()
    run_ids = json.loads(sys.argv[3])

    if action not in {"hide", "unhide"}:
        raise SystemExit("Action must be hide or unhide")

    hidden_value = 1 if action == "hide" else 0

    conn = sqlite3.connect(get_db_path(project_code))
    cur = conn.cursor()

    for run_id in run_ids:
        cur.execute("""
            UPDATE APR_Tracker
            SET hidden = ?
            WHERE run_id = ?
        """, (hidden_value, run_id))

    conn.commit()
    conn.close()

    print(f"{action} completed for {len(run_ids)} run(s)")


if __name__ == "__main__":
    main()