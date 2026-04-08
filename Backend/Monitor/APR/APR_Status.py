from pathlib import Path
from datetime import datetime


RUNNING_WINDOW_SECONDS = 300


def now_dt():
    return datetime.now()


def parse_dt(value: str):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def get_run_status(row: dict):
    run_path = Path(row.get("run_path", ""))
    last_modified_ts = parse_dt(row.get("last_modified_ts", ""))

    if not run_path.exists():
        return "failed"

    if last_modified_ts:
        age = (now_dt() - last_modified_ts).total_seconds()
        if age <= RUNNING_WINDOW_SECONDS:
            return "running"

    return "completed"