import os
from pathlib import Path

import APR_VARS
from Backend.Monitor.APR.MONITORING import APR_FLOW_CONTEXT
import Backend.Monitor.APR.MONITORING.APR_SLEEP as APR_SLEEP
from Backend.Monitor.APR.MONITORING import APR_STATUS_ACTION


def get_run_directories(base_path, context=None):
    """
    Function Name: get_run_directories
    Purpose: Discover APR run directories under IMP that match the configured flow/tool marker and depth rules.
    Input Params: base_path (str), context (dict | None)
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
        if context is not None and APR_SLEEP.should_exit(context):
            break

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


def get_stage_log_paths(run_directory):
    """
    Function Name: get_stage_log_paths
    Purpose: Return the absolute APR stage log files that currently exist under one discovered run directory.
    Input Params: run_directory (str)
    Output: stage_log_paths (list[str])
    """
    stage_log_paths = []
    for stage_name in list(APR_VARS.get_setting("STAGES", [])):
        candidate_path = os.path.abspath(os.path.join(run_directory, "logs", f"{stage_name}.log"))
        if os.path.exists(candidate_path):
            stage_log_paths.append(candidate_path)
    return sorted(stage_log_paths)


def build_monitor_item(run_directory, log_path):
    """
    Function Name: build_monitor_item
    Purpose: Build one APR monitor item from a run directory and one concrete stage log path.
    Input Params: run_directory (str), log_path (str)
    Output: monitor_item (dict)
    """
    return {
        "log_path": os.path.abspath(log_path),
        "run_directory": os.path.abspath(run_directory),
    }


def get_monitor_items(context):
    """
    Function Name: get_monitor_items
    Purpose: Refresh APR batch completion state and return the current stage-level monitor items discovered from APR run directories.
    Input Params: context (dict)
    Output: monitor_items (list[dict])
    """
    project_code = APR_FLOW_CONTEXT.get_project_code(context)
    APR_FLOW_CONTEXT.ensure_runtime_directories(project_code)
    context["db_writer"].check()
    APR_STATUS_ACTION.refresh_batches(context)

    monitor_items = []
    for run_directory in get_run_directories(APR_VARS.get_imp_dir(project_code), context):
        if APR_SLEEP.should_exit(context):
            break
        for log_path in get_stage_log_paths(run_directory):
            monitor_items.append(build_monitor_item(run_directory, log_path))

    return monitor_items
