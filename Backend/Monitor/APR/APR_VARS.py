import importlib
import os
import sys
from datetime import datetime


PROJECTS_BASE_DIR = os.path.abspath(os.environ.get("PROJECTS_BASE_DIR", "/proj"))
DB_NAME = "DashAI_APR.db"
LOG_DIR = "APR_LOGS"
STATE_DIR = "STATE_FILES"
STATE_FILE_NAME = "APR_STATE.json"
FORCE_EXTRACT_FILE_NAME = "APR_FORCE_EXTRACT.json"
FORCE_EXTRACT_IN_DASHAI_ROOT = True
FORCE_EXTRACT_JSON_COMMENT = "Input type is { job: j, milestone:m, block: b, stage: s }"
FORCE_EXTRACT_JSON_ITEMS_KEY = "items"
POLL_SECONDS = 60
LOG_KEEP_DAYS = 14

DEFAULT_MINDEPTH = 5
DEFAULT_MAXDEPTH = 5
DEFAULT_FLOW = "apr"
DEFAULT_TOOL = "innovus"
BATCH_SIZE = 100
MAX_PARALLEL_BATCHES = 10
BATCH_RUN_WAIT_TIME = 60
SQLITE_TIMEOUT_SECONDS = 60
SQLITE_BUSY_TIMEOUT_MS = 60000

STAGES = ["init", "place", "clock", "route", "fill"]

STATE_AWAIT = "Await Extraction"
STATE_RUNNING = "Job Running"
STATE_EXTRACTING = "Extracting"
STATE_FAILED = "Job Failed"
STATE_DONE = "Completed"
STATE_EXTRACT_FAILED = "Extraction Failed"

TRACKER_TABLE = "APR_TRACKER"
TIMING_DETAIL_TABLE = "APR_TIMING_DETAIL"
TIMING_SUMMARY_TABLE = "APR_TIMING_SUMMARY"
TIMING_SUMMARY_COLUMNS = ("Mode", "TCheck", "TCorner", "Voltage", "Pathgroup")

TRACKER_ID_COLUMNS = ["Job", "Milestone", "Block", "Stage"]

TRACKER_COLUMNS = [
    "Job",
    "Milestone",
    "Block",
    "Stage",
    "Dft_release",
    "User",
    "Created",
    "Modified",
    "Rerun",
    "Status",
    "Comments",
    "Promote",
]

KPI_COLUMNS = [
    "Setup_WNS_seq",
    "Setup_TNS_seq",
    "Setup_NVP_seq",
    "Hold_WNS_seq",
    "Hold_TNS_seq",
    "Hold_NVP_seq",
    "Clock_trans",
    "Max_trans",
    "Max_hotspot",
    "Total_hotspot",
    "Fp",
    "Macro",
    "Hard",
    "Soft",
    "Area_fp",
    "Area_macro",
    "Psh",
    "Phys",
    "Logic",
    "Hrow",
    "Srow",
    "Dynamic",
    "Leakage",
    "SVT",
    "LVTL",
    "LVT",
    "ULVTL",
    "ULVT",
    "ELVT",
    "Conversion_rate",
    "Bits_per_cell",
]

STATE_ENTRY_FIELDS = {
    "Created",
    "Force_extract",
    "Last_change_time",
    "Last_extract_finished_at",
    "Last_extract_result",
    "Last_extracted_mtime",
    "Last_seen_mtime",
    "Last_seen_size",
    "Last_status",
    "Rerun",
}

WRITER_TRACKER = "tracker"
WRITER_STOP = "stop"

