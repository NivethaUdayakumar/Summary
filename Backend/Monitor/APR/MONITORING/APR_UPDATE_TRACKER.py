import APR_VARS
from Backend.Monitor.APR.EXTRACTORS.APR_KPI_EXTRACT import extract_apr_kpi


def apply_kpi_status(tracker_record, log_path):
    """
    Function Name: apply_kpi_status
    Purpose: Populate KPI fields and final promote/comments values based on the extraction result for one tracker row.
    Input Params: tracker_record (dict), log_path (str)
    Output: tracker_record (dict)
    """
    settings = APR_VARS.get_runtime_settings()
    if tracker_record["Status"] == settings["STATE_DONE"]:
        tracker_record.update(extract_apr_kpi(log_path))
        is_valid = all(tracker_record[column_name] != "" for column_name in settings["KPI_COLUMNS"])
        tracker_record["Comments"] = "QC PASS" if is_valid else "ERR002"
        tracker_record["Promote"] = "yes" if is_valid else "no"
        if not is_valid:
            tracker_record["Status"] = settings["STATE_FAILED"]
    elif tracker_record["Status"] in {settings["STATE_FAILED"], settings["STATE_EXTRACT_FAILED"]}:
        tracker_record["Comments"] = "ERR001"
        tracker_record["Promote"] = "no"
    return tracker_record


def update_tracker(context, file_item):
    """
    Function Name: update_tracker
    Purpose: Push the latest APR tracker record into SQLite after applying KPI extraction and any failure corrections.
    Input Params: context (dict), file_item (dict)
    Output: outputs (None)
    """
    settings = APR_VARS.get_runtime_settings()
    context["writer"].check()
    tracker_record = apply_kpi_status(file_item["tracker_record"], file_item["log_path"])
    file_item["tracker_record"] = tracker_record

    if file_item["state_entry"].get("Last_status") == settings["STATE_DONE"] and tracker_record["Status"] == settings["STATE_FAILED"]:
        file_item["state_entry"]["Last_status"] = settings["STATE_FAILED"]
        file_item["state_changed"] = True
        context["state_dirty"] = True

    context["writer"].submit_tracker(tracker_record)
