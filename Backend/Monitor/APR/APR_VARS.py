import importlib
import os
import sys
from datetime import datetime


DB_NAME = "DashAI_APR.db"
LOG_DIR = "APR_LOGS"
STATE_DIR = "STATE_FILES"
STATE_FILE_NAME = "APR_STATE.json"
APR_RUNS_DIR = "APR_RUNS"
BATCH_COMMANDS_DIR = "BATCH_COMMANDS"
BATCH_COMMAND_PREFIX = "APR_BATCH_COMMAND"
BATCH_PYTHON_MODULE = "Python3/3.11.1"
BATCH_PYTHON_COMMAND = "python3"
POLL_SECONDS = 60

RUN_ACTIVE_TIME = 900   # 15 minutes
DEFAULT_MINDEPTH = 5
DEFAULT_MAXDEPTH = 5
DEFAULT_FLOW = "apr"
DEFAULT_TOOL = "innovus"
BATCH_SIZE = 100
MAX_PARALLEL_BATCHES = 10
SQLITE_TIMEOUT_SECONDS = 60
SQLITE_BUSY_TIMEOUT_MS = 60000

STAGES = ["init", "place", "clock", "route", "fill"]

STATE_AWAIT = "Await Extraction"
STATE_RUNNING = "Job Running"
STATE_EXTRACTING = "Extracting"
STATE_FAILED = "Job Failed"
STATE_DONE = "Completed"

TRACKER_TABLE = "APR_TRACKER"
TIMING_DETAIL_TABLE = "APR_TIMING_DETAIL"
TIMING_SUMMARY_TABLE = "APR_TIMING_SUMMARY"

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

WRITER_TRACKER = "tracker"
WRITER_STOP = "stop"

