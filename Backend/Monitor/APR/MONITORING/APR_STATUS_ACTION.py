import os
import shlex
import subprocess
import uuid
from pathlib import Path

from Backend.Monitor.APR import APR_VARS
import Backend.Monitor.APR.MONITORING.APR_SLEEP as APR_SLEEP
from Backend.Monitor.APR.EXTRACTORS.APR_TIMING_INNOVUS import get_timing_db_path as build_timing_db_path
from Backend.Monitor.APR.MONITORING import APR_FLOW_CONTEXT
from Backend.Monitor.APR.MONITORING import APR_ITEM_STATUS


_BATCH_RUNTIMES = {}


def _get_runtime(context):
    """
    Function Name: _get_runtime
    Purpose: Return the lightweight in-memory APR batch runtime for one project code.
    Input Params: context (dict)
    Output: runtime (dict)
    """
    project_code = APR_FLOW_CONTEXT.get_project_code(context)
    runtime = _BATCH_RUNTIMES.get(project_code)
    if runtime is None:
        runtime = {
            "pending": {},
            "running": {},
        }
        _BATCH_RUNTIMES[project_code] = runtime
    return runtime


def _is_running_state_key(runtime, state_key):
    """
    Function Name: _is_running_state_key
    Purpose: Check whether one APR state key is already part of a submitted batch.
    Input Params: runtime (dict), state_key (str)
    Output: is_running (bool)
    """
    return any(
        state_key == batch_item["state_key"]
        for batch_info in runtime["running"].values()
        for batch_item in batch_info["items"]
    )


def _cleanup_batch_file(batch_file_path):
    """
    Function Name: _cleanup_batch_file
    Purpose: Delete one generated APR batch command file after the matching subprocess no longer needs it.
    Input Params: batch_file_path (str)
    Output: outputs (None)
    """
    try:
        Path(os.path.abspath(batch_file_path)).unlink()
    except FileNotFoundError:
        pass


def _get_timing_db_path(project_code, batch_item):
    """
    Function Name: _get_timing_db_path
    Purpose: Build the expected timing database path for one queued or running APR batch item.
    Input Params: project_code (str), batch_item (dict)
    Output: timing_db_path (str)
    """
    log_meta = {
        "Block": batch_item["block"],
        "Job": batch_item["job"],
        "Milestone": batch_item["milestone"],
        "Stage": batch_item["stage"],
    }
    return build_timing_db_path(project_code, log_meta)


def _get_source_db_path(batch_item):
    """
    Function Name: _get_source_db_path
    Purpose: Build the expected source-dbinfo path for one queued or running APR batch item.
    Input Params: batch_item (dict)
    Output: source_db_path (str)
    """
    return os.path.abspath(
        os.path.join(
            batch_item["run_directory"],
            "dbs",
            f"{batch_item['stage']}_final",
            f"{batch_item['job']}.dat",
            f"{batch_item['job']}.dbinfo",
        )
    )


def _is_extract_completed(project_code, batch_item):
    """
    Function Name: _is_extract_completed
    Purpose: Check whether one batch item now has a newer timing database than its source database.
    Input Params: project_code (str), batch_item (dict)
    Output: extract_completed (bool)
    """
    source_db_path = _get_source_db_path(batch_item)
    timing_db_path = _get_timing_db_path(project_code, batch_item)
    if not os.path.exists(source_db_path) or not os.path.exists(timing_db_path):
        return False

    try:
        return int(os.path.getmtime(source_db_path)) < int(os.path.getmtime(timing_db_path))
    except OSError:
        return False


def _set_batch_items_extracting(context, batch_items):
    """
    Function Name: _set_batch_items_extracting
    Purpose: Persist the submitted APR items as Extracting immediately after their batch starts.
    Input Params: context (dict), batch_items (list[dict])
    Output: outputs (None)
    """
    submitted_at = APR_VARS.now_str()
    for batch_item in batch_items:
        state_entry = dict(context["state"].get(batch_item["state_key"], {}))
        state_entry["Status"] = APR_VARS.get_setting("STATE_EXTRACTING")
        state_entry["Comments"] = "-"
        state_entry["Last_Extract_Submission"] = submitted_at
        state_entry["Extract_Completed"] = False
        state_entry["Rerun"] = max(0, int(state_entry.get("Rerun", 0) or 0))
        context["state"][batch_item["state_key"]] = state_entry
    APR_FLOW_CONTEXT.save_state(context)


def _sync_tracker_rows(context, batch_items):
    """
    Function Name: _sync_tracker_rows
    Purpose: Push the latest tracker rows for one batch item list so submitted runs show Extracting immediately.
    Input Params: context (dict), batch_items (list[dict])
    Output: outputs (None)
    """
    writer = context["db_writer"]
    writer.check()
    for batch_item in batch_items:
        log_path = batch_item["log_path"]
        state_entry = context["state"].get(batch_item["state_key"], {})
        tracker_record = APR_ITEM_STATUS.build_tracker_record(log_path, state_entry)
        writer.submit_tracker(tracker_record)


