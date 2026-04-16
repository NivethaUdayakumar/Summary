import csv
import os
import pwd
import subprocess
import time

from APR_Definitions import (
    DEFAULT_FLOW,
    DEFAULT_MAXDEPTH,
    DEFAULT_MINDEPTH,
    DEFAULT_TOOL,
    KPI_COLUMNS,
    STAGES,
    STATE_AWAIT,
    STATE_DONE,
    STATE_EXTRACT_FAILED,
    STATE_EXTRACTING,
    STATE_FAILED,
    STATE_RUNNING,
    make_state_key,
)


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


def get_timing_capture_command(rundir, stage, project_name):
    proc_py = os.path.join(os.path.dirname(__file__), "timing_apr_innovus.py")
    py = "python3" if os.name != "nt" else "py"
    cmd = f'module load Python3/3.11.1 && utilq -Is {py} "{proc_py}" "{project_name}" "{stage}" "{rundir}"'
    env = os.environ.copy()
    env["LSB_DEFAULTPROJECT"] = project_name
    return cmd, env


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


def compute_status(state, log_path, mtime, size, is_extracting):
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
    exists = db_exists_for_stage(log_path)
    if is_extracting:
        status = STATE_EXTRACTING
    elif force_extract == 1:
        status = STATE_AWAIT
    elif last_status == STATE_EXTRACT_FAILED and not file_changed:
        status = STATE_EXTRACT_FAILED
    elif exists:
        if last_extracted_mtime is None:
            status = STATE_AWAIT
        elif mtime > last_extracted_mtime:
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
