import sys
import json
import sqlite3
import os
from pathlib import Path

PROJECTS_BASE_DIR = Path(os.environ.get("PROJECTS_BASE_DIR", "/proj"))


def main():
    if len(sys.argv) < 4:
        raise SystemExit("Usage: python APR_Hide_Runs.py <project_code> <hide|unhide> <json_run_ids>")

    project_code = sys.argv[1]
    action = sys.argv[2]
    run_ids = json.loads(sys.argv[3])

    if action not in {"hide", "unhide"}:
        raise SystemExit("Invalid action")

    db_path = PROJECTS_BASE_DIR / project_code / "DB" / f"{project_code}_DB.db"
    if not db_path.exists():
        print(json.dumps({
            "project_code": project_code,
            "action": action,
            "updated": 0,
            "errors": []
        }))
        return

    hidden_val = 1 if action == "hide" else 0

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    updated = 0
    errors = []

    for run_id in run_ids:
        try:
            cur.execute(
                'UPDATE "APR_Tracker" SET hidden = ? WHERE id = ?',
                (hidden_val, run_id)
            )
            if cur.rowcount > 0:
                updated += 1
        except Exception as e:
            errors.append({
                "id": run_id,
                "error": str(e)
            })

    conn.commit()
    conn.close()

    print(json.dumps({
        "project_code": project_code,
        "action": action,
        "updated": updated,
        "errors": errors
    }))


if __name__ == "__main__":
    main()