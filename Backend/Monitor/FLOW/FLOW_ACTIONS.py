import sys

import APR_MONITOR_ITEMS
import APR_EXIT
from Backend.Monitor.FLOW import FLOW_CONTEXT_BUILDER


def CHECK_SYS_ARGS():
    if len(sys.argv) != 3:
        print("Usage: python3 FLOW_MONITOR.py <FLOW> <PROJECT_CODE>")
        sys.exit(1)
    return FLOW_CONTEXT_BUILDER.build_context(sys.argv[1], sys.argv[2])


def GET_MONITOR_ITEMS(context):
    SELECTED_FLOW = context["FLOW"]
    PROJECT_CODE = context["PROJECT_CODE"]
    {FLOW}_MONITOR_ITEMS(PROJECT_CODE)
    return APR_Utils.get_monitor_files(context)


def GET_ITEM_STATUS(context, monitor_item):
    SELECTED_FLOW = context["FLOW"]
    PROJECT_CODE = context["PROJECT_CODE"]
    return APR_Utils.get_file_item(context, monitor_item)


def PERFORM_STATUS_ACTION(context, file_item):
    SELECTED_FLOW = context["FLOW"]
    PROJECT_CODE = context["PROJECT_CODE"]
    APR_Utils.perform_status_action(context, file_item)


def UPDATE_TRACKER(context, file_item):
    SELECTED_FLOW = context["FLOW"]
    PROJECT_CODE = context["PROJECT_CODE"]
    APR_Utils.update_apr_tracker(context, file_item)


def UPDATE_STATE(context, file_item):
    SELECTED_FLOW = context["FLOW"]
    PROJECT_CODE = context["PROJECT_CODE"]
    APR_Utils.update_apr_state(context, file_item)


def UPDATE_LOG(context, file_item):
    SELECTED_FLOW = context["FLOW"]
    PROJECT_CODE = context["PROJECT_CODE"]
    APR_Utils.update_apr_log(context, file_item)


def SLEEP(_context):
    SELECTED_FLOW = context["FLOW"]
    PROJECT_CODE = context["PROJECT_CODE"]
    APR_Utils.sleep_monitor()


def CLOSE(context):
    SELECTED_FLOW = context["FLOW"]
    PROJECT_CODE = context["PROJECT_CODE"]
    APR_Utils.close_context(context)