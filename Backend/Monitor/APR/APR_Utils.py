import csv
import json
import os
import pwd
import signal
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor

import APR_DB_Operations
import TIMING
from APR_Definitions import (
    DEFAULT_FLOW,
    DEFAULT_MAXDEPTH,
    DEFAULT_MINDEPTH,
    DEFAULT_TOOL,
    FORCE_EXTRACT_FILE_NAME,
    KPI_COLUMNS,
    LOG_DIR,
    MAX_ACTIVE_WORKERS,
    POLL_SECONDS,
    STAGES,
    STATE_AWAIT,
    STATE_DIR,
    STATE_DONE,
    STATE_ENTRY_FIELDS,
    STATE_EXTRACT_FAILED,
    STATE_EXTRACTING,
    STATE_FAILED,
    STATE_FILE_NAME,
    STATE_RUNNING,
    now_str,
    make_state_key,
    today_log_file,
)


STOP_REQUESTED = {"value": False}


def parse_log_args(filename):
    parts = os.path.abspath(filename).strip("/").split("/")
    job = parts[-3]
    milestone = parts[4] if len(parts) > 4 else ""
    block = parts[5] if len(parts) > 5 else ""
    stage = os.path.splitext(os.path.basename(filename))[0]
    dft_release = "NA"
    try:
        cmd = f"find {os.path.dirname(filename)}/../../inputs/dft/vlog/*dft.v | xargs -Ixx realpath xx"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=False)
        out = result.stdout.strip()
        if out and "/iExchange/DFT" in out:
            dft_release = out.split("/")[-3]
    except Exception:
        pass
    return {
        "Job": job,
        "Milestone": milestone,
        "Block": block,
        "Stage": stage,
        "Dft_release": dft_release,
        "State_key": make_state_key(job, milestone, block, stage),
    }


def extract_apr_kpi(path):
    try:
        args = parse_log_args(path)
        rptfile = os.path.join(os.path.dirname(os.path.dirname(path)), f"reports/{args['Stage']}.final.kpi.rpt")
        values = []
        with open(rptfile, "r", encoding="utf-8") as infile:
            reader = csv.reader(infile, delimiter="|")
            for index, row in enumerate(reader):
                if index < 2 or len(row) <= 1:
                    continue
                cols = [item.strip() for item in row[1:-1]]
                values.append(cols[-1] if cols else "")
        return {col: (values[i] if i < len(values) else "") for i, col in enumerate(KPI_COLUMNS)}
    except Exception:
        return {col: "" for col in KPI_COLUMNS}


def get_timing_db_path(file_path, project_code, meta=None):
    return os.path.join(
        "/proj",
        project_code,
        "DashAI",
        "DashAI_APR.db",
    )


def get_timing_db_mtime(file_path, project_code, meta=None):
    return APR_DB_Operations.get_timing_stage_mtime(
        get_timing_db_path(file_path, project_code, meta=meta),
        meta or parse_log_args(file_path),
    )


def get_run_directories(basepath, mindepth=DEFAULT_MINDEPTH, maxdepth=DEFAULT_MAXDEPTH, flow=DEFAULT_FLOW, tool=DEFAULT_TOOL):
    cmd = f'find {basepath} -mindepth {mindepth} -maxdepth {maxdepth} -type d -wholename "*/{flow}/{tool}/*"'
    result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def get_log_paths(basepath):
    paths = set()
    for rundir in get_run_directories(basepath):
        for stage in STAGES:
            path = os.path.join(rundir, "logs", f"{stage}.log")
            if os.path.exists(path):
                paths.add(os.path.abspath(path))
    return sorted(paths)


def get_file_info(file_path):
    st = os.stat(file_path)
    try:
        user = pwd.getpwuid(st.st_uid).pw_name
    except Exception:
        user = str(st.st_uid)
    return {
        "User": user,
        "Modified": time.strftime("%Y%m%d %H:%M:%S", time.localtime(st.st_mtime)),
        "mtime": int(st.st_mtime),
        "size": int(st.st_size),
    }


def build_record(log_path, created, meta=None, info=None):
    meta = meta or parse_log_args(log_path)
    info = info or get_file_info(log_path)
    rec = {
        "Job": meta["Job"],
        "Milestone": meta["Milestone"],
        "Block": meta["Block"],
        "Stage": meta["Stage"],
        "Dft_release": meta["Dft_release"],
        "User": info["User"],
        "Created": created,
        "Modified": info["Modified"],
        "Rerun": 0,
        "Status": "",
        "Comments": "-",
        "Promote": "no",
    }
    rec.update({col: "" for col in KPI_COLUMNS})
    return rec


