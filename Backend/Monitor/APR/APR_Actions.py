import json
import os
import signal
import subprocess
import sys
import time

import APR_DB_Operations
import APR_Utils
from APR_Definitions import (
    FORCE_EXTRACT_FILE_NAME,
    LOG_DIR,
    POLL_SECONDS,
    STATE_AWAIT,
    STATE_DIR,
    STATE_DONE,
    STATE_EXTRACT_FAILED,
    STATE_EXTRACTING,
    STATE_FAILED,
    STATE_FILE_NAME,
    now_str,
    today_log_file,
)


RUNTIME_FLAGS = {"stop_requested": False}
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


def _request_stop(*_args):
    """Mark the monitor for shutdown after the current extraction completes."""
    RUNTIME_FLAGS["stop_requested"] = True


def _is_file_state_key(state_key):
    """Return True when the JSON key matches the expected job--milestone--block--stage format."""
    return isinstance(state_key, str) and state_key.count("--") == 3


def _sanitize_state_entry(state_entry):
    """Keep only supported per-file state fields before the state is used or saved."""
    if not isinstance(state_entry, dict):
        return {}
    return {
        field_name: state_entry[field_name]
        for field_name in STATE_ENTRY_FIELDS
        if field_name in state_entry
    }


def _install_signal_handlers():
    """Register signal handlers so stop requests become graceful shutdowns."""
    for signal_name in ("SIGINT", "SIGTERM", "SIGBREAK"):
        sig = getattr(signal, signal_name, None)
        if sig is not None:
            signal.signal(sig, _request_stop)


def _write_atomic_file(path, text):
    """Write a file through a temporary path so state files are never half-written."""
    temp_file = f"{path}.tmp"
    with open(temp_file, "w", encoding="utf-8") as outfile:
        outfile.write(text)
        outfile.flush()
        os.fsync(outfile.fileno())
    os.replace(temp_file, path)


def _append_log(context, message):
    """Append one timestamped line to the current APR monitor log file."""
    log_file = os.path.join(context["log_dir"], today_log_file())
    with open(log_file, "a", encoding="utf-8") as logfile:
        logfile.write(f"{now_str()} | {message}\n")


def _load_state_file(state_file):
    """Load the per-file JSON state dictionary from disk."""
    try:
        with open(state_file, "r", encoding="utf-8") as infile:
            raw_state = json.load(infile)
    except Exception:
        return {}

    if not isinstance(raw_state, dict):
        return {}

    return {
        state_key: _sanitize_state_entry(state_entry)
        for state_key, state_entry in raw_state.items()
        if _is_file_state_key(state_key) and isinstance(state_entry, dict)
    }


def _save_state_file(context):
    """Persist the current per-file state dictionary to disk."""
    clean_state = {
        state_key: _sanitize_state_entry(state_entry)
        for state_key, state_entry in context["state_by_file"].items()
        if _is_file_state_key(state_key)
    }
    context["state_by_file"] = clean_state
    payload = json.dumps(clean_state, indent=2, sort_keys=True)
    _write_atomic_file(context["state_file"], payload)
    context["state_dirty"] = False


def _find_active_extraction_key(state_by_file):
    """Return the run key currently marked as extracting, if any."""
    for state_key, state_entry in state_by_file.items():
        if state_entry.get("Last_status") == STATE_EXTRACTING:
            return state_key
    return None


def _process_is_running(process_id):
    """Check whether a previously started extractor process is still alive."""
    if not process_id or os.name == "nt":
        return False
    try:
        os.kill(process_id, 0)
        return True
    except OSError:
        return False


def _finish_active_extraction(context, state_key, state_entry, return_code):
    """Update one file state after its extraction finishes, fails, or disappears."""
    updated_state = dict(state_entry or {})
    updated_state["Extraction_pid"] = None
    updated_state["Extraction_started_at"] = None
    updated_state["Last_extract_finished_at"] = now_str()

    if return_code == 0:
        updated_state["Last_status"] = STATE_DONE
        updated_state["Last_extracted_mtime"] = updated_state.get("Last_seen_mtime")
        updated_state["Force_extract"] = 0
        updated_state["Last_extract_result"] = "success"
        context["completed_extraction_count"] += 1
        _append_log(context, f"Completed extraction | {state_key}")
    elif return_code is None:
        updated_state["Last_status"] = STATE_AWAIT
        updated_state["Force_extract"] = 1
        updated_state["Last_extract_result"] = "restart-required"
    else:
        updated_state["Last_status"] = STATE_EXTRACT_FAILED
        updated_state["Last_extract_result"] = f"rc={return_code}"
        _append_log(context, f"Extraction failed | {state_key} | rc={return_code}")

    context["state_by_file"][state_key] = updated_state
    context["active_process"] = None
    context["active_state_key"] = None
    context["state_dirty"] = True
    _save_state_file(context)


