import importlib
import getpass
import os
import time
from pathlib import Path

import APR_VARS
from Backend.Monitor.APR.MONITORING import APR_OUTPUTS
from Backend.Monitor.APR.MONITORING import APR_STATUS_ACTION

try:
    pwd = importlib.import_module("pwd")
except ImportError:
    pwd = None


def parse_log_args(filename):
    """
    Function Name: parse_log_args
    Purpose: Parse the absolute APR log path into the job, milestone, block, stage, and state-key fields used by the monitor.
    Input Params: filename (str)
    Output: log_meta (dict)
    """
    normalized_path = os.path.abspath(filename).replace("\\", "/").strip("/")
    path_parts = normalized_path.split("/")
    job = path_parts[-3] if len(path_parts) >= 3 else ""
    milestone = path_parts[4] if len(path_parts) > 4 else ""
    block = path_parts[5] if len(path_parts) > 5 else ""
    stage = Path(filename).stem
    dft_release = get_dft_release(filename)
    return {
        "Block": block,
        "Dft_release": dft_release,
        "Job": job,
        "Milestone": milestone,
        "Stage": stage,
        "State_key": APR_VARS.make_state_key(job, milestone, block, stage),
    }


def get_dft_release(filename):
    """
    Function Name: get_dft_release
    Purpose: Resolve the DFT release name associated with one APR run by following its linked DFT input files.
    Input Params: filename (str)
    Output: dft_release (str)
    """
    try:
        log_path = Path(os.path.abspath(filename))
        input_dir = log_path.parent.parent.parent / "inputs" / "dft" / "vlog"
        if not input_dir.exists():
            return "NA"

        for candidate in input_dir.glob("*dft.v"):
            real_path = os.path.realpath(str(candidate)).replace("\\", "/")
            if "/iExchange/DFT/" in real_path:
                path_parts = real_path.strip("/").split("/")
                if len(path_parts) >= 3:
                    return path_parts[-3]
    except Exception:
        pass
    return "NA"


def get_file_info(file_path):
    """
    Function Name: get_file_info
    Purpose: Read APR log file metadata that is needed for change detection and tracker row fields.
    Input Params: file_path (str)
    Output: file_info (dict)
    """
    absolute_file_path = os.path.abspath(file_path)
    file_stat = os.stat(absolute_file_path)
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


def build_record(log_path, created, meta=None, info=None):
    """
    Function Name: build_record
    Purpose: Build the default APR tracker row for one log file before status-specific updates are applied.
    Input Params: log_path (str), created (str), meta (dict | None), info (dict | None)
    Output: tracker_record (dict)
    """
    settings = APR_VARS.get_runtime_settings()
    metadata = meta or parse_log_args(log_path)
    file_info = info or get_file_info(log_path)
    tracker_record = {
        "Block": metadata["Block"],
        "Comments": "-",
        "Created": created,
        "Dft_release": metadata["Dft_release"],
        "Job": metadata["Job"],
        "Milestone": metadata["Milestone"],
        "Modified": file_info["Modified"],
        "Promote": "no",
        "Rerun": 0,
        "Stage": metadata["Stage"],
        "Status": "",
        "User": file_info["User"],
    }
    tracker_record.update({column_name: "" for column_name in settings["KPI_COLUMNS"]})
    return tracker_record


def get_status_comment(status, state_entry):
    """
    Function Name: get_status_comment
    Purpose: Return the base tracker comment for one APR monitor status before KPI validation is applied.
    Input Params: status (str), state_entry (dict)
    Output: comment (str)
    """
    settings = APR_VARS.get_runtime_settings()
    validation_error = APR_STATUS_ACTION.get_validation_error_code(state_entry)
    if validation_error and status in {settings["STATE_FAILED"], settings["STATE_EXTRACT_FAILED"]}:
        return validation_error
    if status == settings["STATE_FAILED"]:
        return "ERR001"
    if status == settings["STATE_EXTRACT_FAILED"]:
        return "ERR003"
    return "-"


