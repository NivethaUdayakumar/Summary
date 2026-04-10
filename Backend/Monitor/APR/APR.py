import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import APR_DB_Operations
import APR_Utils
from APR_Definitions import (
    LOG_DIR,
    POLL_SECONDS,
    STATE_AWAIT,
    STATE_DONE,
    STATE_EXTRACT_FAILED,
    today_log_file,
    now_str,
)


def write_iter_log(path, to_extract, completed, remaining):
    with open(path, "a", encoding="utf-8") as f:
        f.write(
            f"{now_str()} | To_Extract_This_Iteration = {to_extract} | "
            f"Completed_Extract_This_Iteration = {completed} | "
            f"Remaining_Extract_This_Iteration = {remaining}\n"
        )


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 APR.py <project_code>")
        sys.exit(1)

    project_code = sys.argv[1]
    project_dashai_dir = f"/proj/{project_code}/DashAI"

    conn = APR_DB_Operations.init_db(project_dashai_dir)

    log_dir = os.path.join(project_dashai_dir, LOG_DIR)
    os.makedirs(log_dir, exist_ok=True)

    futures = {}

    with ThreadPoolExecutor(max_workers=8) as pool:
        while True:
            APR_DB_Operations.remove_old_logs(log_dir, keep_days=14)
            log_file = os.path.join(log_dir, today_log_file())
            states = APR_DB_Operations.get_states(conn)

            for action in APR_DB_Operations.get_pending_actions(conn):
                APR_Utils.apply_action(conn, action, states, APR_DB_Operations)
            states = APR_DB_Operations.get_states(conn)

            completed = 0
            to_extract = 0
            paths = APR_Utils.get_log_paths(project_dashai_dir)

            for log_path in paths:
                meta = APR_Utils.parse_log_args(log_path)
                created = states.get(meta["State_key"], {}).get("Created", now_str())
                rec = APR_Utils.build_record(log_path, created)
                key = rec["_state_key"]

                state = states.get(key, {
                    "State_key": key,
                    "Log_path": log_path,
                    "Job": rec["Job"],
                    "Project": rec["Project"],
                    "Milestone": rec["Milestone"],
                    "Block": rec["Block"],
                    "Stage": rec["Stage"],
                    "Dft_release": rec["Dft_release"],
                    "User": rec["User"],
                    "Created": rec["Created"],
                    "Modified": rec["Modified"],
                    "Removed": 0,
                    "Force_extract": 0,
                    "Rerun": 0,
                })

                state["Log_path"] = log_path
                state["Modified"] = rec["Modified"]
                state["User"] = rec["User"]

                busy = any(path == log_path and not fut.done() for fut, path in futures.items())
                rec["Status"], state = APR_Utils.compute_status(rec, state, busy)

                if state.get("Removed", 0) == 1:
                    APR_DB_Operations.upsert_state(conn, state)
                    APR_DB_Operations.delete_tracker_row(
                        conn,
                        rec["Job"],
                        rec["Milestone"],
                        rec["Block"],
                        rec["Stage"],
                    )
                    continue

                if rec["Status"] == STATE_AWAIT and not busy:
                    to_extract += 1
                    rundir = log_path.replace(f"/logs/{rec['Stage']}.log", "")
                    fut = pool.submit(APR_Utils.timing_results_capture, rundir, rec["Stage"], project_code)
                    futures[fut] = log_path
                    rec["Status"] = "Extracting"
                    state["Last_status"] = "Extracting"
                    state["Force_extract"] = 0

                rec = APR_Utils.apply_kpi_status(rec)
                APR_DB_Operations.upsert_tracker(conn, rec)
                APR_DB_Operations.upsert_state(conn, state)

            finished = [fut for fut in list(futures) if fut.done()]
            for fut in finished:
                log_path = futures.pop(fut)
                meta = APR_Utils.parse_log_args(log_path)
                state = APR_DB_Operations.get_states(conn).get(meta["State_key"])

                if not state:
                    continue

                try:
                    fut.result()
                    state["Last_status"] = STATE_DONE
                    state["Last_extracted_mtime"] = state["Last_seen_mtime"]
                    state["Force_extract"] = 0
                    completed += 1
                except Exception:
                    state["Last_status"] = STATE_EXTRACT_FAILED

                APR_DB_Operations.upsert_state(conn, state)

            write_iter_log(log_file, to_extract, completed, len(futures))
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()