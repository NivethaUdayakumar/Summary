from pathlib import Path

from Backend.Monitor.APR.APR_Config import MONITOR_GLOB_PATTERNS, STATE_TABLE, get_project_paths
from Backend.Monitor.APR.APR_DB_Common import get_conn


def Get_monitor_files(project_code: str) -> list[str]:
    paths = get_project_paths(project_code)
    monitor_root = paths["monitor_root"]
    state_db = paths["state_db"]

    found_files: set[str] = set()

    for pattern in MONITOR_GLOB_PATTERNS:
        for path in Path(monitor_root).glob(pattern):
            if path.is_file():
                found_files.add(str(path.resolve()))

    if not found_files:
        return []

    with get_conn(state_db) as conn:
        rows = conn.execute(
            f"""
            SELECT filepath
            FROM {STATE_TABLE}
            WHERE is_excluded = 1
            """
        ).fetchall()
        excluded = {row["filepath"] for row in rows}

    return sorted([fp for fp in found_files if fp not in excluded])