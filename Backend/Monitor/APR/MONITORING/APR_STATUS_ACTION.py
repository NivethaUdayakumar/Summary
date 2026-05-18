from collections import OrderedDict
import os
import shlex
import signal
import subprocess
import time
from pathlib import Path

import APR_VARS
import psutil
from Backend.Monitor.APR.EXTRACTORS.APR_KPI_EXTRACT import get_kpi_report_path
from Backend.Monitor.APR.EXTRACTORS.APR_TIMING_INNOVUS import get_timing_report_paths
import Backend.Monitor.APR.MONITORING.APR_SLEEP as APR_SLEEP
from Backend.Monitor.APR.MONITORING import APR_UPDATE_LOG


_BATCH_RUNTIMES = {}
_VALIDATION_RESULT_PREFIX = "validation_failed:"
_BATCH_PYTHON_MODULE = "Python3/3.11.1"
_BATCH_PYTHON_COMMAND = "python3"


def _get_runtime(context):
    """
    Function Name: _get_runtime
    Purpose: Return the in-memory batch runtime for the current project code, creating it when needed.
    Input Params: context (dict)
    Output: runtime (dict)
    """
    project_code = context["project_code"]
    runtime = _BATCH_RUNTIMES.get(project_code)
    if runtime is None:
        runtime = {
            "available_batch_slots": [],
            "batch_slots_initialized": False,
            "configured_parallel_batch_count": 0,
            "next_batch_id": 1,
            "pending_items": OrderedDict(),
            "running_batches": {},
        }
        _BATCH_RUNTIMES[project_code] = runtime
    return runtime


def get_reserved_state_keys(context):
    """
    Function Name: get_reserved_state_keys
    Purpose: Return the set of APR state keys already reserved by pending or running batch work.
    Input Params: context (dict)
    Output: reserved_state_keys (set[str])
    """
    runtime = _get_runtime(context)
    reserved_state_keys = set(runtime["pending_items"].keys())
    for batch_info in runtime["running_batches"].values():
        reserved_state_keys.update(batch_info["state_keys"])
    return reserved_state_keys


def is_item_in_flight(context, state_key):
    """
    Function Name: is_item_in_flight
    Purpose: Check whether one APR run is already part of an active batch subprocess.
    Input Params: context (dict), state_key (str)
    Output: is_in_flight (bool)
    """
    runtime = _get_runtime(context)
    return any(state_key in batch_info["state_keys"] for batch_info in runtime["running_batches"].values())


def get_validation_error_code(state_entry):
    """
    Function Name: get_validation_error_code
    Purpose: Read the persisted APR validation-failure code from one state entry when the run was rejected before extraction.
    Input Params: state_entry (dict)
    Output: error_code (str)
    """
    if not isinstance(state_entry, dict):
        return ""

    last_extract_result = str(state_entry.get("Last_extract_result") or "").strip()
    if not last_extract_result.startswith(_VALIDATION_RESULT_PREFIX):
        return ""

    error_code = last_extract_result[len(_VALIDATION_RESULT_PREFIX) :].strip().upper()
    if error_code == "ERR001" and state_entry.get("Last_status") == APR_VARS.get_setting("STATE_EXTRACT_FAILED"):
        return "ERR003"
    return error_code if error_code in {"ERR001", "ERR002", "ERR003"} else ""


def check_valid_job(file_item):
    """
    Function Name: check_valid_job
    Purpose: Reject APR runs before batch submission when their KPI report or timing report inputs are missing.
    Input Params: file_item (dict)
    Output: error_code (str)
    """
    log_path = os.path.abspath(file_item["log_path"])
    if not os.path.exists(get_kpi_report_path(log_path)):
        return "ERR002"

    run_dir = os.path.abspath(str(Path(log_path).resolve().parent.parent))
    timing_report_paths = get_timing_report_paths(run_dir, file_item["log_meta"]["Stage"])
    if not timing_report_paths:
        return "ERR003"

    return ""