# Lists the APR settings that are treated as live runtime configuration.
# get_runtime_settings() iterates this tuple to build the current settings snapshot, and get_setting() reloads the module so edits to these names are picked up without restarting the monitor.
_DYNAMIC_SETTING_NAMES = (
    "PROJECTS_BASE_DIR",  # str: Absolute project root under which project_code folders are discovered.
    "DB_NAME",  # str: SQLite database filename used for the shared APR tracker database.
    "LOG_DIR",  # str: DashAI subfolder name where APR batch log files are written.
    "STATE_DIR",  # str: DashAI subfolder name where the persisted APR state JSON file lives.
    "STATE_FILE_NAME",  # str: JSON filename used for the persisted APR monitor state.
    "FORCE_EXTRACT_FILE_NAME",  # str: JSON filename that users edit to request force re-extractions.
    "FORCE_EXTRACT_IN_DASHAI_ROOT",  # bool: Whether the force-extract JSON is expected directly under the DashAI root.
    "FORCE_EXTRACT_JSON_COMMENT",  # str: Informational comment written into the force-extract JSON template.
    "FORCE_EXTRACT_JSON_ITEMS_KEY",  # str: JSON key name that contains the force-extract request list.
    "POLL_SECONDS",  # int: Monitor sleep time in seconds between APR polling cycles.
    "LOG_KEEP_DAYS",  # int: Number of days of APR batch log files that should be retained.
    "DEFAULT_MINDEPTH",  # int: Minimum relative depth where APR run directories should be considered.
    "DEFAULT_MAXDEPTH",  # int: Maximum relative depth where APR run directories should be considered.
    "DEFAULT_FLOW",  # str: Flow folder name expected in the APR run directory path.
    "DEFAULT_TOOL",  # str: Tool folder name expected in the APR run directory path.
    "BATCH_SIZE",  # int: Maximum number of runs grouped into one APR batch subprocess.
    "MAX_PARALLEL_BATCHES",  # int: Maximum number of APR batch subprocesses that may run in parallel.
    "BATCH_RUN_WAIT_TIME",  # int: Seconds the oldest queued run may wait before a short batch is launched.
    "SQLITE_TIMEOUT_SECONDS",  # int: SQLite connection timeout used by APR tracker writers and extractors.
    "SQLITE_BUSY_TIMEOUT_MS",  # int: SQLite busy-timeout pragma value in milliseconds.
    "STAGES",  # list[str]: APR stage names whose log files should be monitored.
    "STATE_AWAIT",  # str: Tracker status text used when a run is waiting to be extracted.
    "STATE_RUNNING",  # str: Tracker status text used while the APR source job still appears to be active.
    "STATE_EXTRACTING",  # str: Tracker status text used while the APR batch subprocess is extracting the run.
    "STATE_FAILED",  # str: Tracker status text used when the APR job appears to have failed.
    "STATE_DONE",  # str: Tracker status text used when extraction and KPI validation completed successfully.
    "STATE_EXTRACT_FAILED",  # str: Tracker status text used when the APR batch extraction itself failed.
    "TRACKER_TABLE",  # str: Table name used for the shared APR tracker rows.
    "TIMING_DETAIL_TABLE",  # str: Table name used by timing extractor detail databases.
    "TIMING_SUMMARY_TABLE",  # str: Table name used by timing extractor summary databases.
    "TIMING_SUMMARY_COLUMNS",  # tuple[str, ...]: Summary-table grouping columns used by APR timing extraction.
    "TRACKER_ID_COLUMNS",  # list[str]: Tracker key column names that uniquely identify one APR run row.
    "TRACKER_COLUMNS",  # list[str]: Non-KPI tracker column names written into the APR tracker database.
    "KPI_COLUMNS",  # list[str]: KPI tracker column names populated from the final APR KPI report.
    "STATE_ENTRY_FIELDS",  # set[str]: Only state-entry keys that are allowed to be persisted in the APR state file.
    "WRITER_TRACKER",  # str: Queue command name used by the SQLite writer for tracker row updates.
    "WRITER_STOP",  # str: Queue command name used by the SQLite writer for graceful shutdown.
)

try:
    _LOADED_SOURCE_MTIME = os.path.getmtime(__file__)
except OSError:
    _LOADED_SOURCE_MTIME = None


def _reload_if_changed():
    """
    Function Name: _reload_if_changed
    Purpose: Reload APR_VARS when the source file changes so the running monitor can pick up edits without a restart.
    Input Params: outputs (None)
    Output: module (module)
    """
    module = sys.modules[__name__]
    try:
        current_source_mtime = os.path.getmtime(__file__)
    except OSError:
        return module

    if getattr(module, "_LOADED_SOURCE_MTIME", None) == current_source_mtime:
        return module

    return importlib.reload(module)


def get_runtime_settings():
    """
    Function Name: get_runtime_settings
    Purpose: Return the latest APR runtime settings snapshot after reloading APR_VARS if it changed on disk.
    Input Params: outputs (None)
    Output: settings (dict)
    """
    module = _reload_if_changed()
    return {
        setting_name: getattr(module, setting_name)
        for setting_name in _DYNAMIC_SETTING_NAMES
    }


def get_setting(setting_name, default=None):
    """
    Function Name: get_setting
    Purpose: Return one APR runtime setting value from the latest APR_VARS module state.
    Input Params: setting_name (str), default (object | None)
    Output: setting_value (object)
    """
    module = _reload_if_changed()
    return getattr(module, setting_name, default)


def make_force_extract_template():
    """
    Function Name: make_force_extract_template
    Purpose: Build the default force-extract JSON payload structure written for APR users.
    Input Params: outputs (None)
    Output: payload (dict)
    """
    return {
        "_comment": get_setting("FORCE_EXTRACT_JSON_COMMENT"),
        get_setting("FORCE_EXTRACT_JSON_ITEMS_KEY"): [],
    }


def now_str():
    """
    Function Name: now_str
    Purpose: Return the current timestamp string in the APR monitor date-time format.
    Input Params: outputs (None)
    Output: timestamp (str)
    """
    return datetime.now().strftime("%Y/%m/%d %H:%M:%S")


def today_log_file():
    """
    Function Name: today_log_file
    Purpose: Return the APR daily log filename for the current date.
    Input Params: outputs (None)
    Output: file_name (str)
    """
    return f"APR_{datetime.now().strftime('%Y%m%d')}.log"


def make_state_key(job, milestone, block, stage):
    """
    Function Name: make_state_key
    Purpose: Build the persisted APR state key for one run from its job, milestone, block, and stage.
    Input Params: job (str), milestone (str), block (str), stage (str)
    Output: state_key (str)
    """
    return f"{job}--{milestone}--{block}--{stage}"
