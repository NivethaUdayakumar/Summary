import json
import os
from pathlib import Path

import APR_DB_ACTIONS
import APR_VARS
import Backend.Monitor.APR.MONITORING.APR_SLEEP as APR_SLEEP
from Backend.Monitor.APR.MONITORING import APR_ITEM_STATUS
from Backend.Monitor.APR.MONITORING import APR_STATUS_ACTION
from Backend.Monitor.APR.MONITORING import APR_UPDATE_LOG


def build_context(project_code):
    """
    Function Name: build_context
    Purpose: Build the APR flow runtime context that the central FLOW monitor keeps reusing across monitor cycles.
    Input Params: project_code (str)
    Output: context (dict)
    """
    APR_SLEEP.reset_stop_request()
    APR_SLEEP.install_signal_handlers()
    return {
        "force_extract_dirty": False,
        "force_extract_payload": None,
        "force_extract_path": None,
        "logger": None,
        "logger_path": None,
        "project_code": str(project_code or "").strip(),
        "runtime_paths": {},
        "state": {},
        "state_dirty": False,
        "writer": None,
        "writer_db_path": None,
    }


def get_runtime_paths(context):
    """
    Function Name: get_runtime_paths
    Purpose: Rebuild the APR runtime paths from the latest APR_VARS values using absolute paths every monitor cycle.
    Input Params: context (dict)
    Output: runtime_paths (dict)
    """
    settings = APR_VARS.get_runtime_settings()
    dashai_dir = Path(os.path.abspath(str(Path(settings["PROJECTS_BASE_DIR"]) / context["project_code"] / "DashAI")))
    state_dir = Path(os.path.abspath(str(dashai_dir / settings["STATE_DIR"])))
    log_dir = Path(os.path.abspath(str(dashai_dir / settings["LOG_DIR"])))
    force_extract_file = Path(os.path.abspath(str(dashai_dir / settings["FORCE_EXTRACT_FILE_NAME"])))
    state_file = Path(os.path.abspath(str(state_dir / settings["STATE_FILE_NAME"])))
    log_file = Path(os.path.abspath(str(log_dir / APR_VARS.today_log_file())))
    timing_script = Path(os.path.abspath(str(Path(__file__).resolve().parents[1] / "EXTRACTORS" / "APR_TIMING_INNOVUS.py")))
    return {
        "dashai_dir": dashai_dir,
        "force_extract_file": force_extract_file,
        "log_dir": log_dir,
        "log_file": log_file,
        "settings": settings,
        "state_dir": state_dir,
        "state_file": state_file,
        "timing_script": timing_script,
    }


def refresh_runtime_context(context):
    """
    Function Name: refresh_runtime_context
    Purpose: Refresh APR folders, logger, writer, and force-extract files using the latest runtime settings.
    Input Params: context (dict)
    Output: runtime_paths (dict)
    """
    runtime_paths = get_runtime_paths(context)
    runtime_paths["dashai_dir"].mkdir(parents=True, exist_ok=True)
    runtime_paths["state_dir"].mkdir(parents=True, exist_ok=True)
    runtime_paths["log_dir"].mkdir(parents=True, exist_ok=True)

    ensure_force_extract_file(runtime_paths["force_extract_file"])
    APR_UPDATE_LOG.ensure_logger(context, runtime_paths["log_file"])
    ensure_writer(context, runtime_paths["dashai_dir"])
    APR_UPDATE_LOG.remove_old_logs(runtime_paths["log_dir"])

    context["runtime_paths"] = runtime_paths
    context["force_extract_path"] = str(runtime_paths["force_extract_file"])
    return runtime_paths


def ensure_writer(context, dashai_dir):
    """
    Function Name: ensure_writer
    Purpose: Keep the APR SQLite writer attached to the current absolute tracker database path.
    Input Params: context (dict), dashai_dir (str | os.PathLike)
    Output: writer (APR_DB_ACTIONS.SQLiteWriter)
    """
    db_path = APR_DB_ACTIONS.get_db_path(str(dashai_dir))
    if context.get("writer") is not None and context.get("writer_db_path") == db_path:
        return context["writer"]

    writer = context.get("writer")
    if writer is not None:
        try:
            writer.close()
        except Exception:
            pass

    context["writer"] = APR_DB_ACTIONS.SQLiteWriter(db_path).start()
    context["writer_db_path"] = db_path
    return context["writer"]


