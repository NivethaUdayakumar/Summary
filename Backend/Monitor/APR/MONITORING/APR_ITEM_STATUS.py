import getpass
import os
import time
from pathlib import Path

import APR_VARS
from Backend.Monitor.APR.EXTRACTORS.APR_KPI_EXTRACT import get_kpi_report_path
from Backend.Monitor.APR.EXTRACTORS.APR_TIMING_INNOVUS import (
    get_timing_db_path as build_timing_db_path,
    get_timing_report_paths,
)
from Backend.Monitor.APR.MONITORING import APR_FLOW_CONTEXT

try:
    import pwd
except ImportError:
    pwd = None


def parse_log_args(log_path):
    """
    Function Name: parse_log_args
    Purpose: Parse one APR stage log path into the tracker scope fields used throughout the monitor.
    Input Params: log_path (str)
    Output: log_meta (dict)
    """
    path_parts = list(Path(os.path.abspath(log_path)).parts)
    lowered_parts = [path_part.lower() for path_part in path_parts]
    flow_name = str(APR_VARS.get_setting("DEFAULT_FLOW")).lower()
    tool_name = str(APR_VARS.get_setting("DEFAULT_TOOL")).lower()
    job = ""
    milestone = ""
    block = ""
    for index, path_part in enumerate(lowered_parts[:-1]):
        if path_part != flow_name:
            continue
        if index + 1 >= len(lowered_parts) or lowered_parts[index + 1] != tool_name:
            continue
        if index >= 2:
            milestone = path_parts[index - 2]
            block = path_parts[index - 1]
        if index + 2 < len(path_parts):
            job = path_parts[index + 2]
        break
    if not job and len(path_parts) >= 3:
        job = path_parts[-3]
    stage = Path(log_path).stem
    dft_release = get_dft_release(log_path)
    return {
        "Block": block,
        "Dft_release": dft_release,
        "Job": job,
        "Milestone": milestone,
        "Stage": stage,
        "State_key": APR_VARS.make_state_key(job, milestone, block, stage),
    }


def get_dft_release(log_path):
    """
    Function Name: get_dft_release
    Purpose: Resolve the DFT release name for one APR run by following the linked DFT inputs when available.
    Input Params: log_path (str)
    Output: dft_release (str)
    """
    try:
        absolute_log_path = Path(os.path.abspath(log_path))
        input_dir = absolute_log_path.parent.parent.parent / "inputs" / "dft" / "vlog"
        if not input_dir.exists():
            return "NA"

        for candidate in input_dir.glob("*dft.v"):
            real_path = os.path.realpath(str(candidate)).replace("\\", "/")
            if "/iExchange/DFT/" not in real_path:
                continue
            path_parts = real_path.strip("/").split("/")
            if len(path_parts) >= 3:
                return path_parts[-3]
    except Exception:
        pass
    return "NA"


def get_file_info(log_path):
    """
    Function Name: get_file_info
    Purpose: Read the APR stage log file metadata required for status computation and tracker updates.
    Input Params: log_path (str)
    Output: file_info (dict)
    """
    absolute_log_path = os.path.abspath(log_path)
    file_stat = os.stat(absolute_log_path)
    user_name = ""
    if pwd is not None:
        try:
            user_name = pwd.getpwuid(file_stat.st_uid).pw_name
        except Exception:
            user_name = ""
    if not user_name:
        try:
            user_name = getpass.getuser()
        except Exception:
            user_name = str(getattr(file_stat, "st_uid", ""))
    return {
        "Modified": time.strftime("%Y%m%d %H:%M:%S", time.localtime(file_stat.st_mtime)),
        "User": user_name,
        "mtime": int(file_stat.st_mtime),
        "size": int(file_stat.st_size),
    }


def get_source_db_path(log_path, log_meta=None):
    """
    Function Name: get_source_db_path
    Purpose: Build the absolute APR source-dbinfo path that belongs to one monitored stage log.
    Input Params: log_path (str), log_meta (dict | None)
    Output: source_db_path (str)
    """
    absolute_log_path = Path(os.path.abspath(log_path))
    run_directory = absolute_log_path.parent.parent
    metadata = log_meta or parse_log_args(log_path)
    return str(run_directory / "dbs" / f"{metadata['Stage']}_final" / f"{metadata['Job']}.dat" / f"{metadata['Job']}.dbinfo")


def get_timing_db_path(project_code, log_meta):
    """
    Function Name: get_timing_db_path
    Purpose: Build the absolute DashAI timing database path for one monitored APR stage item.
    Input Params: project_code (str), log_meta (dict)
    Output: timing_db_path (str)
    """
    return build_timing_db_path(project_code, log_meta)


def get_path_mtime(path):
    """
    Function Name: get_path_mtime
    Purpose: Return one path's integer mtime when the path exists.
    Input Params: path (str)
    Output: mtime (int | None)
    """
    try:
        return int(os.path.getmtime(os.path.abspath(path)))
    except OSError:
        return None


