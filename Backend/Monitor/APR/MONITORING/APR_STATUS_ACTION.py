from collections import OrderedDict
import os
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path

import APR_VARS
import Backend.Monitor.APR.MONITORING.APR_SLEEP as APR_SLEEP
from Backend.Monitor.APR.MONITORING import APR_UPDATE_LOG


_BATCH_RUNTIMES = {}


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
        return_code = batch_info["process"].poll()
        if return_code is None:
            continue

        runtime["running_batches"].pop(batch_id, None)
        result = _finalize_batch(state, batch_info, return_code)
        state_dirty = state_dirty or result["state_dirty"]
        completed_force_keys.update(result["completed_force_keys"])
        APR_UPDATE_LOG.log_batch_completion(
            context,
            batch_id,
            len(batch_info["items"]),
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
            _set_await_state(state, batch_item, "terminated")
            state_dirty = True

    for batch_item in list(runtime["pending_items"].values()):
        _set_await_state(state, batch_item, "pending")
        state_dirty = True

    runtime["running_batches"].clear()
    runtime["pending_items"].clear()
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
    return str(project_root / log_meta["Block"] / log_meta["Milestone"] / log_meta["Job"] / f"{log_meta['Stage']}.db")


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

    while len(runtime["running_batches"]) < max_parallel_batches:
        pending_count = len(runtime["pending_items"])
        if pending_count == 0:
            return

        if pending_count >= batch_size:
            item_count = batch_size
        elif runtime["running_batches"]:
            return
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

    command_text = _build_batch_command(context, batch_items)
    submitted_at = time.time()
    try:
        process = _spawn_batch_process(command_text)
    except Exception:
        for batch_item in reversed(batch_items):
            batch_item["queued_at"] = time.time()
            runtime["pending_items"][batch_item["state_key"]] = batch_item
        APR_UPDATE_LOG.log_batch_completion(context, batch_id, len(batch_items), 0, len(batch_items))
        return False

    batch_info = {
        "batch_id": batch_id,
        "command_text": command_text,
        "items": batch_items,
        "process": process,
        "state_keys": {batch_item["state_key"] for batch_item in batch_items},
        "submitted_at": submitted_at,
        "terminated": False,
    }
    runtime["running_batches"][batch_id] = batch_info

    _mark_batch_items_extracting(context, batch_items)
    APR_UPDATE_LOG.log_batch_submission(context, batch_id, len(batch_items))
    return True


def _build_batch_command(context, batch_items):
    """
    Function Name: _build_batch_command
    Purpose: Build the APR batch shell command in the required utilq plus chained extractor-command format.
    Input Params: context (dict), batch_items (list[dict])
    Output: command_text (str)
    """
    timing_script = os.path.abspath(str(context["runtime_paths"]["timing_script"]))
    command_parts = []
    for batch_item in batch_items:
        command_parts.append(
            " ".join(
                [
                    shlex.quote(sys.executable),
                    shlex.quote(timing_script),
                    shlex.quote(context["project_code"]),
                    shlex.quote(batch_item["stage"]),
                    shlex.quote(batch_item["run_dir"]),
                ]
            )
        )
    return "utilq -Is && " + " && ".join(command_parts)


def _spawn_batch_process(command_text):
    """
    Function Name: _spawn_batch_process
    Purpose: Spawn the APR batch subprocess that runs the chained extractor command string.
    Input Params: command_text (str)
    Output: process (subprocess.Popen)
    """
    kwargs = {
        "shell": True,
        "stderr": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
    }
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["executable"] = os.environ.get("SHELL", "/bin/bash")
        kwargs["start_new_session"] = True
    return subprocess.Popen(command_text, **kwargs)


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


def _finalize_batch(state, batch_info, return_code):
    """
    Function Name: _finalize_batch
    Purpose: Translate a finished APR batch result into success, failure, and retry state updates.
    Input Params: state (dict), batch_info (dict), return_code (int)
    Output: result (dict)
    """
    completed_at = APR_VARS.now_str()
    success_items, failed_item, retry_items = _classify_batch_items(batch_info, return_code)
    completed_force_keys = set()
    state_dirty = False

    for batch_item in success_items:
        _set_success_state(state, batch_item, completed_at)
        completed_force_keys.add(batch_item["state_key"])
        state_dirty = True

    if failed_item is not None:
        _set_failure_state(state, failed_item, completed_at, return_code)
        completed_force_keys.add(failed_item["state_key"])
        state_dirty = True

    for batch_item in retry_items:
        _set_await_state(state, batch_item, "retry")
        state_dirty = True

    success_count = len(success_items)
    failed_count = len(batch_info["items"]) - success_count
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
            process.terminate()
            process.wait(timeout=3)
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