def ensure_force_extract_file(force_extract_file):
    """
    Function Name: ensure_force_extract_file
    Purpose: Create the force-extract JSON file with the expected template when it does not exist yet.
    Input Params: force_extract_file (str | os.PathLike)
    Output: outputs (None)
    """
    absolute_force_extract_file = Path(os.path.abspath(str(force_extract_file)))
    if absolute_force_extract_file.exists():
        return
    absolute_force_extract_file.parent.mkdir(parents=True, exist_ok=True)
    write_json_file(absolute_force_extract_file, APR_VARS.make_force_extract_template())


def get_run_directories(base_path):
    """
    Function Name: get_run_directories
    Purpose: Discover APR run directories under IMP that match the configured flow/tool marker and depth rules.
    Input Params: base_path (str)
    Output: run_directories (list[str])
    """
    settings = APR_VARS.get_runtime_settings()
    absolute_base_path = os.path.abspath(base_path)
    if not os.path.isdir(absolute_base_path):
        return []

    normalized_marker = f"/{str(settings['DEFAULT_FLOW']).lower()}/{str(settings['DEFAULT_TOOL']).lower()}/"
    base_depth = len(Path(absolute_base_path).parts)
    run_directories = []

    for root, dirs, _files in os.walk(absolute_base_path):
        root_path = Path(root)
        depth = len(root_path.parts) - base_depth
        if depth > int(settings["DEFAULT_MAXDEPTH"]):
            dirs[:] = []
            continue
        if depth >= int(settings["DEFAULT_MAXDEPTH"]):
            dirs[:] = []
        if depth < int(settings["DEFAULT_MINDEPTH"]):
            continue

        normalized_root = os.path.abspath(root).replace("\\", "/").lower()
        if normalized_marker in normalized_root:
            run_directories.append(os.path.abspath(root))

    return sorted(set(run_directories))


def get_log_paths(base_path):
    """
    Function Name: get_log_paths
    Purpose: Build the absolute list of APR stage log files that currently exist in the discovered run directories.
    Input Params: base_path (str)
    Output: log_paths (list[str])
    """
    stage_names = list(APR_VARS.get_setting("STAGES", []))
    paths = set()
    for run_dir in get_run_directories(base_path):
        for stage_name in stage_names:
            path = os.path.abspath(os.path.join(run_dir, "logs", f"{stage_name}.log"))
            if os.path.exists(path):
                paths.add(path)
    return sorted(paths)


def get_monitor_items(context):
    """
    Function Name: get_monitor_items
    Purpose: Refresh runtime state, reconcile APR batches, apply force-extract requests, and return the log files to monitor.
    Input Params: context (dict)
    Output: monitor_items (list[dict])
    """
    runtime_paths = refresh_runtime_context(context)
    context["writer"].check()

    state = load_state_file(runtime_paths["state_file"])
    force_extract_payload = load_force_extract_payload(runtime_paths["force_extract_file"])
    context["state"] = state
    context["force_extract_payload"] = force_extract_payload

    reconcile_result = APR_STATUS_ACTION.reconcile_batches(context, state)
    if reconcile_result["completed_force_keys"]:
        remove_force_extract_requests(force_extract_payload, reconcile_result["completed_force_keys"])
        context["force_extract_dirty"] = True

    reserved_state_keys = APR_STATUS_ACTION.get_reserved_state_keys(context)
    if apply_force_extract_requests(state, force_extract_payload, reserved_state_keys):
        context["state_dirty"] = True

    if reconcile_result["state_dirty"] or context["state_dirty"]:
        save_state_file(context)
    if context["force_extract_dirty"]:
        save_force_extract_payload(context)

    project_imp_dir = os.path.abspath(str(Path(runtime_paths["settings"]["PROJECTS_BASE_DIR"]) / context["project_code"] / "IMP"))
    monitor_items = []
    for log_path in get_log_paths(project_imp_dir):
        log_meta = APR_ITEM_STATUS.parse_log_args(log_path)
        state_key = log_meta["State_key"]
        monitor_items.append(
            {
                "log_path": log_path,
                "saved_state": dict(context["state"].get(state_key, {})),
                "state_key": state_key,
            }
        )
    return monitor_items