def _refresh_active_extraction(context):
    """Re-check the single in-flight extraction and finalize it when it finishes."""
    active_state_key = context["active_state_key"]
    if not active_state_key:
        if context["active_process"] and context["active_process"].poll() is not None:
            context["active_process"] = None
        return

    active_state = context["state_by_file"].get(active_state_key, {})
    extractor_pid = active_state.get("Extraction_pid")

    if context["active_process"] and extractor_pid and context["active_process"].pid == extractor_pid:
        return_code = context["active_process"].poll()
        if return_code is None:
            return
        _finish_active_extraction(context, active_state_key, active_state, return_code)
        return

    if not _process_is_running(extractor_pid):
        _finish_active_extraction(context, active_state_key, active_state, None)


def _load_force_extract_requests(context):
    """Read force-extract keys from text file and apply them onto per-file state."""
    force_extract_file = context["force_extract_file"]
    if not os.path.exists(force_extract_file):
        _write_atomic_file(force_extract_file, "")
        return

    requested_keys = []
    with open(force_extract_file, "r", encoding="utf-8") as infile:
        for line in infile:
            state_key = line.strip()
            if _is_file_state_key(state_key) and state_key not in requested_keys:
                requested_keys.append(state_key)

    if not requested_keys:
        return

    for state_key in requested_keys:
        context["state_by_file"].setdefault(state_key, {"Created": now_str()})
        context["state_by_file"][state_key]["Force_extract"] = 1
        if context["state_by_file"][state_key].get("Last_status") != STATE_EXTRACTING:
            context["state_by_file"][state_key]["Last_status"] = STATE_AWAIT

    context["state_dirty"] = True
    _save_state_file(context)
    _write_atomic_file(force_extract_file, "")


def _write_iteration_summary(context):
    """Record how many extractions are still queued and how many finished this loop."""
    _append_log(
        context,
        f"Queued_Extractions = {context['queued_extraction_count']} | "
        f"Completed_Extractions = {context['completed_extraction_count']}",
    )


def CHECK_SYS_ARGS():
    """Validate CLI input, create directories, and build the monitor context."""
    if len(sys.argv) != 2:
        print("Usage: python3 APR.py <project_code>")
        sys.exit(1)

    project_code = sys.argv[1]
    project_dashai_dir = f"/proj/{project_code}/DashAI"
    state_dir = os.path.join(project_dashai_dir, STATE_DIR)

    context = {
        "project_code": project_code,
        "project_dashai_dir": project_dashai_dir,
        "log_dir": os.path.join(project_dashai_dir, LOG_DIR),
        "state_file": os.path.join(state_dir, STATE_FILE_NAME),
        "force_extract_file": os.path.join(state_dir, FORCE_EXTRACT_FILE_NAME),
        "tracker_connection": APR_DB_Operations.init_db(project_dashai_dir),
        "state_by_file": {},
        "active_process": None,
        "active_state_key": None,
        "state_dirty": False,
        "queued_extraction_count": 0,
        "completed_extraction_count": 0,
        "remaining_files": 0,
    }

    os.makedirs(context["log_dir"], exist_ok=True)
    os.makedirs(state_dir, exist_ok=True)
    if not os.path.exists(context["force_extract_file"]):
        _write_atomic_file(context["force_extract_file"], "")

    _install_signal_handlers()
    _append_log(context, "APR monitor started")
    return context


def GET_MONITOR_FILES(context):
    """Reload per-file state, refresh the active extraction, and list current logs."""
    context["queued_extraction_count"] = 0
    context["completed_extraction_count"] = 0
    context["state_by_file"] = _load_state_file(context["state_file"])
    context["active_state_key"] = _find_active_extraction_key(context["state_by_file"])
    context["state_dirty"] = False

    _refresh_active_extraction(context)
    context["active_state_key"] = _find_active_extraction_key(context["state_by_file"])
    _load_force_extract_requests(context)
    context["active_state_key"] = _find_active_extraction_key(context["state_by_file"])

    monitor_files = APR_Utils.get_log_paths(context["project_dashai_dir"])
    context["remaining_files"] = len(monitor_files)
    if not monitor_files:
        _write_iteration_summary(context)
    return monitor_files


