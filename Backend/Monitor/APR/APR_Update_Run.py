import sys
import json
import sqlite3
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from APR_Data_Processing_Code import data_processing_code

PROJECTS_BASE_DIR = Path(os.environ.get("PROJECTS_BASE_DIR", "/proj"))


def main():
    if len(sys.argv) < 3:
        raise SystemExit("Usage: python APR_Update_Run.py <project_code> <json_run_ids>")

    project_code = sys.argv[1]
    run_ids = json.loads(sys.argv[2])

    db_path = PROJECTS_BASE_DIR / project_code / "DB" / f"{project_code}_DB.db"
    if not db_path.exists():
        print(json.dumps({
            "project_code": project_code,
            "updated": 0,
            "filepaths": [],
            "errors": []
        }))
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    filepaths = []
    for run_id in run_ids:
        cur.execute('SELECT filepath FROM "APR_Tracker" WHERE id = ?', (run_id,))
        row = cur.fetchone()
        if row and row["filepath"]:
            filepaths.append(row["filepath"])

    conn.close()

    errors = []

    with ThreadPoolExecutor(max_workers=4) as executor:
        future_map = {executor.submit(data_processing_code, fp): fp for fp in filepaths}

        for future in as_completed(future_map):
            fp = future_map[future]
            try:
                future.result()
            except Exception as e:
                errors.append({
                    "filepath": fp,
                    "error": str(e)
                })

    print(json.dumps({
        "project_code": project_code,
        "updated": len(filepaths) - len(errors),
        "filepaths": filepaths,
        "errors": errors
    }))


if __name__ == "__main__":
    main()