def build_tracker_record(log_path, state_entry, meta=None, file_info=None):
    """
    Function Name: build_tracker_record
    Purpose: Build one APR tracker row from the current stage log metadata and the computed in-memory state entry.
    Input Params: log_path (str), state_entry (dict), meta (dict | None), file_info (dict | None)
    Output: tracker_record (dict)
    """
    metadata = meta or parse_log_args(log_path)
    current_file_info = file_info or get_file_info(log_path)
    tracker_record = {
        "Block": metadata["Block"],
        "Comments": state_entry.get("Comments") or "-",
        "Created": state_entry.get("Last_Extract_Submission") or "",
        "Dft_release": metadata["Dft_release"],
        "Job": metadata["Job"],
        "Milestone": metadata["Milestone"],
        "Modified": current_file_info["Modified"],
        "Promote": "yes" if state_entry.get("Status") == APR_VARS.get_setting("STATE_DONE") else "no",
        "Rerun": max(0, int(state_entry.get("Rerun", 0) or 0)),
        "Stage": metadata["Stage"],
        "Status": state_entry.get("Status") or "",
        "User": current_file_info["User"],
    }
    tracker_record.update({column_name: "" for column_name in APR_VARS.get_setting("KPI_COLUMNS", [])})
    return tracker_record


def _compute_status(previous_state, file_info, source_db_exists, source_db_mtime, timing_db_exists, timing_db_mtime, kpi_file_exists, has_timing_reports):
    """
    Function Name: _compute_status
    Purpose: Apply the APR runtime status rules using the current outputs and the persisted light state entry.
    Input Params: previous_state (dict), file_info (dict), source_db_exists (bool), source_db_mtime (int | None), timing_db_exists (bool), timing_db_mtime (int | None), kpi_file_exists (bool), has_timing_reports (bool)
    Output: outputs (tuple[str, str, bool, int])
    """
    settings = APR_VARS.get_runtime_settings()
    previous_status = previous_state.get("Status")
    rerun_count = max(0, int(previous_state.get("Rerun", 0) or 0))
    extract_completed = False

    if source_db_exists:
        if timing_db_exists:
            if source_db_mtime is not None and timing_db_mtime is not None and source_db_mtime < timing_db_mtime:
                extract_completed = True
                if kpi_file_exists:
                    return settings["STATE_DONE"], "QC_PASS", extract_completed, rerun_count
                return settings["STATE_FAILED"], "ERR002", extract_completed, rerun_count

            if previous_status == settings["STATE_EXTRACTING"]:
                return settings["STATE_EXTRACTING"], "-", extract_completed, rerun_count
            if has_timing_reports:
                if previous_status != settings["STATE_AWAIT"]:
                    rerun_count += 1
                return settings["STATE_AWAIT"], "-", extract_completed, rerun_count
            return settings["STATE_FAILED"], "ERR003", extract_completed, rerun_count

        if previous_status == settings["STATE_EXTRACTING"]:
            return settings["STATE_EXTRACTING"], "-", extract_completed, rerun_count
        if has_timing_reports:
            return settings["STATE_AWAIT"], "-", extract_completed, rerun_count
        return settings["STATE_FAILED"], "ERR003", extract_completed, rerun_count

    if int(time.time()) - int(file_info["mtime"]) <= int(settings["RUN_ACTIVE_TIME"]):
        return settings["STATE_RUNNING"], "-", extract_completed, rerun_count
    return settings["STATE_FAILED"], "ERR001", extract_completed, rerun_count


def get_item_status(context, monitor_item):
    """
    Function Name: get_item_status
    Purpose: Compute one APR stage item's current status, comments, rerun count, and tracker row entirely from live files plus the light persisted state entry.
    Input Params: context (dict), monitor_item (dict)
    Output: file_item (dict)
    """
    project_code = APR_FLOW_CONTEXT.get_project_code(context)
    log_path = os.path.abspath(monitor_item["log_path"])
    run_directory = os.path.abspath(monitor_item["run_directory"])
    log_meta = parse_log_args(log_path)
    file_info = get_file_info(log_path)
    state_key = log_meta["State_key"]
    previous_state = dict(context.get("state", {}).get(state_key, {}))

    source_db_path = get_source_db_path(log_path, log_meta)
    timing_db_path = get_timing_db_path(project_code, log_meta)
    source_db_exists = os.path.exists(source_db_path)
    timing_db_exists = os.path.exists(timing_db_path)
    source_db_mtime = get_path_mtime(source_db_path) if source_db_exists else None
    timing_db_mtime = get_path_mtime(timing_db_path) if timing_db_exists else None
    kpi_report_path = get_kpi_report_path(log_path)
    kpi_file_exists = os.path.exists(kpi_report_path)
    has_timing_reports = bool(get_timing_report_paths(run_directory, log_meta["Stage"]))

    status, comments, extract_completed, rerun_count = _compute_status(
        previous_state,
        file_info,
        source_db_exists,
        source_db_mtime,
        timing_db_exists,
        timing_db_mtime,
        kpi_file_exists,
        has_timing_reports,
    )
    state_entry = {
        "Comments": comments,
        "Extract_Completed": extract_completed,
        "Last_Extract_Submission": str(previous_state.get("Last_Extract_Submission") or "").strip(),
        "Rerun": rerun_count,
        "Status": status,
    }
    tracker_record = build_tracker_record(log_path, state_entry, meta=log_meta, file_info=file_info)

    return {
        "file_info": file_info,
        "has_timing_reports": has_timing_reports,
        "kpi_report_path": kpi_report_path,
        "log_meta": log_meta,
        "log_path": log_path,
        "run_directory": run_directory,
        "source_db_path": source_db_path,
        "state_changed": state_entry != previous_state,
        "state_entry": state_entry,
        "state_key": state_key,
        "timing_db_path": timing_db_path,
        "tracker_record": tracker_record,
    }
