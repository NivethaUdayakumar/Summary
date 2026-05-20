from Backend.Monitor.APR.MONITORING.APR_MONITOR_ITEMS import persist_runtime_payloads


def update_state(context, file_item):
    """
    Function Name: update_state
    Purpose: Persist any APR state or force-extract payload changes generated while processing one monitor item.
    Input Params: context (dict), file_item (dict)
    Output: outputs (None)
    """
    context["state"][file_item["state_key"]] = file_item["state_entry"]
    if file_item["state_changed"]:
        context["state_dirty"] = True

    persist_runtime_payloads(context)
