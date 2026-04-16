import json
import os
import signal
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

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
    """Stop launching new extractions after the current loop finishes."""
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
    """Register signal handlers so APR.py can stop scheduling new work cleanly."""
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


def _process_is_running(process_id):
    """Return True when the given PID still exists."""
    try:
        os.kill(int(process_id), 0)
        return True
    except Exception:
        return False


def _start_detached_process(command, environment):
    """Launch one extractor process that keeps running after APR.py exits."""
    popen_kwargs = {
        "shell": True,
        "env": environment,
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if os.name == "nt":
        creationflags = (
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "DETACHED_PROCESS", 0)
        )
        if creationflags:
            popen_kwargs["creationflags"] = creationflags
    else:
        popen_kwargs["start_new_session"] = True

    return subprocess.Popen(command, **popen_kwargs).pid


def _launch_extraction(context, command, environment):
    """Use a small thread pool only to launch detached extractor processes."""
    return context["launch_executor"].submit(
        _start_detached_process,
        command,
        environment,
    ).result()


def _refresh_extraction_state(context, log_path, log_meta, file_info, state_entry):
    """Turn finished extractor PIDs into DONE or EXTRACT_FAILED states."""
    if state_entry.get("Last_status") != STATE_EXTRACTING:
        return state_entry, None

    extractor_pid = state_entry.get("Extraction_pid")
    if _process_is_running(extractor_pid):
        return state_entry, None

    updated_state = dict(state_entry)
    updated_state["Extraction_pid"] = None
    updated_state["Extraction_started_at"] = None
    updated_state["Last_extract_finished_at"] = now_str()

    if APR_Utils.timing_db_exists_for_stage(
        log_path,
        context["project_code"],
        meta=log_meta,
    ):
        updated_state["Last_status"] = STATE_DONE
        updated_state["Last_extracted_mtime"] = file_info["mtime"]
        updated_state["Force_extract"] = 0
        updated_state["Last_extract_result"] = "success"
        return updated_state, "success"

    updated_state["Last_status"] = STATE_EXTRACT_FAILED
    updated_state["Force_extract"] = 1
    updated_state["Last_extract_result"] = "failed"
    return updated_state, "failed"


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
        "launch_executor": ThreadPoolExecutor(
            max_workers=max(1, os.cpu_count() or 1),
            thread_name_prefix="apr-launch",
        ),
        "state_by_file": {},
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
    """Reload per-file state and list the current APR stage logs."""
    context["queued_extraction_count"] = 0
    context["completed_extraction_count"] = 0
    context["state_by_file"] = _load_state_file(context["state_file"])
    context["state_dirty"] = False

    _load_force_extract_requests(context)

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
    previous_status = saved_state.get("Last_status")

    state_entry = dict(saved_state)
    state_entry.setdefault("Created", now_str())
    state_entry, extraction_result = _refresh_extraction_state(
        context,
        log_path,
        log_meta,
        file_info,
        state_entry,
    )

    tracker_record = APR_Utils.build_record(log_path, state_entry["Created"], log_meta, file_info)
    is_extracting = (
        state_entry.get("Last_status") == STATE_EXTRACTING
        and _process_is_running(state_entry.get("Extraction_pid"))
    )
    status, state_entry, rerun_count = APR_Utils.compute_status(
        state_entry,
        log_path,
        file_info["mtime"],
        file_info["size"],
        is_extracting,
    )
    tracker_record["Status"] = status
    tracker_record["Rerun"] = rerun_count

    if status == STATE_AWAIT:
        context["queued_extraction_count"] += 1
    if extraction_result == "success":
        context["completed_extraction_count"] += 1

    return {
        "state_key": state_key,
        "log_path": log_path,
        "tracker_record": tracker_record,
        "state_entry": state_entry,
        "previous_status": previous_status,
        "state_changed": state_entry != saved_state,
    }


def PERFORM_STATUS_ACTION(context, file_item):
    """Launch a detached timing extraction for every file waiting to be processed."""
    if file_item["tracker_record"]["Status"] != STATE_AWAIT:
        return
    if RUNTIME_FLAGS["stop_requested"]:
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
    extractor_pid = _launch_extraction(context, command, environment)
    context["queued_extraction_count"] = max(context["queued_extraction_count"] - 1, 0)

    file_item["tracker_record"]["Status"] = STATE_EXTRACTING
    file_item["state_entry"]["Last_status"] = STATE_EXTRACTING
    file_item["state_entry"]["Force_extract"] = 0
    file_item["state_entry"]["Extraction_pid"] = extractor_pid
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


def SHOULD_EXIT(_context):
    """Stop the monitor once a shutdown signal was received."""
    return RUNTIME_FLAGS["stop_requested"]


def SLEEP(_context):
    """Pause between loops unless shutdown was requested."""
    for _ in range(POLL_SECONDS):
        if RUNTIME_FLAGS["stop_requested"]:
            return
        time.sleep(1)


def CLOSE(context):
    """Flush any pending state changes, close resources, and log shutdown."""
    if context["state_dirty"]:
        _save_state_file(context)
    context["launch_executor"].shutdown(wait=False, cancel_futures=True)
    context["tracker_connection"].close()
    _append_log(context, "APR monitor stopped")