def reconcile_batches(context, state):
    """
    Function Name: reconcile_batches
    Purpose: Finalize completed APR batches, update state results, and submit any next ready batches.
    Input Params: context (dict), state (dict)
    Output: reconcile_result (dict)
    """
    runtime = _get_runtime(context)
    state_dirty = False
    completed_force_keys = set()

    for batch_id, batch_info in list(runtime["running_batches"].items()):
        progress_result = _finalize_ready_batch_items(context, state, batch_info)
        state_dirty = state_dirty or progress_result["state_dirty"]
        completed_force_keys.update(progress_result["completed_force_keys"])

        return_code = batch_info["process"].poll()
        if return_code is None:
            continue

        runtime["running_batches"].pop(batch_id, None)
        _release_batch_slot(runtime, batch_info.get("slot_index"))
        result = _finalize_batch(context, state, batch_info, return_code)
        state_dirty = state_dirty or result["state_dirty"]
        completed_force_keys.update(result["completed_force_keys"])
        APR_UPDATE_LOG.log_batch_completion(
            context,
            batch_id,
            batch_info["item_count"],
            result["success_count"],
            result["failed_count"],
        )

    _dispatch_ready_batches(context)
    return {
        "completed_force_keys": completed_force_keys,
        "state_dirty": state_dirty,
    }


def perform_status_action(context, file_item):
    """
    Function Name: perform_status_action
    Purpose: Queue APR runs that are waiting for extraction and mark them as extracting once they enter a batch.
    Input Params: context (dict), file_item (dict)
    Output: outputs (None)
    """
    state_await = APR_VARS.get_setting("STATE_AWAIT")
    if file_item["tracker_record"]["Status"] != state_await or APR_SLEEP.should_exit():
        return

    error_code = check_valid_job(file_item)
    if error_code:
        _remove_pending_item(context, file_item["state_key"])
        _mark_file_item_invalid(context, file_item, error_code)
        _remove_force_extract_request(context, file_item["state_key"])
        return

    runtime = _get_runtime(context)
    state_key = file_item["state_key"]
    if state_key not in runtime["pending_items"] and not is_item_in_flight(context, state_key):
        runtime["pending_items"][state_key] = _build_batch_item(context, file_item)

    _dispatch_ready_batches(context)

    if is_item_in_flight(context, state_key):
        _mark_file_item_extracting(context, file_item)


def shutdown_runtime(context, state):
    """
    Function Name: shutdown_runtime
    Purpose: Terminate running APR batch subprocesses, reset affected files to await state, and clear runtime queues.
    Input Params: context (dict), state (dict)
    Output: state_dirty (bool)
    """
    runtime = _BATCH_RUNTIMES.get(context["project_code"])
    if runtime is None:
        return False

    state_dirty = False
    for batch_info in list(runtime["running_batches"].values()):
        _terminate_batch_process(batch_info["process"])
        for batch_item in batch_info["items"]:
            state_entry = _set_await_state(state, batch_item, "terminated")
            _push_batch_item_tracker_state(context, batch_item, state_entry)
            state_dirty = True

    for batch_item in list(runtime["pending_items"].values()):
        state_entry = _set_await_state(state, batch_item, "pending")
        _push_batch_item_tracker_state(context, batch_item, state_entry)
        state_dirty = True

    runtime["running_batches"].clear()
    runtime["pending_items"].clear()
    _sync_batch_command_slots(
        context,
        runtime,
        max(1, int(APR_VARS.get_runtime_settings()["MAX_PARALLEL_BATCHES"])),
        force_reset=True,
    )
    _BATCH_RUNTIMES.pop(context["project_code"], None)
    return state_dirty


def _build_batch_item(context, file_item):
    """
    Function Name: _build_batch_item
    Purpose: Build the lightweight batch payload for one APR run that can be safely kept outside the persisted state file.
    Input Params: context (dict), file_item (dict)
    Output: batch_item (dict)
    """
    log_meta = file_item["log_meta"]
    return {
        "queued_at": time.time(),
        "log_meta": dict(log_meta),
        "log_mtime": file_item["file_info"]["mtime"],
        "log_path": os.path.abspath(file_item["log_path"]),
        "run_dir": os.path.abspath(str(Path(file_item["log_path"]).resolve().parent.parent)),
        "stage": log_meta["Stage"],
        "state_key": file_item["state_key"],
        "timing_db_path": _get_timing_db_path(context["project_code"], log_meta),
    }