def compute_status(context, state_entry, log_path, log_meta, file_info, is_extracting):
    """
    Function Name: compute_status
    Purpose: Compute the APR monitor status for one run from file changes, source/timing outputs, persisted state, and batch activity.
    Input Params: context (dict), state_entry (dict), log_path (str), log_meta (dict), file_info (dict), is_extracting (bool)
    Output: outputs (tuple[str, str, dict, int])
    """
    settings = APR_VARS.get_runtime_settings()
    now_epoch = int(time.time())
    mtime = int(file_info["mtime"])
    size = int(file_info["size"])
    last_seen_mtime = state_entry.get("Last_seen_mtime")
    last_seen_size = state_entry.get("Last_seen_size")
    last_change_time = state_entry.get("Last_change_time")
    last_extracted_mtime = state_entry.get("Last_extracted_mtime")
    last_status = state_entry.get("Last_status")
    validation_error = APR_STATUS_ACTION.get_validation_error_code(state_entry)
    rerun_count = int(state_entry.get("Rerun", 0) or 0)
    force_extract = int(state_entry.get("Force_extract", 0) or 0)
    file_changed = last_seen_mtime is None or mtime != last_seen_mtime or size != last_seen_size

    if file_changed:
        last_change_time = now_epoch

    output_state = APR_OUTPUTS.get_output_state(context["project_code"], log_path, log_meta)
    outputs_complete = APR_OUTPUTS.outputs_are_complete(output_state)
    effective_extract_mtime = output_state["timing_db_mtime"]
    if effective_extract_mtime is None and last_extracted_mtime is not None:
        effective_extract_mtime = int(last_extracted_mtime)

    if is_extracting:
        status = settings["STATE_EXTRACTING"]
    elif force_extract == 1:
        status = settings["STATE_AWAIT"]
    elif outputs_complete:
        if effective_extract_mtime is not None and mtime > effective_extract_mtime:
            if last_status == settings["STATE_DONE"]:
                rerun_count += 1
            status = settings["STATE_AWAIT"]
        else:
            status = settings["STATE_DONE"]
    elif validation_error in {"ERR001", "ERR002"} and not file_changed:
        status = settings["STATE_FAILED"]
    elif validation_error == "ERR003" and not file_changed:
        status = settings["STATE_EXTRACT_FAILED"]
    elif last_status == settings["STATE_EXTRACTING"] and not outputs_complete:
        status = settings["STATE_AWAIT"]
    elif last_status == settings["STATE_EXTRACT_FAILED"] and not file_changed:
        status = settings["STATE_EXTRACT_FAILED"]
    elif output_state["source_db_exists"]:
        status = settings["STATE_AWAIT"]
    else:
        age = now_epoch - (last_change_time if last_change_time is not None else now_epoch)
        status = settings["STATE_RUNNING"] if age <= 15 * 60 else settings["STATE_FAILED"]

    state_entry["Last_change_time"] = last_change_time
    state_entry["Last_seen_mtime"] = mtime
    state_entry["Last_seen_size"] = size
    state_entry["Last_status"] = status
    state_entry["Rerun"] = rerun_count
    return status, get_status_comment(status, state_entry), state_entry, rerun_count


def get_item_status(context, monitor_item):
    """
    Function Name: get_item_status
    Purpose: Build the full APR monitor item payload used by status action, tracker, state, and log update steps.
    Input Params: context (dict), monitor_item (dict)
    Output: file_item (dict)
    """
    log_path = os.path.abspath(monitor_item["log_path"])
    log_meta = parse_log_args(log_path)
    file_info = get_file_info(log_path)
    state_key = log_meta["State_key"]

    # Finalize any already-ready batch items before computing a fresh status so
    # this pass uses the latest shared batch state.
    APR_STATUS_ACTION.finalize_ready_batch_items_now(context)

    saved_state = dict(context.get("state", {}).get(state_key, monitor_item.get("saved_state") or {}))
    state_entry = dict(saved_state)

    state_entry.setdefault("Created", APR_VARS.now_str())
    tracker_record = build_record(log_path, state_entry["Created"], log_meta, file_info)
    status, comment, state_entry, rerun_count = compute_status(
        context,
        state_entry,
        log_path,
        log_meta,
        file_info,
        APR_STATUS_ACTION.is_item_in_flight(context, state_key),
    )
    tracker_record["Comments"] = comment
    tracker_record["Rerun"] = rerun_count
    tracker_record["Status"] = status

    return {
        "file_info": file_info,
        "log_meta": log_meta,
        "log_path": log_path,
        "state_changed": state_entry != saved_state,
        "state_entry": state_entry,
        "state_key": state_key,
        "tracker_record": tracker_record,
    }