def db_exists_for_stage(file_path):
    meta = parse_log_args(file_path)
    stage = meta["Stage"]
    job = meta["Job"]
    db_path = file_path.replace(f"/logs/{stage}.log", f"/dbs/{stage}_final/{job}.dat/{job}.dbinfo")
    return os.path.exists(db_path)


def compute_status(state, log_path, mtime, size, is_extracting, timing_db_mtime=None):
    now_epoch = int(time.time())
    last_seen_mtime = state.get("Last_seen_mtime")
    last_seen_size = state.get("Last_seen_size")
    last_change_time = state.get("Last_change_time")
    last_extracted_mtime = state.get("Last_extracted_mtime")
    last_status = state.get("Last_status")
    rerun = int(state.get("Rerun", 0) or 0)
    force_extract = int(state.get("Force_extract", 0) or 0)
    file_changed = last_seen_mtime is None or mtime != last_seen_mtime or size != last_seen_size

    if file_changed:
        last_change_time = now_epoch

    source_db_exists = db_exists_for_stage(log_path)
    effective_extracted_mtime = last_extracted_mtime
    if effective_extracted_mtime is None and timing_db_mtime is not None:
        effective_extracted_mtime = timing_db_mtime

    if is_extracting:
        status = STATE_EXTRACTING
    elif force_extract == 1:
        status = STATE_AWAIT
    elif timing_db_mtime is not None:
        if effective_extracted_mtime is not None and mtime > effective_extracted_mtime:
            if last_status == STATE_DONE:
                rerun += 1
            status = STATE_AWAIT
        else:
            status = STATE_DONE
            if last_extracted_mtime is None and effective_extracted_mtime is not None:
                state["Last_extracted_mtime"] = effective_extracted_mtime
    elif last_status == STATE_EXTRACT_FAILED and not file_changed:
        status = STATE_EXTRACT_FAILED
    elif source_db_exists or last_extracted_mtime is not None:
        if effective_extracted_mtime is None:
            status = STATE_AWAIT
        elif mtime > effective_extracted_mtime:
            if last_status == STATE_DONE:
                rerun += 1
            status = STATE_AWAIT
        else:
            status = STATE_DONE
    else:
        age = now_epoch - (last_change_time if last_change_time is not None else now_epoch)
        status = STATE_RUNNING if age <= 15 * 60 else STATE_FAILED

    state["Last_seen_mtime"] = mtime
    state["Last_seen_size"] = size
    state["Last_change_time"] = last_change_time
    state["Last_status"] = status
    state["Rerun"] = rerun
    return status, state, rerun


def apply_kpi_status(rec, log_path):
    if rec["Status"] == STATE_DONE:
        rec.update(extract_apr_kpi(log_path))
        ok = all(rec[col] != "" for col in KPI_COLUMNS)
        rec["Comments"] = "QC PASS" if ok else "ERR002"
        rec["Promote"] = "yes" if ok else "no"
        if not ok:
            rec["Status"] = STATE_FAILED
    elif rec["Status"] in {STATE_FAILED, STATE_EXTRACT_FAILED}:
        rec["Comments"] = "ERR001"
        rec["Promote"] = "no"
    return rec


def build_context(project_code):
    STOP_REQUESTED["value"] = False
    dashai_dir = f"/proj/{project_code}/DashAI"
    state_dir = os.path.join(dashai_dir, STATE_DIR)
    log_dir = os.path.join(dashai_dir, LOG_DIR)
    force_extract_file = os.path.join(state_dir, FORCE_EXTRACT_FILE_NAME)

    os.makedirs(log_dir, exist_ok=True)
    os.makedirs(state_dir, exist_ok=True)
    if not os.path.exists(force_extract_file):
        write_text_file(force_extract_file, "")

    worker_count = max(1, min(MAX_ACTIVE_WORKERS, os.cpu_count() or 1))
    context = {
        "active_workers": {},
        "completed_extraction_count": 0,
        "force_extract_file": force_extract_file,
        "log_dir": log_dir,
        "project_code": project_code,
        "queued_extraction_count": 0,
        "remaining_files": 0,
        "state_by_file": {},
        "state_dirty": False,
        "state_file": os.path.join(state_dir, STATE_FILE_NAME),
        "worker_pool": ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="apr-worker"),
        "writer": APR_DB_Operations.SQLiteWriter(APR_DB_Operations.get_db_path(dashai_dir)).start(),
    }

    install_signal_handlers()
    APR_DB_Operations.remove_old_logs(log_dir)
    append_log(context, "APR monitor started")
    return context


