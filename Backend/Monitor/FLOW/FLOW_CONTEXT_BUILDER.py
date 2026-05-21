import importlib
import re
import sys
from pathlib import Path
from types import SimpleNamespace


FLOW_DIR = Path(__file__).resolve().parent
MONITOR_DIR = FLOW_DIR.parent
ROOT_DIR = MONITOR_DIR.parent.parent
FLOW_CONTEXT_MODULE_SUFFIX = "FLOW_CONTEXT"

FLOW_MODULE_SPECS = {
    "MONITOR_ITEMS": ("MONITOR_ITEMS", ("get_monitor_items",)),
    "ITEM_STATUS": ("ITEM_STATUS", ("get_item_status",)),
    "STATUS_ACTION": ("STATUS_ACTION", ("perform_status_action",)),
    "SLEEP": ("SLEEP", ("should_exit", "sleep_monitor")),
    "CLOSE": ("CLOSE", ("close_context",)),
}

FLOW_UPDATE_MODULE_SPECS = (
    ("UPDATE_TRACKER", "UPDATE_TRACKER", "update_tracker"),
    ("UPDATE_STATE", "UPDATE_STATE", "update_state"),
    ("UPDATE_LOG", "UPDATE_LOG", "update_log"),
)


class MissingFlowModuleError(ImportError):
    """Raised when a selected flow module does not exist in either supported import location."""


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


def _ensure_import_roots(selected_flow):
    """
    Function Name: _ensure_import_roots
    Purpose: Validate the selected FLOW directory and ensure repo-style package imports resolve from the repository root.
    Input Params: selected_flow (str)
    Output: flow_dir (Path)
    """
    flow_dir = _get_flow_dir(selected_flow)
    root_dir_str = str(ROOT_DIR)
    if root_dir_str not in sys.path:
        sys.path.insert(0, root_dir_str)
    return flow_dir


def _get_module_candidates(selected_flow, module_suffix):
    """
    Function Name: _get_module_candidates
    Purpose: Build the supported import paths for one selected FLOW module suffix.
    Input Params: selected_flow (str), module_suffix (str)
    Output: module_candidates (list[str])
    """
    flow_package = f"Backend.Monitor.{selected_flow}"
    return [
        f"{flow_package}.MONITORING.{selected_flow}_{module_suffix}",
        f"{flow_package}.{selected_flow}_{module_suffix}",
    ]


def _load_flow_module(selected_flow, module_suffix, required_functions):
    """
    Function Name: _load_flow_module
    Purpose: Import one FLOW module from the supported package locations and validate its required functions.
    Input Params: selected_flow (str), module_suffix (str), required_functions (tuple[str, ...])
    Output: module (module)
    """
    module_candidates = _get_module_candidates(selected_flow, module_suffix)
    last_not_found_error = None
    for module_name in module_candidates:
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            if exc.name == module_name:
                last_not_found_error = exc
                continue
            raise ImportError(f"Unable to load flow module '{module_name}'") from exc
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
        return module

    candidates_display = ", ".join(module_candidates)
    raise MissingFlowModuleError(
        f"Unable to locate flow module for '{selected_flow}_{module_suffix}'. Tried: {candidates_display}"
    ) from last_not_found_error


def _build_update_db_module(update_modules):
    """
    Function Name: _build_update_db_module
    Purpose: Adapt split tracker/state/log flow update modules into the shared single update_db hook.
    Input Params: update_modules (dict)
    Output: update_db_module (types.SimpleNamespace)
    """
    def update_db(context, file_item):
        update_modules["UPDATE_TRACKER"].update_tracker(context, file_item)
        update_modules["UPDATE_STATE"].update_state(context, file_item)
        update_modules["UPDATE_LOG"].update_log(context, file_item)

    return SimpleNamespace(update_db=update_db)


def _load_context_module(selected_flow):
    """
    Function Name: _load_context_module
    Purpose: Load the selected flow context-builder module, preferring a dedicated FLOW_CONTEXT file and falling back to MONITOR_ITEMS when needed.
    Input Params: selected_flow (str)
    Output: context_module (module)
    """
    try:
        return _load_flow_module(selected_flow, FLOW_CONTEXT_MODULE_SUFFIX, ("build_context",))
    except MissingFlowModuleError:
        return _load_flow_module(selected_flow, "MONITOR_ITEMS", ("build_context",))


def _load_update_modules(selected_flow):
    """
    Function Name: _load_update_modules
    Purpose: Load either a legacy single update-db module or the split update pipeline and expose one update_db hook.
    Input Params: selected_flow (str)
    Output: update_modules (dict)
    """
    try:
        return {
            "UPDATE_DB": _load_flow_module(selected_flow, "UPDATE_DB", ("update_db",)),
        }
    except MissingFlowModuleError:
        update_modules = {}
        for module_key, module_suffix, function_name in FLOW_UPDATE_MODULE_SPECS:
            update_modules[module_key] = _load_flow_module(selected_flow, module_suffix, (function_name,))
        update_modules["UPDATE_DB"] = _build_update_db_module(update_modules)
        return update_modules


def _load_flow_modules(selected_flow):
    """
    Function Name: _load_flow_modules
    Purpose: Import and validate the full shared FLOW module set required for the selected monitor flow.
    Input Params: selected_flow (str)
    Output: modules (dict)
    """
    _ensure_import_roots(selected_flow)

    modules = {}
    for key, (module_suffix, required_functions) in FLOW_MODULE_SPECS.items():
        modules[key] = _load_flow_module(selected_flow, module_suffix, required_functions)
    modules.update(_load_update_modules(selected_flow))
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
    context_module = _load_context_module(selected_flow)
    context = context_module.build_context(normalized_project_code)
    if not isinstance(context, dict):
        raise TypeError(f"{selected_flow} flow context builder must return a dict")

    context.setdefault("flow", selected_flow)
    context.setdefault("project_code", normalized_project_code)
    context["FLOW"] = selected_flow
    context["PROJECT_CODE"] = normalized_project_code
    context["FLOW_MODULES"] = modules
    return context