# Lists the APR settings that are treated as live runtime configuration.
# get_runtime_settings() iterates this tuple to build the current settings snapshot, and get_setting() reloads the module so edits to these names are picked up without restarting the monitor.
_DYNAMIC_SETTING_NAMES = (
    "DB_NAME",  # str: SQLite database filename used for the shared APR tracker database.
    "LOG_DIR",  # str: DashAI subfolder name where APR batch log files are written.
    "STATE_DIR",  # str: DashAI subfolder name where the persisted APR state JSON file lives.
    "STATE_FILE_NAME",  # str: JSON filename used for the persisted APR monitor state.
    "APR_RUNS_DIR",  # str: DashAI subfolder name where extracted APR timing databases are written.
    "BATCH_COMMANDS_DIR",  # str: Extractor subfolder that stores generated batch command files.
    "BATCH_COMMAND_PREFIX",  # str: Prefix used for dynamically generated APR batch command filenames.
    "BATCH_PYTHON_MODULE",  # str: Module name loaded into the batch command file before running the timing extractor.
    "BATCH_PYTHON_COMMAND",  # str: Python executable invoked inside each APR batch command file.
    "POLL_SECONDS",  # int: Monitor sleep time in seconds between APR polling cycles.
    "DEFAULT_MINDEPTH",  # int: Minimum relative depth where APR run directories should be considered.
    "DEFAULT_MAXDEPTH",  # int: Maximum relative depth where APR run directories should be considered.
    "DEFAULT_FLOW",  # str: Flow folder name expected in the APR run directory path.
    "DEFAULT_TOOL",  # str: Tool folder name expected in the APR run directory path.
    "BATCH_SIZE",  # int: Maximum number of runs grouped into one APR batch subprocess.
    "MAX_PARALLEL_BATCHES",  # int: Maximum number of APR batch subprocesses that may run in parallel.
    "SQLITE_TIMEOUT_SECONDS",  # int: SQLite connection timeout used by APR tracker writers and extractors.
    "SQLITE_BUSY_TIMEOUT_MS",  # int: SQLite busy-timeout pragma value in milliseconds.
    "STAGES",  # list[str]: APR stage names whose log files should be monitored.
    "STATE_AWAIT",  # str: Tracker status text used when a run is waiting to be extracted.
    "STATE_RUNNING",  # str: Tracker status text used while the APR source job still appears to be active.
    "STATE_EXTRACTING",  # str: Tracker status text used while the APR batch subprocess is extracting the run.
    "STATE_FAILED",  # str: Tracker status text used when the APR job appears to have failed.
    "STATE_DONE",  # str: Tracker status text used when extraction and KPI validation completed successfully.
    "TRACKER_TABLE",  # str: Table name used for the shared APR tracker rows.
    "TIMING_DETAIL_TABLE",  # str: Table name used by timing extractor detail databases.
    "TIMING_SUMMARY_TABLE",  # str: Table name used by timing extractor summary databases.
    "TRACKER_COLUMNS",  # list[str]: Non-KPI tracker column names written into the APR tracker database.
    "KPI_COLUMNS",  # list[str]: KPI tracker column names populated from the final APR KPI report.
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


def now_str():
    """
    Function Name: now_str
    Purpose: Return the current timestamp string in the APR monitor date-time format.
    Input Params: outputs (None)
    Output: timestamp (str)
    """
    return datetime.now().strftime("%Y/%m/%d %H:%M:%S")


def get_projects_base_dir():
    """
    Function Name: get_projects_base_dir
    Purpose: Build the absolute projects base directory path from the live environment setting.
    Input Params: outputs (None)
    Output: projects_base_dir (str)
    """
    return os.path.abspath(os.environ.get("PROJECTS_BASE_DIR", "/proj"))


def today_log_file():
    """
    Function Name: today_log_file
    Purpose: Return the APR daily log filename for the current date.
    Input Params: outputs (None)
    Output: file_name (str)
    """
    return f"APR_{datetime.now().strftime('%Y%m%d')}.log"


def get_project_dir(project_code):
    """
    Function Name: get_project_dir
    Purpose: Build the absolute project directory path for one APR project code.
    Input Params: project_code (str)
    Output: project_dir (str)
    """
    return os.path.abspath(os.path.join(get_projects_base_dir(), str(project_code or "").strip()))


def get_dashai_dir(project_code):
    """
    Function Name: get_dashai_dir
    Purpose: Build the absolute DashAI directory path for one APR project code.
    Input Params: project_code (str)
    Output: dashai_dir (str)
    """
    return os.path.abspath(os.path.join(get_project_dir(project_code), "DashAI"))


def get_imp_dir(project_code):
    """
    Function Name: get_imp_dir
    Purpose: Build the absolute IMP directory path for one APR project code.
    Input Params: project_code (str)
    Output: imp_dir (str)
    """
    return os.path.abspath(os.path.join(get_project_dir(project_code), "IMP"))


def get_state_dir(project_code):
    """
    Function Name: get_state_dir
    Purpose: Build the absolute state-directory path for one APR project code.
    Input Params: project_code (str)
    Output: state_dir (str)
    """
    return os.path.abspath(os.path.join(get_dashai_dir(project_code), get_setting("STATE_DIR")))


def get_state_file_path(project_code):
    """
    Function Name: get_state_file_path
    Purpose: Build the absolute APR monitor state-file path for one APR project code.
    Input Params: project_code (str)
    Output: state_file_path (str)
    """
    return os.path.abspath(os.path.join(get_state_dir(project_code), get_setting("STATE_FILE_NAME")))


def get_log_dir_path(project_code):
    """
    Function Name: get_log_dir_path
    Purpose: Build the absolute APR log-directory path for one APR project code.
    Input Params: project_code (str)
    Output: log_dir_path (str)
    """
    return os.path.abspath(os.path.join(get_dashai_dir(project_code), get_setting("LOG_DIR")))


def get_log_file_path(project_code):
    """
    Function Name: get_log_file_path
    Purpose: Build the absolute APR daily log-file path for one APR project code.
    Input Params: project_code (str)
    Output: log_file_path (str)
    """
    return os.path.abspath(os.path.join(get_log_dir_path(project_code), today_log_file()))


def get_tracker_db_path(project_code):
    """
    Function Name: get_tracker_db_path
    Purpose: Build the absolute APR tracker database path for one APR project code.
    Input Params: project_code (str)
    Output: tracker_db_path (str)
    """
    return os.path.abspath(os.path.join(get_dashai_dir(project_code), get_setting("DB_NAME")))


def get_apr_runs_dir(project_code):
    """
    Function Name: get_apr_runs_dir
    Purpose: Build the absolute APR extracted-runs directory path for one APR project code.
    Input Params: project_code (str)
    Output: apr_runs_dir (str)
    """
    return os.path.abspath(os.path.join(get_dashai_dir(project_code), get_setting("APR_RUNS_DIR")))


def get_batch_commands_dir():
    """
    Function Name: get_batch_commands_dir
    Purpose: Build the absolute directory path that stores generated APR batch command files.
    Input Params: outputs (None)
    Output: batch_commands_dir (str)
    """
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "EXTRACTORS", get_setting("BATCH_COMMANDS_DIR")))


def get_timing_script_path():
    """
    Function Name: get_timing_script_path
    Purpose: Build the absolute APR timing extractor script path used in batch command files.
    Input Params: outputs (None)
    Output: timing_script_path (str)
    """
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "EXTRACTORS", "APR_TIMING_INNOVUS.py"))


def make_state_key(job, milestone, block, stage):
    """
    Function Name: make_state_key
    Purpose: Build the persisted APR state key for one run from its job, milestone, block, and stage.
    Input Params: job (str), milestone (str), block (str), stage (str)
    Output: state_key (str)
    """
    return f"{job}--{milestone}--{block}--{stage}"