def _get_timing_db_path(project_code, log_meta):
    """
    Function Name: _get_timing_db_path
    Purpose: Build the absolute DashAI timing database path that should be created for one APR run extraction.
    Input Params: project_code (str), log_meta (dict)
    Output: db_path (str)
    """
    project_root = Path(
        os.path.abspath(
            str(Path(APR_VARS.get_setting("PROJECTS_BASE_DIR")) / project_code / "DashAI" / "APR_RUNS")
        )
    )
    return str(project_root / log_meta["Block"] / log_meta["Milestone"] / log_meta["Job"] / f"{log_meta['Stage']}_timing.db")


def _dispatch_ready_batches(context):
    """
    Function Name: _dispatch_ready_batches
    Purpose: Launch new APR batch subprocesses when batch-size, wait-time, and max-parallel rules allow it.
    Input Params: context (dict)
    Output: outputs (None)
    """
    runtime = _get_runtime(context)
    settings = APR_VARS.get_runtime_settings()
    batch_size = max(1, int(settings["BATCH_SIZE"]))
    max_parallel_batches = max(1, int(settings["MAX_PARALLEL_BATCHES"]))
    batch_wait_time = max(0, int(settings["BATCH_RUN_WAIT_TIME"]))
    _sync_batch_command_slots(context, runtime, max_parallel_batches)

    while len(runtime["running_batches"]) < max_parallel_batches:
        pending_count = len(runtime["pending_items"])
        if pending_count == 0:
            return

        if pending_count >= batch_size:
            item_count = batch_size
        else:
            oldest_item = next(iter(runtime["pending_items"].values()))
            if time.time() - oldest_item["queued_at"] < batch_wait_time:
                return
            item_count = pending_count

        batch_items = [runtime["pending_items"].popitem(last=False)[1] for _ in range(item_count)]
        if not _submit_batch(context, runtime, batch_items):
            return


def _submit_batch(context, runtime, batch_items):
    """
    Function Name: _submit_batch
    Purpose: Start one APR batch subprocess and move its items from the pending queue into the running-batch set.
    Input Params: context (dict), runtime (dict), batch_items (list[dict])
    Output: submitted (bool)
    """
    batch_id = f"{context['project_code']}-{runtime['next_batch_id']}"
    runtime["next_batch_id"] += 1

    max_parallel_batches = max(1, int(APR_VARS.get_runtime_settings()["MAX_PARALLEL_BATCHES"]))
    slot_index = _claim_batch_slot(context, runtime, max_parallel_batches)
    if slot_index is None:
        _requeue_batch_items(runtime, batch_items)
        return False

    batch_file_path = _get_batch_command_file_path(context["runtime_paths"]["batch_commands_dir"], slot_index)
    command_text = _build_batch_command(batch_file_path)
    submitted_at = time.time()
    try:
        _write_batch_file(batch_file_path, _build_batch_file_lines(context, batch_items))
        process = _spawn_batch_process(command_text)
    except Exception:
        _release_batch_slot(runtime, slot_index)
        _requeue_batch_items(runtime, batch_items)
        APR_UPDATE_LOG.log_batch_completion(context, batch_id, len(batch_items), 0, len(batch_items))
        return False

    batch_info = {
        "batch_id": batch_id,
        "batch_file_path": batch_file_path,
        "command_text": command_text,
        "item_count": len(batch_items),
        "items": batch_items,
        "process": process,
        "slot_index": slot_index,
        "state_keys": {batch_item["state_key"] for batch_item in batch_items},
        "submitted_at": submitted_at,
        "success_count": 0,
        "terminated": False,
    }
    runtime["running_batches"][batch_id] = batch_info

    _mark_batch_items_extracting(context, batch_items)
    APR_UPDATE_LOG.log_batch_submission(context, batch_id, len(batch_items))
    return True


