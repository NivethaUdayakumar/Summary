from datetime import datetime

DB_NAME = "DashAI_APR.db"
LOG_DIR = "LogsAPR"
STATE_DIR = "States"
STATE_FILE_NAME = "APR_State.json"
FORCE_EXTRACT_FILE_NAME = "APR_Force_Extract.txt"
POLL_SECONDS = 60

DEFAULT_MINDEPTH = 5
DEFAULT_MAXDEPTH = 5
DEFAULT_FLOW = "apr"
DEFAULT_TOOL = "innovus"

STAGES = ["init", "place", "clock", "route", "fill"]

STATE_AWAIT = "Await Extraction"
STATE_RUNNING = "Job Running"
STATE_EXTRACTING = "Extracting"
STATE_FAILED = "Job Failed"
STATE_DONE = "Completed"
STATE_EXTRACT_FAILED = "Extraction Failed"

TRACKER_TABLE = "APR_TRACKER"

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

def now_str():
    return datetime.now().strftime("%Y%m%d %H:%M:%S")

def today_log_file():
    return f"APR_{datetime.now().strftime('%Y%m%d')}.log"

def make_state_key(job, milestone, block, stage):
    return f"{job}--{milestone}--{block}--{stage}"