def should_stop():
    return STOP_REQUESTED["value"]


def get_monitor_files(context):
    context["writer"].check()
    context["queued_extraction_count"] = 0
    context["completed_extraction_count"] = 0
    context["state_by_file"] = load_state_file(context["state_file"])
    context["state_dirty"] = False
    apply_force_extract_requests(context)

    monitor_files = get_log_paths(f"/proj/{context['project_code']}/IMP")
    context["remaining_files"] = len(monitor_files)
    if not monitor_files:
        append_iteration_summary(context)
    return monitor_files


def get_file_item(context, log_path):
    log_meta = parse_log_args(log_path)
    file_info = get_file_info(log_path)
    state_key = log_meta["State_key"]
    saved_state = context["state_by_file"].get(state_key, {})
    state_entry = dict(saved_state)
    previous_status = saved_state.get("Last_status")

    state_entry.setdefault("Created", now_str())
    extraction_result, state_finished = finish_completed_work(context, state_key, file_info, state_entry)
    if state_finished:
        state_entry = state_finished

    tracker_record = build_record(log_path, state_entry["Created"], log_meta, file_info)
    status, state_entry, rerun_count = compute_status(
        state_entry,
        log_path,
        file_info["mtime"],
        file_info["size"],
        state_key in context["active_workers"],
        timing_db_mtime=get_timing_db_mtime(log_path, context["project_code"], meta=log_meta),
    )
    tracker_record["Status"] = status
    tracker_record["Rerun"] = rerun_count

    if status == STATE_AWAIT:
        context["queued_extraction_count"] += 1
    if extraction_result == "success":
        context["completed_extraction_count"] += 1

    return {
        "log_path": log_path,
        "previous_status": previous_status,
        "source_mtime": file_info["mtime"],
        "state_changed": state_entry != saved_state,
        "state_entry": state_entry,
        "state_key": state_key,
        "tracker_record": tracker_record,
    }


def perform_status_action(context, file_item):
    if file_item["tracker_record"]["Status"] != STATE_AWAIT or should_stop():
        return
    if file_item["state_key"] in context["active_workers"]:
        return

    run_dir = file_item["log_path"].replace(
        f"/logs/{file_item['tracker_record']['Stage']}.log",
        "",
    )
    future = context["worker_pool"].submit(
        timing_worker,
        context["writer"],
        context["project_code"],
        file_item["tracker_record"]["Stage"],
        run_dir,
        file_item["source_mtime"],
    )
    context["active_workers"][file_item["state_key"]] = future
    context["queued_extraction_count"] = max(context["queued_extraction_count"] - 1, 0)

    file_item["tracker_record"]["Status"] = STATE_EXTRACTING
    file_item["state_entry"]["Extraction_pid"] = None
    file_item["state_entry"]["Extraction_started_at"] = now_str()
    file_item["state_entry"]["Force_extract"] = 0
    file_item["state_entry"]["Last_extract_result"] = "running"
    file_item["state_entry"]["Last_status"] = STATE_EXTRACTING
    file_item["state_changed"] = True
    context["state_dirty"] = True


def update_apr_tracker(context, file_item):
    context["writer"].check()
    tracker_record = apply_kpi_status(file_item["tracker_record"], file_item["log_path"])
    file_item["tracker_record"] = tracker_record

    if file_item["state_entry"].get("Last_status") == STATE_DONE and tracker_record["Status"] == STATE_FAILED:
        file_item["state_entry"]["Last_status"] = STATE_FAILED
        file_item["state_changed"] = True

    context["writer"].submit_tracker(tracker_record)


def update_apr_state(context, file_item):
    context["state_by_file"][file_item["state_key"]] = file_item["state_entry"]
    if file_item["state_changed"] or context["state_dirty"]:
        save_state_file(context)


def update_apr_log(context, file_item):
    if file_item["previous_status"] and file_item["previous_status"] != file_item["tracker_record"]["Status"]:
        append_log(
            context,
            f"Status changed | {file_item['state_key']} | "
            f"{file_item['previous_status']} -> {file_item['tracker_record']['Status']}",
        )

    context["remaining_files"] -= 1
    if context["remaining_files"] <= 0:
        append_iteration_summary(context)


def sleep_monitor():
    for _ in range(POLL_SECONDS):
        if should_stop():
            return
        time.sleep(1)


