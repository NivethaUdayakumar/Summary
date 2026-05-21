import json
import os
from pathlib import Path

import APR_DB_ACTIONS
import APR_VARS
import Backend.Monitor.APR.MONITORING.APR_SLEEP as APR_SLEEP


def get_project_code(context):
    """
    Function Name: get_project_code
    Purpose: Return the normalized APR project code from the shared flow context.
    Input Params: context (dict)
    Output: project_code (str)
    """
    return str(context.get("project_code") or context.get("PROJECT_CODE") or "").strip()


def ensure_runtime_directories(project_code):
    """
    Function Name: ensure_runtime_directories
    Purpose: Ensure every APR runtime directory used by the monitor exists before work begins.
    Input Params: project_code (str)
    Output: outputs (None)
    """
    for path in (
        APR_VARS.get_dashai_dir(project_code),
        APR_VARS.get_state_dir(project_code),
        APR_VARS.get_log_dir_path(project_code),
        APR_VARS.get_apr_runs_dir(project_code),
        APR_VARS.get_batch_commands_dir(),
    ):
        Path(os.path.abspath(path)).mkdir(parents=True, exist_ok=True)


def _normalize_project_code(project_code):
    """
    Function Name: _normalize_project_code
    Purpose: Normalize the requested APR project code before building the monitor context.
    Input Params: project_code (str)
    Output: normalized_project_code (str)
    """
    normalized_project_code = str(project_code or "").strip()
    if not normalized_project_code:
        raise ValueError("PROJECT_CODE is required")
    return normalized_project_code


def _sanitize_state_entry(state_entry):
    """
    Function Name: _sanitize_state_entry
    Purpose: Keep only the supported APR state-entry fields and normalize their basic value types.
    Input Params: state_entry (dict)
    Output: clean_state_entry (dict)
    """
    if not isinstance(state_entry, dict):
        return {}

    clean_state_entry = {
        "Comments": state_entry.get("Comments"),
        "Extract_Completed": bool(state_entry.get("Extract_Completed", False)),
        "Last_Extract_Submission": str(state_entry.get("Last_Extract_Submission") or "").strip(),
        "Rerun": max(0, int(state_entry.get("Rerun", 0) or 0)),
        "Status": state_entry.get("Status"),
    }
    if not clean_state_entry["Last_Extract_Submission"]:
        clean_state_entry["Last_Extract_Submission"] = ""
    return clean_state_entry


def _write_json_file(path, payload):
    """
    Function Name: _write_json_file
    Purpose: Atomically write one JSON payload to disk using a temporary file in the same directory.
    Input Params: path (str | os.PathLike), payload (dict)
    Output: outputs (None)
    """
    absolute_path = Path(os.path.abspath(str(path)))
    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = absolute_path.with_suffix(f"{absolute_path.suffix}.tmp")
    with open(temp_path, "w", encoding="utf-8", newline="\n") as output_file:
        json.dump(payload, output_file, indent=2, sort_keys=True)
        output_file.write("\n")
        output_file.flush()
        os.fsync(output_file.fileno())
    os.replace(temp_path, absolute_path)


def load_state(project_code):
    """
    Function Name: load_state
    Purpose: Load the APR state JSON file and keep only valid run-state entries.
    Input Params: project_code (str)
    Output: state (dict)
    """
    state_file_path = APR_VARS.get_state_file_path(project_code)
    try:
        with open(state_file_path, "r", encoding="utf-8") as input_file:
            raw_state = json.load(input_file)
    except Exception:
        return {}

    if not isinstance(raw_state, dict):
        return {}

    clean_state = {}
    for state_key, state_entry in raw_state.items():
        if not isinstance(state_key, str) or state_key.count("--") != 3:
            continue
        clean_state[state_key] = _sanitize_state_entry(state_entry)
    return clean_state


def save_state(context):
    """
    Function Name: save_state
    Purpose: Persist the current APR monitor state back to APR_STATE.json after sanitizing every entry.
    Input Params: context (dict)
    Output: outputs (None)
    """
    project_code = get_project_code(context)
    clean_state = {
        state_key: _sanitize_state_entry(state_entry)
        for state_key, state_entry in dict(context.get("state") or {}).items()
        if isinstance(state_key, str) and state_key.count("--") == 3
    }
    context["state"] = clean_state
    _write_json_file(APR_VARS.get_state_file_path(project_code), clean_state)


def append_log(context, message):
    """
    Function Name: append_log
    Purpose: Append one APR monitor log line to the current day's project log file.
    Input Params: context (dict), message (str)
    Output: outputs (None)
    """
    project_code = get_project_code(context)
    ensure_runtime_directories(project_code)
    log_file_path = APR_VARS.get_log_file_path(project_code)
    with open(log_file_path, "a", encoding="utf-8", newline="\n") as output_file:
        output_file.write(f"{APR_VARS.now_str()} | {str(message or '').strip()}\n")


def build_context(project_code):
    """
    Function Name: build_context
    Purpose: Build the APR monitoring context, reset persisted statuses/comments, and start the shared SQLite writer.
    Input Params: project_code (str)
    Output: context (dict)
    """
    normalized_project_code = _normalize_project_code(project_code)
    APR_SLEEP.reset_stop_request()
    APR_SLEEP.install_signal_handlers()
    ensure_runtime_directories(normalized_project_code)

    context = {
        "db_writer": APR_DB_ACTIONS.SQLiteWriter(APR_VARS.get_tracker_db_path(normalized_project_code)).start(),
        "project_code": normalized_project_code,
        "state": load_state(normalized_project_code),
    }
    for state_entry in context["state"].values():
        state_entry["Status"] = None
        state_entry["Comments"] = None
    save_state(context)
    append_log(context, "monitor_started")
    return context
