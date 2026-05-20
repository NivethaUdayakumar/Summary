import os
from pathlib import Path

from Backend.Monitor.APR.EXTRACTORS.APR_TIMING_INNOVUS import get_timing_db_path as build_timing_db_path


def get_run_dir(log_path):
    """
    Function Name: get_run_dir
    Purpose: Return the absolute APR run directory that owns one stage log file.
    Input Params: log_path (str)
    Output: run_dir (Path)
    """
    return Path(os.path.abspath(log_path)).parent.parent


def get_source_db_path(log_path, log_meta=None):
    """
    Function Name: get_source_db_path
    Purpose: Build the absolute APR source-dbinfo path for one stage log.
    Input Params: log_path (str), log_meta (dict | None)
    Output: db_path (str)
    """
    run_dir = get_run_dir(log_path)
    metadata = log_meta or {}
    stage = metadata.get("Stage") or Path(log_path).stem
    job = metadata.get("Job") or run_dir.name
    return str(run_dir / "dbs" / f"{stage}_final" / f"{job}.dat" / f"{job}.dbinfo")


def get_timing_db_path(project_code, log_meta):
    """
    Function Name: get_timing_db_path
    Purpose: Build the absolute DashAI timing database path for one monitored APR run.
    Input Params: project_code (str), log_meta (dict)
    Output: db_path (str)
    """
    return build_timing_db_path(project_code, log_meta)


def path_exists(path):
    """
    Function Name: path_exists
    Purpose: Check whether one filesystem path currently exists without raising path errors.
    Input Params: path (str)
    Output: exists (bool)
    """
    try:
        return os.path.exists(os.path.abspath(path))
    except OSError:
        return False


def get_path_mtime(path):
    """
    Function Name: get_path_mtime
    Purpose: Return one path's integer mtime when available.
    Input Params: path (str)
    Output: mtime (int | None)
    """
    try:
        return int(os.path.getmtime(os.path.abspath(path)))
    except OSError:
        return None


def get_output_state(project_code, log_path, log_meta):
    """
    Function Name: get_output_state
    Purpose: Collect the source-db and timing-db paths, existence flags, and mtimes for one APR run.
    Input Params: project_code (str), log_path (str), log_meta (dict)
    Output: output_state (dict)
    """
    source_db_path = get_source_db_path(log_path, log_meta)
    timing_db_path = get_timing_db_path(project_code, log_meta)
    source_db_exists = path_exists(source_db_path)
    timing_db_exists = path_exists(timing_db_path)
    return {
        "source_db_exists": source_db_exists,
        "source_db_path": source_db_path,
        "timing_db_exists": timing_db_exists,
        "timing_db_mtime": get_path_mtime(timing_db_path) if timing_db_exists else None,
        "timing_db_path": timing_db_path,
    }


def outputs_are_complete(output_state):
    """
    Function Name: outputs_are_complete
    Purpose: Check whether both APR completion artifacts exist for one monitored run.
    Input Params: output_state (dict)
    Output: is_complete (bool)
    """
    return bool(output_state.get("source_db_exists")) and bool(output_state.get("timing_db_exists"))
