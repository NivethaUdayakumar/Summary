import importlib
import re
import sys
from pathlib import Path


FLOW_DIR = Path(__file__).resolve().parent
MONITOR_DIR = FLOW_DIR.parent

FLOW_MODULE_SPECS = {
    "MONITOR_ITEMS": ("{flow}_MONITOR_ITEMS", ("build_context", "get_monitor_items")),
    "ITEM_STATUS": ("{flow}_ITEM_STATUS", ("get_item_status",)),
    "STATUS_ACTION": ("{flow}_STATUS_ACTION", ("perform_status_action",)),
    "UPDATE_TRACKER": ("{flow}_UPDATE_TRACKER", ("update_tracker",)),
    "UPDATE_STATE": ("{flow}_UPDATE_STATE", ("update_state",)),
    "UPDATE_LOG": ("{flow}_UPDATE_LOG", ("update_log",)),
    "SLEEP": ("{flow}_SLEEP", ("should_exit", "sleep_monitor")),
    "CLOSE": ("{flow}_CLOSE", ("close_context",)),
}


def _normalize_flow_name(flow_name):
    """
    Function Name: _normalize_flow_name
    Purpose: Normalize and validate the requested FLOW name before module lookup.
    Input Params: flow_name (str)
    Output: selected_flow (str)
    """
    selected_flow = str(flow_name or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9_]+", selected_flow):
        raise ValueError(f"Invalid FLOW value: {flow_name!r}")
    return selected_flow


def _get_flow_dir(selected_flow):
    """
    Function Name: _get_flow_dir
    Purpose: Resolve the absolute monitor directory for one validated FLOW name.
    Input Params: selected_flow (str)
    Output: flow_dir (Path)
    """
    flow_dir = MONITOR_DIR / selected_flow
    if not flow_dir.is_dir():
        raise FileNotFoundError(f"Flow directory not found: {flow_dir}")
    return flow_dir


def _get_flow_module_dirs(selected_flow):
    """
    Function Name: _get_flow_module_dirs
    Purpose: Return the module search directories for one FLOW, preferring its MONITORING subfolder when present.
    Input Params: selected_flow (str)
    Output: module_dirs (list[Path])
    """
    flow_dir = _get_flow_dir(selected_flow)
    module_dirs = [flow_dir]
    monitoring_dir = flow_dir / "MONITORING"
    if monitoring_dir.is_dir():
        module_dirs.insert(0, monitoring_dir)
    return module_dirs


def _ensure_flow_dirs_on_path(flow_dirs):
    """
    Function Name: _ensure_flow_dirs_on_path
    Purpose: Insert the FLOW module directories into sys.path so the selected monitor modules can be imported.
    Input Params: flow_dirs (list[Path])
    Output: outputs (None)
    """
    for flow_dir in reversed(flow_dirs):
        flow_dir_str = str(flow_dir)
        if flow_dir_str not in sys.path:
            sys.path.insert(0, flow_dir_str)


def _load_flow_modules(selected_flow):
    """
    Function Name: _load_flow_modules
    Purpose: Import and validate the full shared FLOW module set required for the selected monitor flow.
    Input Params: selected_flow (str)
    Output: modules (dict)
    """
    flow_dirs = _get_flow_module_dirs(selected_flow)
    _ensure_flow_dirs_on_path(flow_dirs)

    modules = {}
    for key, (module_template, required_functions) in FLOW_MODULE_SPECS.items():
        module_name = module_template.format(flow=selected_flow)
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:
            raise ImportError(f"Unable to load flow module '{module_name}'") from exc

        missing_functions = [
            function_name
            for function_name in required_functions
            if not hasattr(module, function_name)
        ]
        if missing_functions:
            missing_display = ", ".join(missing_functions)
            raise AttributeError(
                f"Flow module '{module_name}' is missing required functions: {missing_display}"
            )

        modules[key] = module

    return modules


def build_context(flow_name, project_code):
    """
    Function Name: build_context
    Purpose: Build the shared FLOW runtime context by loading the selected flow modules and merging their base context data.
    Input Params: flow_name (str), project_code (str)
    Output: context (dict)
    """
    selected_flow = _normalize_flow_name(flow_name)
    normalized_project_code = str(project_code or "").strip()
    if not normalized_project_code:
        raise ValueError("PROJECT_CODE is required")

    modules = _load_flow_modules(selected_flow)
    context = modules["MONITOR_ITEMS"].build_context(normalized_project_code)
    if not isinstance(context, dict):
        raise TypeError(f"{selected_flow}_MONITOR_ITEMS.build_context must return a dict")

    context["FLOW"] = selected_flow
    context["PROJECT_CODE"] = normalized_project_code
    context["FLOW_MODULES"] = modules
    return context