def load_state_file(state_file):
    """
    Function Name: load_state_file
    Purpose: Read the APR state JSON file and keep only valid persisted state entries.
    Input Params: state_file (str | os.PathLike)
    Output: state (dict)
    """
    absolute_state_file = os.path.abspath(str(state_file))
    try:
        with open(absolute_state_file, "r", encoding="utf-8") as input_file:
            raw_state = json.load(input_file)
    except Exception:
        return {}

    if not isinstance(raw_state, dict):
        return {}

    return {
        state_key: sanitize_state_entry(state_entry)
        for state_key, state_entry in raw_state.items()
        if is_file_state_key(state_key) and isinstance(state_entry, dict)
    }


def save_state_file(context, state=None):
    """
    Function Name: save_state_file
    Purpose: Persist the sanitized APR state payload back to the configured absolute state file path.
    Input Params: context (dict), state (dict | None)
    Output: outputs (None)
    """
    state = context.get("state") if state is None else state
    clean_state = {
        state_key: sanitize_state_entry(state_entry)
        for state_key, state_entry in (state or {}).items()
        if is_file_state_key(state_key)
    }
    write_json_file(context["runtime_paths"]["state_file"], clean_state)
    context["state"] = clean_state
    context["state_dirty"] = False


def load_force_extract_payload(force_extract_file):
    """
    Function Name: load_force_extract_payload
    Purpose: Read and normalize the APR force-extract JSON payload from its configured absolute path.
    Input Params: force_extract_file (str | os.PathLike)
    Output: payload (dict)
    """
    absolute_force_extract_file = os.path.abspath(str(force_extract_file))
    try:
        with open(absolute_force_extract_file, "r", encoding="utf-8") as input_file:
            payload = json.load(input_file)
    except Exception:
        payload = APR_VARS.make_force_extract_template()

    if isinstance(payload, list):
        payload = {
            "_comment": APR_VARS.get_setting("FORCE_EXTRACT_JSON_COMMENT"),
            APR_VARS.get_setting("FORCE_EXTRACT_JSON_ITEMS_KEY"): payload,
        }

    if not isinstance(payload, dict):
        payload = APR_VARS.make_force_extract_template()

    items_key = APR_VARS.get_setting("FORCE_EXTRACT_JSON_ITEMS_KEY")
    payload.setdefault("_comment", APR_VARS.get_setting("FORCE_EXTRACT_JSON_COMMENT"))
    payload.setdefault(items_key, [])
    if not isinstance(payload[items_key], list):
        payload[items_key] = []
    normalized_items = []
    for item in payload[items_key]:
        normalized_item = normalize_force_extract_item(item)
        if normalized_item is not None:
            normalized_items.append(normalized_item)
    payload[items_key] = normalized_items
    return payload


def save_force_extract_payload(context, payload=None):
    """
    Function Name: save_force_extract_payload
    Purpose: Persist the normalized APR force-extract request payload to its configured absolute JSON file path.
    Input Params: context (dict), payload (dict | None)
    Output: outputs (None)
    """
    payload = context.get("force_extract_payload") if payload is None else payload
    normalized_payload = {
        "_comment": APR_VARS.get_setting("FORCE_EXTRACT_JSON_COMMENT"),
        APR_VARS.get_setting("FORCE_EXTRACT_JSON_ITEMS_KEY"): [],
    }
    for item in payload.get(APR_VARS.get_setting("FORCE_EXTRACT_JSON_ITEMS_KEY"), []):
        normalized_item = normalize_force_extract_item(item)
        if normalized_item is not None:
            normalized_payload[APR_VARS.get_setting("FORCE_EXTRACT_JSON_ITEMS_KEY")].append(normalized_item)
    write_json_file(context["runtime_paths"]["force_extract_file"], normalized_payload)
    context["force_extract_payload"] = normalized_payload
    context["force_extract_dirty"] = False


def get_force_extract_items(force_extract_payload):
    """
    Function Name: get_force_extract_items
    Purpose: Return the normalized list of APR force-extract request objects from the current payload.
    Input Params: force_extract_payload (dict)
    Output: items (list[dict])
    """
    return list(force_extract_payload.get(APR_VARS.get_setting("FORCE_EXTRACT_JSON_ITEMS_KEY"), []))


