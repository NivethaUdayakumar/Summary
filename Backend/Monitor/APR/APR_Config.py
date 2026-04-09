from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent
MONITOR_LOG_DIR_NAME = "Monitor_Logs"

POLL_INTERVAL_SECONDS = 60
LOG_RETENTION_DAYS = 14
FILE_STABLE_SECONDS = 120

MONITOR_GLOB_PATTERNS = [
    "**/*.log",
]

DATA_TABLE = "APR_Tracker"
STATE_TABLE = "APR_Monitor_State"

DATA_TABLE_COLUMNS = (
    "id",
    "record_key",
    "filepath",
    "filename",
    "project_code",
    "status",
    "file_size",
    "modified_time",
    "created_at",
    "updated_at",
    "hidden",
    "metadata_json",
)

STATE_TABLE_COLUMNS = (
    "filepath",
    "record_key",
    "project_code",
    "is_excluded",
    "is_hidden",
    "last_status",
    "first_seen_at",
    "last_seen_at",
    "last_processed_at",
    "notes",
)

PROJECTS_BASE_DIR = Path(os.environ.get("PROJECTS_BASE_DIR", "/proj"))


def get_project_paths(project_code: str) -> dict:
    project_root = PROJECTS_BASE_DIR / project_code
    db_dir = project_root / "DB"
    dashboard_dir = project_root / "Dashboard"

    return {
        "project_root": project_root,
        "db_dir": db_dir,
        "dashboard_dir": dashboard_dir,
        "monitor_root": project_root,
        "monitor_log_dir": dashboard_dir / MONITOR_LOG_DIR_NAME,
        "data_db": db_dir / f"{project_code}_DB.db",
        "state_db": dashboard_dir / "APR_monitor_state.db",
    }