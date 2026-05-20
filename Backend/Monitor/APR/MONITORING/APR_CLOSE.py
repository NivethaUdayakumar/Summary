from Backend.Monitor.APR.MONITORING import APR_STATUS_ACTION
from Backend.Monitor.APR.MONITORING.APR_MONITOR_ITEMS import (
    get_runtime_paths,
    load_force_extract_payload,
    load_state_file,
    persist_runtime_payloads,
)
from Backend.Monitor.APR.MONITORING.APR_UPDATE_LOG import close_logger


def close_context(context):
    """
    Function Name: close_context
    Purpose: Cleanly stop APR batch work, persist state and force-extract files, and close writer/logger resources even on errors.
    Input Params: context (dict)
    Output: outputs (None)
    """
    state = context.get("state")

    try:
        runtime_paths = get_runtime_paths(context)
        runtime_paths["dashai_dir"].mkdir(parents=True, exist_ok=True)
        runtime_paths["state_dir"].mkdir(parents=True, exist_ok=True)
        context["runtime_paths"] = runtime_paths
    except Exception:
        runtime_paths = context.get("runtime_paths", {})

    try:
        if state is None and runtime_paths.get("state_file") is not None:
            state = load_state_file(runtime_paths["state_file"])
            context["state"] = state

        if context.get("force_extract_payload") is None and runtime_paths.get("force_extract_file") is not None:
            context["force_extract_payload"] = load_force_extract_payload(runtime_paths["force_extract_file"])

        if state is not None and APR_STATUS_ACTION.shutdown_runtime(context, state):
            context["state_dirty"] = True

        persist_runtime_payloads(context)
    except Exception:
        pass
    finally:
        writer = context.get("writer")
        if writer is not None:
            try:
                writer.close()
            except Exception:
                pass
        close_logger(context)