def normalize_force_extract_item(item):
    """
    Function Name: normalize_force_extract_item
    Purpose: Normalize one force-extract item into the expected lowercase key structure.
    Input Params: item (dict)
    Output: normalized_item (dict | None)
    """
    if not isinstance(item, dict):
        return None

    normalized_item = {
        "job": str(item.get("job", item.get("Job", "")) or "").strip(),
        "milestone": str(item.get("milestone", item.get("Milestone", "")) or "").strip(),
        "block": str(item.get("block", item.get("Block", "")) or "").strip(),
        "stage": str(item.get("stage", item.get("Stage", "")) or "").strip(),
    }
    if not all(normalized_item.values()):
        return None
    return normalized_item


def force_extract_item_to_state_key(item):
    """
    Function Name: force_extract_item_to_state_key
    Purpose: Convert one normalized force-extract request into the APR state key used by the monitor runtime.
    Input Params: item (dict)
    Output: state_key (str | None)
    """
    normalized_item = normalize_force_extract_item(item)
    if normalized_item is None:
        return None
    return APR_VARS.make_state_key(
        normalized_item["job"],
        normalized_item["milestone"],
        normalized_item["block"],
        normalized_item["stage"],
    )


def remove_force_extract_requests(force_extract_payload, completed_state_keys):
    """
    Function Name: remove_force_extract_requests
    Purpose: Remove completed force-extract requests after their batches finish.
    Input Params: force_extract_payload (dict), completed_state_keys (set[str] | list[str])
    Output: outputs (None)
    """
    completed_state_keys = set(completed_state_keys or [])
    if not completed_state_keys:
        return

    items_key = APR_VARS.get_setting("FORCE_EXTRACT_JSON_ITEMS_KEY")
    force_extract_payload[items_key] = [
        item
        for item in get_force_extract_items(force_extract_payload)
        if force_extract_item_to_state_key(item) not in completed_state_keys
    ]


def apply_force_extract_requests(state, force_extract_payload, reserved_state_keys):
    """
    Function Name: apply_force_extract_requests
    Purpose: Mark requested APR runs for extraction while respecting runs already reserved by pending or active batches.
    Input Params: state (dict), force_extract_payload (dict), reserved_state_keys (set[str] | list[str])
    Output: state_changed (bool)
    """
    settings = APR_VARS.get_runtime_settings()
    state_await = settings["STATE_AWAIT"]
    reserved_state_keys = set(reserved_state_keys or [])
    state_changed = False

    for item in get_force_extract_items(force_extract_payload):
        state_key = force_extract_item_to_state_key(item)
        if not state_key:
            continue

        state_entry = dict(state.get(state_key, {}))
        state_entry.setdefault("Created", APR_VARS.now_str())
        state_entry["Force_extract"] = 1
        if state_key not in reserved_state_keys:
            state_entry["Last_status"] = state_await

        if state_entry != state.get(state_key, {}):
            state[state_key] = state_entry
            state_changed = True

    return state_changed


def write_json_file(path, payload):
    """
    Function Name: write_json_file
    Purpose: Atomically write one JSON payload to disk using a temporary file in the same absolute directory.
    Input Params: path (str | os.PathLike), payload (dict)
    Output: outputs (None)
    """
    absolute_path = Path(os.path.abspath(str(path)))
    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    temp_file = Path(f"{absolute_path}.tmp")
    with open(temp_file, "w", encoding="utf-8") as output_file:
        json.dump(payload, output_file, indent=2, sort_keys=True)
        output_file.write("\n")
        output_file.flush()
        os.fsync(output_file.fileno())
    os.replace(temp_file, absolute_path)


def is_file_state_key(state_key):
    """
    Function Name: is_file_state_key
    Purpose: Check whether a state key matches the APR file-state key format.
    Input Params: state_key (str)
    Output: is_valid (bool)
    """
    return isinstance(state_key, str) and state_key.count("--") == 3


def sanitize_state_entry(state_entry):
    """
    Function Name: sanitize_state_entry
    Purpose: Keep only the persisted APR state fields that are allowed to be written into the state file.
    Input Params: state_entry (dict)
    Output: clean_state_entry (dict)
    """
    if not isinstance(state_entry, dict):
        return {}
    return {
        field_name: state_entry[field_name]
        for field_name in APR_VARS.get_setting("STATE_ENTRY_FIELDS", set())
        if field_name in state_entry
    }