def _build_batch_file_lines(context, batch_items):
    """
    Function Name: _build_batch_file_lines
    Purpose: Build one batch command file with the required module-load header and one timing extractor command per queued APR run.
    Input Params: context (dict), batch_items (list[dict])
    Output: batch_file_lines (list[str])
    """
    timing_script = os.path.abspath(str(context["runtime_paths"]["timing_script"]))
    batch_file_lines = [f"module load {_BATCH_PYTHON_MODULE}"]
    for batch_item in batch_items:
        batch_file_lines.append(
            " ".join(
                [
                    _BATCH_PYTHON_COMMAND,
                    shlex.quote(timing_script),
                    shlex.quote(context["project_code"]),
                    shlex.quote(batch_item["stage"]),
                    shlex.quote(batch_item["run_dir"]),
                ]
            )
        )
    return batch_file_lines


def _requeue_batch_items(runtime, batch_items):
    """
    Function Name: _requeue_batch_items
    Purpose: Put one batch's items back at the front of the pending queue after submission could not start.
    Input Params: runtime (dict), batch_items (list[dict])
    Output: outputs (None)
    """
    for batch_item in reversed(batch_items):
        batch_item["queued_at"] = time.time()
        runtime["pending_items"][batch_item["state_key"]] = batch_item
        runtime["pending_items"].move_to_end(batch_item["state_key"], last=False)


def _sync_batch_command_slots(context, runtime, max_parallel_batches, force_reset=False):
    """
    Function Name: _sync_batch_command_slots
    Purpose: Rebuild the managed batch-command files so `BATCH_COMMANDS` contains one slot file per configured parallel batch when it is safe to do so.
    Input Params: context (dict), runtime (dict), max_parallel_batches (int), force_reset (bool)
    Output: outputs (None)
    """
    batch_commands_dir = context.get("runtime_paths", {}).get("batch_commands_dir")
    if batch_commands_dir is None:
        return

    if runtime["running_batches"] and not force_reset:
        if runtime.get("configured_parallel_batch_count") == max_parallel_batches and runtime.get("batch_slots_initialized"):
            return
        return

    absolute_batch_commands_dir = Path(os.path.abspath(str(batch_commands_dir)))
    managed_batch_file_count = len(list(absolute_batch_commands_dir.glob("BATCH_COMMAND_*.txt")))
    if (
        not force_reset
        and runtime.get("configured_parallel_batch_count") == max_parallel_batches
        and runtime.get("batch_slots_initialized")
        and managed_batch_file_count == max_parallel_batches
    ):
        return

    _reset_batch_command_files(absolute_batch_commands_dir, max_parallel_batches)
    runtime["available_batch_slots"] = list(range(1, max_parallel_batches + 1))
    runtime["batch_slots_initialized"] = True
    runtime["configured_parallel_batch_count"] = max_parallel_batches


def _reset_batch_command_files(batch_commands_dir, max_parallel_batches):
    """
    Function Name: _reset_batch_command_files
    Purpose: Delete managed batch-command files and recreate exactly one command file per configured parallel batch slot.
    Input Params: batch_commands_dir (str | os.PathLike), max_parallel_batches (int)
    Output: outputs (None)
    """
    absolute_batch_commands_dir = Path(os.path.abspath(str(batch_commands_dir)))
    absolute_batch_commands_dir.mkdir(parents=True, exist_ok=True)

    for existing_batch_file in absolute_batch_commands_dir.glob("BATCH_COMMAND_*.txt"):
        try:
            existing_batch_file.unlink()
        except FileNotFoundError:
            pass

    for slot_index in range(1, max_parallel_batches + 1):
        _write_batch_file(
            _get_batch_command_file_path(absolute_batch_commands_dir, slot_index),
            [f"module load {_BATCH_PYTHON_MODULE}"],
        )


def _claim_batch_slot(context, runtime, max_parallel_batches):
    """
    Function Name: _claim_batch_slot
    Purpose: Reserve one available batch-command slot file for a new APR batch submission.
    Input Params: context (dict), runtime (dict), max_parallel_batches (int)
    Output: slot_index (int | None)
    """
    _sync_batch_command_slots(context, runtime, max_parallel_batches)
    if not runtime["available_batch_slots"]:
        return None
    return runtime["available_batch_slots"].pop(0)


