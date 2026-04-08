import os
from pathlib import Path
from datetime import datetime


PROJECTS_BASE_DIR = Path("/proj")


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_project_root(project_code: str) -> Path:
    return PROJECTS_BASE_DIR / project_code


def get_apr_base_dir(project_code: str) -> Path:
    """
    Modify this if your APR runs are stored elsewhere.
    Example assumed structure:
    /proj/<project_code>/APR/<block>/<run>/
    """
    return get_project_root(project_code) / "APR"


def safe_stat_time(path: Path):
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


def extract_apr_runs(project_code: str):
    """
    Returns list of run dicts.
    Assumed folder structure:
    /proj/<project_code>/APR/<block>/<run>/
    """
    apr_base = get_apr_base_dir(project_code)
    rows = []

    if not apr_base.exists():
        return rows

    for block_dir in apr_base.iterdir():
        if not block_dir.is_dir():
            continue

        block_name = block_dir.name

        for run_dir in block_dir.iterdir():
            if not run_dir.is_dir():
                continue

            run_name = run_dir.name
            run_id = f"{block_name}_{run_name}"

            rows.append({
                "run_id": run_id,
                "project_code": project_code,
                "block": block_name,
                "run_name": run_name,
                "run_path": str(run_dir),
                "status": "unknown",
                "hidden": 0,
                "last_seen_ts": now_str(),
                "last_modified_ts": safe_stat_time(run_dir),
                "manual_update_ts": "",
                "created_at": now_str(),
                "updated_at": now_str(),
            })

    return rows