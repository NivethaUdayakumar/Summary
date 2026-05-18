import APR_VARS
from Backend.Monitor.APR.EXTRACTORS.APR_KPI_EXTRACT import extract_apr_kpi
from Backend.Monitor.APR.MONITORING import APR_STATUS_ACTION


def apply_kpi_status(tracker_record, log_path, state_entry=None):
    """
    Function Name: apply_kpi_status
    Purpose: Populate KPI fields and final promote/comments values based on the extraction result for one tracker row.
    Input Params: tracker_record (dict), log_path (str), state_entry (dict | None)
    Output: tracker_record (dict)
    """
    settings = APR_VARS.get_runtime_settings()
    validation_error = APR_STATUS_ACTION.get_validation_error_code(state_entry)
    if tracker_record["Status"] == settings["STATE_DONE"]:
        tracker_record.update(extract_apr_kpi(log_path))
        is_valid = all(tracker_record[column_name] != "" for column_name in settings["KPI_COLUMNS"])
        tracker_record["Comments"] = "QC PASS" if is_valid else "ERR002"
        tracker_record["Promote"] = "yes" if is_valid else "no"
    elif validation_error and tracker_record["Status"] in {settings["STATE_FAILED"], settings["STATE_EXTRACT_FAILED"]}:
        tracker_record["Comments"] = validation_error
        tracker_record["Promote"] = "no"
    elif tracker_record["Status"] == settings["STATE_FAILED"]:
        tracker_record["Comments"] = "ERR001"
        tracker_record["Promote"] = "no"
    elif tracker_record["Status"] == settings["STATE_EXTRACT_FAILED"]:
        tracker_record["Comments"] = "ERR003"
        tracker_record["Promote"] = "no"
    return tracker_record


def update_tracker(context, file_item):
    """
    Function Name: update_tracker
    Purpose: Push the latest APR tracker record into SQLite after applying KPI extraction and any failure corrections.
    Input Params: context (dict), file_item (dict)
    Output: outputs (None)
    """
    context["writer"].check()
    tracker_record = apply_kpi_status(file_item["tracker_record"], file_item["log_path"], file_item["state_entry"])
    file_item["tracker_record"] = tracker_record

    context["writer"].submit_tracker(tracker_record)