def _release_batch_slot(runtime, slot_index):
    """
    Function Name: _release_batch_slot
    Purpose: Return one batch-command slot file back to the available pool after its batch finishes or fails to submit.
    Input Params: runtime (dict), slot_index (int | None)
    Output: outputs (None)
    """
    if slot_index is None:
        return
    if slot_index in runtime["available_batch_slots"]:
        return
    runtime["available_batch_slots"].append(slot_index)
    runtime["available_batch_slots"].sort()


def _get_batch_command_file_path(batch_commands_dir, slot_index):
    """
    Function Name: _get_batch_command_file_path
    Purpose: Build the absolute managed command-file path for one parallel APR batch slot.
    Input Params: batch_commands_dir (str | os.PathLike), slot_index (int)
    Output: batch_file_path (str)
    """
    absolute_batch_commands_dir = Path(os.path.abspath(str(batch_commands_dir)))
    return str(absolute_batch_commands_dir / f"BATCH_COMMAND_{slot_index}.txt")


def _write_batch_file(batch_file_path, batch_file_lines):
    """
    Function Name: _write_batch_file
    Purpose: Atomically rewrite one managed APR batch-command file before its matching batch is submitted through utilq.
    Input Params: batch_file_path (str), batch_file_lines (list[str])
    Output: outputs (None)
    """
    absolute_batch_file_path = Path(os.path.abspath(str(batch_file_path)))
    absolute_batch_file_path.parent.mkdir(parents=True, exist_ok=True)
    temp_batch_file_path = absolute_batch_file_path.with_name(f"{absolute_batch_file_path.name}.tmp")
    with open(temp_batch_file_path, "w", encoding="utf-8", newline="\n") as output_file:
        output_file.write("\n".join(batch_file_lines).rstrip())
        output_file.write("\n")
        output_file.flush()
        os.fsync(output_file.fileno())
    os.replace(temp_batch_file_path, absolute_batch_file_path)


def _build_batch_command(batch_file_path):
    """
    Function Name: _build_batch_command
    Purpose: Build the APR batch shell command that submits one prepared slot command file through utilq.
    Input Params: batch_file_path (str)
    Output: command_text (str)
    """
    return f"utilq -Is source {shlex.quote(os.path.abspath(str(batch_file_path)))}"


def _spawn_batch_process(command_text):
    """
    Function Name: _spawn_batch_process
    Purpose: Spawn the APR batch subprocess that runs the chained extractor command string.
    Input Params: command_text (str)
    Output: process (subprocess.Popen)
    """
    kwargs = {
        "stderr": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
    }
    if os.name == "nt":
        kwargs["shell"] = True
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        return subprocess.Popen(command_text, **kwargs)

    shell_path = "/bin/bash" if os.path.exists("/bin/bash") else os.environ.get("SHELL", "/bin/sh")
    kwargs["start_new_session"] = True
    return subprocess.Popen([shell_path, "-lc", command_text], **kwargs)


def _mark_batch_items_extracting(context, batch_items):
    """
    Function Name: _mark_batch_items_extracting
    Purpose: Update persisted APR state for each item that has just been submitted into a running batch.
    Input Params: context (dict), batch_items (list[dict])
    Output: outputs (None)
    """
    state = context["state"]
    state_extracting = APR_VARS.get_setting("STATE_EXTRACTING")
    for batch_item in batch_items:
        state_entry = dict(state.get(batch_item["state_key"], {}))
        state_entry.setdefault("Created", APR_VARS.now_str())
        state_entry["Force_extract"] = 0
        state_entry["Last_status"] = state_extracting
        state[batch_item["state_key"]] = state_entry
        _push_batch_item_tracker_state(context, batch_item, state_entry)
    context["state_dirty"] = True


