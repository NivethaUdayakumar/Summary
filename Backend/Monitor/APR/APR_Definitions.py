from datetime import datetime

DB_NAME = "DashAI_APR.db"
LOG_DIR = "LogsAPR"
STATE_DIR = "States"
STATE_FILE_NAME = "APR_State.json"
FORCE_EXTRACT_FILE_NAME = "APR_Force_Extract.txt"
POLL_SECONDS = 60
LOG_KEEP_DAYS = 14

DEFAULT_MINDEPTH = 5
DEFAULT_MAXDEPTH = 5
DEFAULT_FLOW = "apr"
DEFAULT_TOOL = "innovus"
MAX_ACTIVE_WORKERS = 4
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
    "Job", "Milestone", "Block", "Stage", "Dft_release",
    "User", "Created", "Modified", "Rerun", "Status", "Comments", "Promote"
]

KPI_COLUMNS = [
    "Setup_WNS_seq", "Setup_TNS_seq", "Setup_NVP_seq",
    "Hold_WNS_seq", "Hold_TNS_seq", "Hold_NVP_seq",
    "Clock_trans", "Max_trans", "Max_hotspot", "Total_hotspot",
    "Fp", "Macro", "Hard", "Soft", "Area_fp", "Area_macro",
    "Psh", "Phys", "Logic", "Hrow", "Srow", "Dynamic",
    "Leakage", "SVT", "LVTL", "LVT", "ULVTL", "ULVT",
    "ELVT", "Conversion_rate", "Bits_per_cell"
]

STATE_ENTRY_FIELDS = {
    "Created",
    "Extraction_pid",
    "Extraction_started_at",
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
WRITER_TIMING = "timing"
WRITER_STOP = "stop"

def now_str():
    return datetime.now().strftime("%Y%m%d %H:%M:%S")

def today_log_file():
    return f"APR_{datetime.now().strftime('%Y%m%d')}.log"

def make_state_key(job, milestone, block, stage):
    return f"{job}--{milestone}--{block}--{stage}"