def _mark_current_item_extracting(context, file_item):
    """
    Function Name: _mark_current_item_extracting
    Purpose: Update the current monitor item's in-flight state so UPDATE_DB writes Extracting for the item being processed now.
    Input Params: context (dict), file_item (dict)
    Output: outputs (None)
    """
    state_entry = dict(context["state"].get(file_item["state_key"], file_item["state_entry"]))
    file_item["state_entry"] = state_entry
    file_item["state_changed"] = True
    file_item["tracker_record"]["Status"] = state_entry["Status"]
    file_item["tracker_record"]["Comments"] = state_entry["Comments"]
    file_item["tracker_record"]["Created"] = state_entry.get("Last_Extract_Submission") or ""
    file_item["tracker_record"]["Promote"] = "no"


def _build_batch_item(file_item):
    """
    Function Name: _build_batch_item
    Purpose: Build the minimal APR batch item payload required for queueing, submission, and completion checks.
    Input Params: file_item (dict)
    Output: batch_item (dict)
    """
    log_meta = file_item["log_meta"]
    return {
        "block": log_meta["Block"],
        "job": log_meta["Job"],
        "log_path": os.path.abspath(file_item["log_path"]),
        "milestone": log_meta["Milestone"],
        "run_directory": os.path.abspath(file_item["run_directory"]),
        "stage": log_meta["Stage"],
        "state_key": file_item["state_key"],
    }


def _write_batch_file(batch_file_path, batch_file_lines):
    """
    Function Name: _write_batch_file
    Purpose: Atomically write one generated APR batch command file before submitting it through utilq.
    Input Params: batch_file_path (str), batch_file_lines (list[str])
    Output: outputs (None)
    """
    absolute_batch_file_path = Path(os.path.abspath(batch_file_path))
    absolute_batch_file_path.parent.mkdir(parents=True, exist_ok=True)
    temp_batch_file_path = absolute_batch_file_path.with_suffix(f"{absolute_batch_file_path.suffix}.tmp")
    with open(temp_batch_file_path, "w", encoding="utf-8", newline="\n") as output_file:
        output_file.write("\n".join(batch_file_lines).rstrip())
        output_file.write("\n")
        output_file.flush()
        os.fsync(output_file.fileno())
    os.replace(temp_batch_file_path, absolute_batch_file_path)


def _build_batch_file_lines(project_code, batch_items):
    """
    Function Name: _build_batch_file_lines
    Purpose: Build the APR batch command file content for one submitted batch.
    Input Params: project_code (str), batch_items (list[dict])
    Output: batch_file_lines (list[str])
    """
    timing_script_path = APR_VARS.get_timing_script_path()
    batch_file_lines = [f"module load {APR_VARS.get_setting('BATCH_PYTHON_MODULE')}"]
    for batch_item in batch_items:
        batch_file_lines.append(
            " ".join(
                [
                    APR_VARS.get_setting("BATCH_PYTHON_COMMAND"),
                    shlex.quote(timing_script_path),
                    shlex.quote(project_code),
                    shlex.quote(batch_item["stage"]),
                    shlex.quote(batch_item["run_directory"]),
                ]
            )
        )
    return batch_file_lines


def _build_batch_command(batch_file_path):
    """
    Function Name: _build_batch_command
    Purpose: Build the utilq command used to source one generated APR batch command file.
    Input Params: batch_file_path (str)
    Output: command_parts (list[str])
    """
    return ["utilq", "-Is", "source", os.path.abspath(batch_file_path)]


def _spawn_batch_process(project_code, command_parts):
    """
    Function Name: _spawn_batch_process
    Purpose: Spawn the APR batch submit subprocess with the matching LSF default project.
    Input Params: project_code (str), command_parts (list[str])
    Output: process (subprocess.Popen)
    """
    process_env = os.environ.copy()
    process_env["LSB_DEFAULTPROJECT"] = str(project_code or "").replace("dthpcadm_", "")
    kwargs = {
        "env": process_env,
        "stderr": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
    }
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        return subprocess.Popen(command_parts, **kwargs)

    kwargs["start_new_session"] = True
    return subprocess.Popen(command_parts, **kwargs)


def _prepend_pending_items(runtime, batch_items):
    """
    Function Name: _prepend_pending_items
    Purpose: Put batch items back at the front of the pending queue when submission fails.
    Input Params: runtime (dict), batch_items (list[dict])
    Output: outputs (None)
    """
    preserved_pending = dict(runtime["pending"])
    runtime["pending"] = {batch_item["state_key"]: batch_item for batch_item in batch_items}
    runtime["pending"].update(preserved_pending)