def _mark_file_item_invalid(context, file_item, error_code):
    """
    Function Name: _mark_file_item_invalid
    Purpose: Persist the APR tracker/state outcome for one run that failed pre-submit validation and must not enter extraction.
    Input Params: context (dict), file_item (dict), error_code (str)
    Output: outputs (None)
    """
    status_by_error = {
        "ERR001": APR_VARS.get_setting("STATE_FAILED"),
        "ERR002": APR_VARS.get_setting("STATE_FAILED"),
        "ERR003": APR_VARS.get_setting("STATE_EXTRACT_FAILED"),
    }
    status = status_by_error.get(error_code, APR_VARS.get_setting("STATE_FAILED"))
    completed_at = APR_VARS.now_str()

    file_item["tracker_record"]["Comments"] = error_code
    file_item["tracker_record"]["Promote"] = "no"
    file_item["tracker_record"]["Status"] = status

    file_item["state_entry"].setdefault("Created", completed_at)
    file_item["state_entry"]["Force_extract"] = 0
    file_item["state_entry"]["Last_extract_finished_at"] = completed_at
    file_item["state_entry"]["Last_extract_result"] = f"{_VALIDATION_RESULT_PREFIX}{error_code}"
    file_item["state_entry"]["Last_status"] = status
    file_item["state_changed"] = True
    context["state_dirty"] = True


def _mark_file_item_extracting(context, file_item):
    """
    Function Name: _mark_file_item_extracting
    Purpose: Reflect the in-flight extracting status in the current monitor item after it joins a running batch.
    Input Params: context (dict), file_item (dict)
    Output: outputs (None)
    """
    state_extracting = APR_VARS.get_setting("STATE_EXTRACTING")
    file_item["tracker_record"]["Status"] = state_extracting
    file_item["state_entry"]["Force_extract"] = 0
    file_item["state_entry"]["Last_status"] = state_extracting
    file_item["state_changed"] = True
    context["state_dirty"] = True


def _remove_force_extract_request(context, state_key):
    """
    Function Name: _remove_force_extract_request
    Purpose: Drop one APR force-extract request after it was rejected during pre-submit validation so it is not retried every cycle.
    Input Params: context (dict), state_key (str)
    Output: outputs (None)
    """
    payload = context.get("force_extract_payload")
    if not isinstance(payload, dict):
        return

    items_key = APR_VARS.get_setting("FORCE_EXTRACT_JSON_ITEMS_KEY")
    items = payload.get(items_key)
    if not isinstance(items, list):
        return

    filtered_items = []
    changed = False
    for item in items:
        item_state_key = APR_VARS.make_state_key(
            str(item.get("job", item.get("Job", "")) or "").strip(),
            str(item.get("milestone", item.get("Milestone", "")) or "").strip(),
            str(item.get("block", item.get("Block", "")) or "").strip(),
            str(item.get("stage", item.get("Stage", "")) or "").strip(),
        )
        if item_state_key == state_key:
            changed = True
            continue
        filtered_items.append(item)

    if changed:
        payload[items_key] = filtered_items
        context["force_extract_dirty"] = True


def _remove_pending_item(context, state_key):
    """
    Function Name: _remove_pending_item
    Purpose: Drop one APR run from the pending batch queue after pre-submit validation fails.
    Input Params: context (dict), state_key (str)
    Output: outputs (None)
    """
    _get_runtime(context)["pending_items"].pop(state_key, None)


def _push_batch_item_tracker_state(context, batch_item, state_entry):
    """
    Function Name: _push_batch_item_tracker_state
    Purpose: Submit one batch-owned tracker row immediately so queued, extracting, completed, and retry states show up without waiting for another file scan pass.
    Input Params: context (dict), batch_item (dict), state_entry (dict)
    Output: outputs (None)
    """
    writer = context.get("writer")
    if writer is None:
        return

    from Backend.Monitor.APR.MONITORING import APR_ITEM_STATUS, APR_UPDATE_TRACKER

    writer.check()
    tracker_record = APR_ITEM_STATUS.build_record(
        batch_item["log_path"],
        state_entry.get("Created", APR_VARS.now_str()),
        batch_item.get("log_meta"),
        APR_ITEM_STATUS.get_file_info(batch_item["log_path"]),
    )
    tracker_record["Rerun"] = int(state_entry.get("Rerun", 0) or 0)
    tracker_record["Status"] = state_entry.get("Last_status", APR_VARS.get_setting("STATE_AWAIT"))
    writer.submit_tracker(APR_UPDATE_TRACKER.apply_kpi_status(tracker_record, batch_item["log_path"], state_entry))