def GET_FILE_STATUS(context, log_path):
    """Build the tracker row and current state for one monitored log file."""
    log_meta = APR_Utils.parse_log_args(log_path)
    file_info = APR_Utils.get_file_info(log_path)
    state_key = log_meta["State_key"]
    saved_state = context["state_by_file"].get(state_key, {})
    state_entry = dict(saved_state)
    previous_status = state_entry.get("Last_status")
    state_entry.setdefault("Created", now_str())

    tracker_record = APR_Utils.build_record(log_path, state_entry["Created"], log_meta, file_info)
    status, state_entry, rerun_count = APR_Utils.compute_status(
        state_entry,
        log_path,
        file_info["mtime"],
        file_info["size"],
        context["active_state_key"] == state_key,
    )
    tracker_record["Status"] = status
    tracker_record["Rerun"] = rerun_count

    if status == STATE_AWAIT:
        context["queued_extraction_count"] += 1

    return {
        "state_key": state_key,
        "log_path": log_path,
        "tracker_record": tracker_record,
        "state_entry": state_entry,
        "previous_status": previous_status,
        "state_changed": state_entry != saved_state,
    }


def PERFORM_STATUS_ACTION(context, file_item):
    """Start the next sequential extraction when this file is waiting and no other one is active."""
    if file_item["tracker_record"]["Status"] != STATE_AWAIT:
        return
    if context["active_state_key"] or RUNTIME_FLAGS["stop_requested"]:
        return

    run_dir = file_item["log_path"].replace(
        f"/logs/{file_item['tracker_record']['Stage']}.log",
        "",
    )
    command, environment = APR_Utils.get_timing_capture_command(
        run_dir,
        file_item["tracker_record"]["Stage"],
        context["project_code"],
    )
    context["active_process"] = subprocess.Popen(
        command,
        shell=True,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    context["active_state_key"] = file_item["state_key"]
    context["queued_extraction_count"] = max(context["queued_extraction_count"] - 1, 0)

    file_item["tracker_record"]["Status"] = STATE_EXTRACTING
    file_item["state_entry"]["Last_status"] = STATE_EXTRACTING
    file_item["state_entry"]["Force_extract"] = 0
    file_item["state_entry"]["Extraction_pid"] = context["active_process"].pid
    file_item["state_entry"]["Extraction_started_at"] = now_str()
    file_item["state_entry"]["Last_extract_result"] = "running"
    file_item["state_changed"] = True
    context["state_dirty"] = True


def UPDATE_APR_TRACKER(context, file_item):
    """Write the latest user-facing tracker row for this file into SQLite."""
    file_item["tracker_record"] = APR_Utils.apply_kpi_status(
        file_item["tracker_record"],
        file_item["log_path"],
    )
    if (
        file_item["state_entry"].get("Last_status") == STATE_DONE
        and file_item["tracker_record"]["Status"] == STATE_FAILED
    ):
        file_item["state_entry"]["Last_status"] = STATE_FAILED
        file_item["state_changed"] = True

    APR_DB_Operations.upsert_tracker(context["tracker_connection"], file_item["tracker_record"])


def UPDATE_APR_STATE(context, file_item):
    """Save the updated per-file JSON state when this file changed."""
    context["state_by_file"][file_item["state_key"]] = file_item["state_entry"]
    if file_item["state_changed"] or context["state_dirty"]:
        _save_state_file(context)


def UPDATE_APR_LOG(context, file_item):
    """Log status transitions and write one loop summary after all files are checked."""
    if (
        file_item["previous_status"]
        and file_item["previous_status"] != file_item["tracker_record"]["Status"]
    ):
        _append_log(
            context,
            f"Status changed | {file_item['state_key']} | "
            f"{file_item['previous_status']} -> {file_item['tracker_record']['Status']}",
        )

    context["remaining_files"] -= 1
    if context["remaining_files"] <= 0:
        _write_iteration_summary(context)


def SHOULD_EXIT(context):
    """Tell the main loop to exit only after shutdown is requested and no extraction is active."""
    return RUNTIME_FLAGS["stop_requested"] and not context["active_state_key"]


def SLEEP(context):
    """Pause between loops while polling faster when an extraction is still active."""
    sleep_seconds = 5 if context["active_state_key"] or RUNTIME_FLAGS["stop_requested"] else POLL_SECONDS
    for _ in range(sleep_seconds):
        if SHOULD_EXIT(context):
            return
        time.sleep(1)


def CLOSE(context):
    """Flush any pending state changes, close the tracker DB, and log shutdown."""
    if context["state_dirty"]:
        _save_state_file(context)
    context["tracker_connection"].close()
    _append_log(context, "APR monitor stopped")
