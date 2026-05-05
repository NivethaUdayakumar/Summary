from Backend.Monitor.APR.MONITORING.APR_MONITOR_ITEMS import save_force_extract_payload, save_state_file


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

    if context.get("state_dirty"):
        save_state_file(context)
    if context.get("force_extract_dirty"):
        save_force_extract_payload(context)
