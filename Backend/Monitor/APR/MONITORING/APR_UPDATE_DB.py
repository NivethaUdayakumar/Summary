import os

from Backend.Monitor.APR import APR_VARS
from Backend.Monitor.APR.EXTRACTORS.APR_KPI_EXTRACT import extract_apr_kpi
from Backend.Monitor.APR.MONITORING import APR_FLOW_CONTEXT
from Backend.Monitor.APR.MONITORING import APR_ITEM_STATUS


def _build_tracker_record(file_item):
    """
    Function Name: _build_tracker_record
    Purpose: Build the current APR tracker row from the latest computed state entry and attach KPI data only for completed items.
    Input Params: file_item (dict)
    Output: tracker_record (dict)
    """
    tracker_record = APR_ITEM_STATUS.build_tracker_record(
        file_item["log_path"],
        file_item["state_entry"],
        meta=file_item.get("log_meta"),
        file_info=file_item.get("file_info"),
    )
    if (
        file_item["state_entry"]["Status"] == APR_VARS.get_setting("STATE_DONE")
        and os.path.exists(file_item.get("kpi_report_path", ""))
    ):
        tracker_record.update(extract_apr_kpi(file_item["log_path"]))
    return tracker_record


def update_db(context, file_item):
    """
    Function Name: update_db
    Purpose: Persist one APR monitor item's light state entry and upsert its APR_TRACKER row.
    Input Params: context (dict), file_item (dict)
    Output: outputs (None)
    """
    previous_state = dict(context["state"].get(file_item["state_key"], {}))
    current_state = dict(file_item["state_entry"])
    context["state"][file_item["state_key"]] = current_state
    if previous_state != current_state or file_item.get("state_changed"):
        APR_FLOW_CONTEXT.save_state(context)

    tracker_record = _build_tracker_record(file_item)
    file_item["tracker_record"] = tracker_record
    context["db_writer"].check()
    context["db_writer"].submit_tracker(tracker_record)