def _finalize_ready_batch_items(context, state, batch_info):
    """
    Function Name: _finalize_ready_batch_items
    Purpose: Promote any still-running batch items to completed as soon as their timing databases exist, without waiting for the whole batch process to exit.
    Input Params: context (dict), state (dict), batch_info (dict)
    Output: result (dict)
    """
    ready_items = []
    remaining_items = []
    for batch_item in batch_info["items"]:
        if _db_was_written_after_submit(batch_item["timing_db_path"], batch_info["submitted_at"]):
            ready_items.append(batch_item)
        else:
            remaining_items.append(batch_item)

    if not ready_items:
        return {
            "completed_force_keys": set(),
            "state_dirty": False,
        }

    completed_at = APR_VARS.now_str()
    completed_force_keys = set()
    for batch_item in ready_items:
        state_entry = _set_success_state(state, batch_item, completed_at)
        _push_batch_item_tracker_state(context, batch_item, state_entry)
        completed_force_keys.add(batch_item["state_key"])

    batch_info["items"] = remaining_items
    batch_info["state_keys"] = {batch_item["state_key"] for batch_item in remaining_items}
    batch_info["success_count"] = int(batch_info.get("success_count", 0)) + len(ready_items)
    return {
        "completed_force_keys": completed_force_keys,
        "state_dirty": True,
    }


def _finalize_batch(context, state, batch_info, return_code):
    """
    Function Name: _finalize_batch
    Purpose: Translate a finished APR batch result into success, failure, and retry state updates.
    Input Params: context (dict), state (dict), batch_info (dict), return_code (int)
    Output: result (dict)
    """
    completed_at = APR_VARS.now_str()
    success_items, failed_item, retry_items = _classify_batch_items(batch_info, return_code)
    completed_force_keys = set()
    state_dirty = False

    for batch_item in success_items:
        state_entry = _set_success_state(state, batch_item, completed_at)
        _push_batch_item_tracker_state(context, batch_item, state_entry)
        completed_force_keys.add(batch_item["state_key"])
        state_dirty = True

    if failed_item is not None:
        state_entry = _set_failure_state(state, failed_item, completed_at, return_code)
        _push_batch_item_tracker_state(context, failed_item, state_entry)
        completed_force_keys.add(failed_item["state_key"])
        state_dirty = True

    for batch_item in retry_items:
        state_entry = _set_await_state(state, batch_item, "retry")
        _push_batch_item_tracker_state(context, batch_item, state_entry)
        state_dirty = True

    success_count = int(batch_info.get("success_count", 0)) + len(success_items)
    failed_count = max(0, int(batch_info.get("item_count", len(batch_info["items"]))) - success_count)
    return {
        "completed_force_keys": completed_force_keys,
        "failed_count": failed_count,
        "state_dirty": state_dirty,
        "success_count": success_count,
    }


def _classify_batch_items(batch_info, return_code):
    """
    Function Name: _classify_batch_items
    Purpose: Decide which APR runs in a finished batch succeeded, which failed first, and which should be retried.
    Input Params: batch_info (dict), return_code (int)
    Output: classification (tuple[list[dict], dict | None, list[dict]])
    """
    success_items = []
    failed_item = None
    retry_items = []

    if return_code == 0:
        for batch_item in batch_info["items"]:
            if _db_was_written_after_submit(batch_item["timing_db_path"], batch_info["submitted_at"]):
                success_items.append(batch_item)
            elif failed_item is None:
                failed_item = batch_item
            else:
                retry_items.append(batch_item)
        return success_items, failed_item, retry_items

    first_missing_index = None
    for index, batch_item in enumerate(batch_info["items"]):
        if _db_was_written_after_submit(batch_item["timing_db_path"], batch_info["submitted_at"]):
            if first_missing_index is None:
                success_items.append(batch_item)
            continue
        first_missing_index = index
        break

    if first_missing_index is None:
        first_missing_index = len(success_items)

    if first_missing_index < len(batch_info["items"]):
        failed_item = batch_info["items"][first_missing_index]
        retry_items = batch_info["items"][first_missing_index + 1 :]

    return success_items, failed_item, retry_items


