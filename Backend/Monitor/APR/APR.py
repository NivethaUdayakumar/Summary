import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.append(str(CURRENT_DIR))

import time
import traceback

from APR_Data_Extraction import extract_apr_runs
from APR_Status import get_run_status
from APR_Update_DB import (
    init_apr_tables,
    upsert_tracker_row,
    mark_missing_runs_failed,
    log_message,
)


POLL_INTERVAL_SECONDS = 30


def run_monitor(project_code: str):
    init_apr_tables(project_code)
    log_message(project_code, f"APR monitor started for project {project_code}")

    while True:
        try:
            extracted_rows = extract_apr_runs(project_code)
            active_run_ids = set()

            for row in extracted_rows:
                row["status"] = get_run_status(row)
                active_run_ids.add(row["run_id"])
                upsert_tracker_row(project_code, row)

            mark_missing_runs_failed(project_code, active_run_ids)

            log_message(
                project_code,
                f"APR monitor cycle complete. discovered_runs={len(extracted_rows)}"
            )

        except Exception as e:
            log_message(project_code, f"APR monitor error: {str(e)}", level="ERROR")
            log_message(project_code, traceback.format_exc(), level="ERROR")

        time.sleep(POLL_INTERVAL_SECONDS)


def main():
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python APR.py <project_code>")

    project_code = sys.argv[1]
    run_monitor(project_code)


if __name__ == "__main__":
    main()