def _submit_batch(context, runtime, batch_items):
    """
    Function Name: _submit_batch
    Purpose: Create one dynamic APR batch command file, submit it, and move the matching items into the running-batch set.
    Input Params: context (dict), runtime (dict), batch_items (list[dict])
    Output: submitted (bool)
    """
    project_code = APR_FLOW_CONTEXT.get_project_code(context)
    batch_id = uuid.uuid4().hex
    batch_file_path = os.path.abspath(
        os.path.join(
            APR_VARS.get_batch_commands_dir(),
            f"{APR_VARS.get_setting('BATCH_COMMAND_PREFIX')}_{batch_id}.txt",
        )
    )
    command_parts = _build_batch_command(batch_file_path)
    try:
        _write_batch_file(batch_file_path, _build_batch_file_lines(project_code, batch_items))
        process = _spawn_batch_process(project_code, command_parts)
    except Exception as exc:
        _cleanup_batch_file(batch_file_path)
        _prepend_pending_items(runtime, batch_items)
        APR_FLOW_CONTEXT.append_log(context, f"batch_submit_failed | batch_id={batch_id} | error={exc}")
        return False

    runtime["running"][batch_id] = {
        "batch_file_path": batch_file_path,
        "items": batch_items,
        "process": process,
    }
    _set_batch_items_extracting(context, batch_items)
    _sync_tracker_rows(context, batch_items)
    APR_FLOW_CONTEXT.append_log(
        context,
        f"batch_submitted | batch_id={batch_id} | items={len(batch_items)} | command={' '.join(command_parts)}",
    )
    return True


def _dispatch_batches(context, runtime):
    """
    Function Name: _dispatch_batches
    Purpose: Launch new APR batch subprocesses while pending work exists and the configured parallel limit allows it.
    Input Params: context (dict), runtime (dict)
    Output: outputs (None)
    """
    batch_size = max(1, int(APR_VARS.get_setting("BATCH_SIZE")))
    max_parallel_batches = max(1, int(APR_VARS.get_setting("MAX_PARALLEL_BATCHES")))
    while runtime["pending"] and len(runtime["running"]) < max_parallel_batches:
        pending_state_keys = list(runtime["pending"].keys())[:batch_size]
        batch_items = [runtime["pending"].pop(state_key) for state_key in pending_state_keys]
        if not _submit_batch(context, runtime, batch_items):
            return


def refresh_batches(context):
    """
    Function Name: refresh_batches
    Purpose: Reconcile finished APR batch subprocesses, delete their generated batch files, clear the temporary Extracting state, and launch any next waiting batch.
    Input Params: context (dict)
    Output: outputs (None)
    """
    runtime = _get_runtime(context)
    project_code = APR_FLOW_CONTEXT.get_project_code(context)
    state_changed = False

    for batch_id, batch_info in list(runtime["running"].items()):
        return_code = batch_info["process"].poll()
        if return_code is None:
            continue

        runtime["running"].pop(batch_id, None)
        _cleanup_batch_file(batch_info["batch_file_path"])
        for batch_item in batch_info["items"]:
            state_entry = dict(context["state"].get(batch_item["state_key"], {}))
            state_entry["Status"] = None
            state_entry["Comments"] = None
            state_entry["Extract_Completed"] = _is_extract_completed(project_code, batch_item)
            state_entry["Rerun"] = max(0, int(state_entry.get("Rerun", 0) or 0))
            context["state"][batch_item["state_key"]] = state_entry
            state_changed = True

        APR_FLOW_CONTEXT.append_log(
            context,
            f"batch_completed | batch_id={batch_id} | items={len(batch_info['items'])} | return_code={return_code}",
        )

    if state_changed:
        APR_FLOW_CONTEXT.save_state(context)

    _dispatch_batches(context, runtime)


def perform_status_action(context, file_item):
    """
    Function Name: perform_status_action
    Purpose: Queue APR items that are waiting for extraction and mark them Extracting once they join a submitted batch.
    Input Params: context (dict), file_item (dict)
    Output: outputs (None)
    """
    refresh_batches(context)
    if APR_SLEEP.should_exit(context):
        return
    if file_item["state_entry"]["Status"] != APR_VARS.get_setting("STATE_AWAIT"):
        return

    runtime = _get_runtime(context)
    state_key = file_item["state_key"]
    if _is_running_state_key(runtime, state_key):
        _mark_current_item_extracting(context, file_item)
        return

    if state_key not in runtime["pending"]:
        runtime["pending"][state_key] = _build_batch_item(file_item)

    _dispatch_batches(context, runtime)
    if _is_running_state_key(runtime, state_key):
        _mark_current_item_extracting(context, file_item)