def close_context(context):
    try:
        if context["state_dirty"]:
            save_state_file(context)
        context["worker_pool"].shutdown(wait=True, cancel_futures=False)
        context["writer"].close()
    finally:
        append_log(context, "APR monitor stopped")


def timing_worker(writer, project_code, stage, run_dir, source_mtime):
    payload = TIMING.build_timing_payload(project_code, stage, run_dir, source_mtime=source_mtime)
    if payload is None:
        return {"success": False, "result": "no reports found"}
    writer.submit_timing(payload)
    return {"success": True, "result": "success"}


def finish_completed_work(context, state_key, file_info, state_entry):
    future = context["active_workers"].get(state_key)
    if future is None or not future.done():
        return None, None

    context["active_workers"].pop(state_key, None)
    updated_state = dict(state_entry)
    updated_state["Extraction_pid"] = None
    updated_state["Extraction_started_at"] = None
    updated_state["Last_extract_finished_at"] = now_str()

    try:
        result = future.result()
    except Exception as exc:
        result = {"success": False, "result": str(exc) or "failed"}

    if result.get("success"):
        updated_state["Force_extract"] = 0
        updated_state["Last_extract_result"] = "success"
        updated_state["Last_extracted_mtime"] = file_info["mtime"]
        updated_state["Last_status"] = STATE_DONE
        return "success", updated_state

    updated_state["Force_extract"] = 1
    updated_state["Last_extract_result"] = result.get("result", "failed")
    updated_state["Last_status"] = STATE_EXTRACT_FAILED
    append_log(context, f"Extraction failed | {state_key} | {updated_state['Last_extract_result']}")
    return "failed", updated_state


def request_stop(*_args):
    STOP_REQUESTED["value"] = True


def install_signal_handlers():
    for signal_name in ("SIGINT", "SIGTERM", "SIGBREAK"):
        signal_value = getattr(signal, signal_name, None)
        if signal_value is not None:
            signal.signal(signal_value, request_stop)


def append_log(context, message):
    with open(os.path.join(context["log_dir"], today_log_file()), "a", encoding="utf-8") as logfile:
        logfile.write(f"{now_str()} | {message}\n")


def append_iteration_summary(context):
    append_log(
        context,
        f"Queued_Extractions = {context['queued_extraction_count']} | "
        f"Completed_Extractions = {context['completed_extraction_count']}",
    )


def load_state_file(state_file):
    try:
        with open(state_file, "r", encoding="utf-8") as infile:
            raw_state = json.load(infile)
    except Exception:
        return {}

    if not isinstance(raw_state, dict):
        return {}

    return {
        state_key: sanitize_state_entry(state_entry)
        for state_key, state_entry in raw_state.items()
        if is_file_state_key(state_key) and isinstance(state_entry, dict)
    }


def save_state_file(context):
    clean_state = {
        state_key: sanitize_state_entry(state_entry)
        for state_key, state_entry in context["state_by_file"].items()
        if is_file_state_key(state_key)
    }
    context["state_by_file"] = clean_state
    write_text_file(context["state_file"], json.dumps(clean_state, indent=2, sort_keys=True))
    context["state_dirty"] = False


def apply_force_extract_requests(context):
    requested_keys = []
    with open(context["force_extract_file"], "r", encoding="utf-8") as infile:
        for line in infile:
            state_key = line.strip()
            if is_file_state_key(state_key) and state_key not in requested_keys:
                requested_keys.append(state_key)

    if not requested_keys:
        return

    for state_key in requested_keys:
        context["state_by_file"].setdefault(state_key, {"Created": now_str()})
        context["state_by_file"][state_key]["Force_extract"] = 1
        if state_key not in context["active_workers"]:
            context["state_by_file"][state_key]["Last_status"] = STATE_AWAIT

    context["state_dirty"] = True
    save_state_file(context)
    write_text_file(context["force_extract_file"], "")


def write_text_file(path, text):
    temp_file = f"{path}.tmp"
    with open(temp_file, "w", encoding="utf-8") as outfile:
        outfile.write(text)
        outfile.flush()
        os.fsync(outfile.fileno())
    os.replace(temp_file, path)


def is_file_state_key(state_key):
    return isinstance(state_key, str) and state_key.count("--") == 3


def sanitize_state_entry(state_entry):
    if not isinstance(state_entry, dict):
        return {}
    return {
        field_name: state_entry[field_name]
        for field_name in STATE_ENTRY_FIELDS
        if field_name in state_entry
    }