def _db_was_written_after_submit(db_path, submitted_at):
    """
    Function Name: _db_was_written_after_submit
    Purpose: Check whether the expected APR timing database file was written after the batch started.
    Input Params: db_path (str), submitted_at (float)
    Output: was_written (bool)
    """
    absolute_db_path = os.path.abspath(db_path)
    try:
        return os.path.exists(absolute_db_path) and os.path.getmtime(absolute_db_path) >= submitted_at
    except OSError:
        return False


def _set_success_state(state, batch_item, completed_at):
    """
    Function Name: _set_success_state
    Purpose: Persist the success state for one APR run after its batch extraction completed successfully.
    Input Params: state (dict), batch_item (dict), completed_at (str)
    Output: outputs (None)
    """
    state_done = APR_VARS.get_setting("STATE_DONE")
    state_entry = dict(state.get(batch_item["state_key"], {}))
    state_entry.setdefault("Created", APR_VARS.now_str())
    state_entry["Force_extract"] = 0
    state_entry["Last_extract_finished_at"] = completed_at
    state_entry["Last_extract_result"] = "success"
    state_entry["Last_extracted_mtime"] = batch_item["log_mtime"]
    state_entry["Last_status"] = state_done
    state[batch_item["state_key"]] = state_entry
    return state_entry


def _set_failure_state(state, batch_item, completed_at, return_code):
    """
    Function Name: _set_failure_state
    Purpose: Persist the extraction-failed state for the first APR run that failed in a finished batch.
    Input Params: state (dict), batch_item (dict), completed_at (str), return_code (int)
    Output: outputs (None)
    """
    state_entry = dict(state.get(batch_item["state_key"], {}))
    state_entry.setdefault("Created", APR_VARS.now_str())
    state_entry["Force_extract"] = 0
    state_entry["Last_extract_finished_at"] = completed_at
    state_entry["Last_extract_result"] = f"batch_failed:{return_code}"
    state_entry["Last_status"] = APR_VARS.get_setting("STATE_EXTRACT_FAILED")
    state[batch_item["state_key"]] = state_entry
    return state_entry


def _set_await_state(state, batch_item, reason):
    """
    Function Name: _set_await_state
    Purpose: Reset one APR run back to the await state so it can be retried after shutdown or retry classification.
    Input Params: state (dict), batch_item (dict), reason (str)
    Output: outputs (None)
    """
    state_entry = dict(state.get(batch_item["state_key"], {}))
    state_entry.setdefault("Created", APR_VARS.now_str())
    state_entry["Force_extract"] = 1
    state_entry["Last_extract_result"] = reason
    state_entry["Last_status"] = APR_VARS.get_setting("STATE_AWAIT")
    state[batch_item["state_key"]] = state_entry
    return state_entry


def _terminate_batch_process(process):
    """
    Function Name: _terminate_batch_process
    Purpose: Stop one APR batch subprocess as cleanly as possible and force-kill it if needed.
    Input Params: process (subprocess.Popen | None)
    Output: outputs (None)
    """
    if process is None or process.poll() is not None:
        return

    try:
        if os.name == "nt":
            root_process = psutil.Process(process.pid)
            child_processes = root_process.children(recursive=True)
            for child_process in child_processes:
                try:
                    child_process.terminate()
                except Exception:
                    pass
            try:
                root_process.terminate()
            except Exception:
                pass

            _, alive_processes = psutil.wait_procs([root_process, *child_processes], timeout=3)
            for alive_process in alive_processes:
                try:
                    alive_process.kill()
                except Exception:
                    pass
        else:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            process.wait(timeout=3)
    except Exception:
        try:
            if os.name == "nt":
                process.kill()
            else:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except Exception:
            pass
