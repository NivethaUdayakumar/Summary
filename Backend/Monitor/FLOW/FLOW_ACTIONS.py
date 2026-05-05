import sys

import FLOW_CONTEXT_BUILDER


def CHECK_SYS_ARGS():
    if len(sys.argv) != 3:
        print("Usage: python FLOW_MONITOR.py <FLOW> <PROJECT_CODE>")
        sys.exit(1)
    return FLOW_CONTEXT_BUILDER.build_context(sys.argv[1], sys.argv[2])


def SHOULD_EXIT(context):
    return context["FLOW_MODULES"]["SLEEP"].should_exit(context)


def GET_MONITOR_ITEMS(context):
    return context["FLOW_MODULES"]["MONITOR_ITEMS"].get_monitor_items(context)


def GET_ITEM_STATUS(context, monitor_item):
    return context["FLOW_MODULES"]["ITEM_STATUS"].get_item_status(context, monitor_item)


def PERFORM_STATUS_ACTION(context, file_item):
    context["FLOW_MODULES"]["STATUS_ACTION"].perform_status_action(context, file_item)


def UPDATE_TRACKER(context, file_item):
    context["FLOW_MODULES"]["UPDATE_TRACKER"].update_tracker(context, file_item)


def UPDATE_STATE(context, file_item):
    context["FLOW_MODULES"]["UPDATE_STATE"].update_state(context, file_item)


def UPDATE_LOG(context, file_item):
    context["FLOW_MODULES"]["UPDATE_LOG"].update_log(context, file_item)


def SLEEP(context):
    context["FLOW_MODULES"]["SLEEP"].sleep_monitor(context)


def CLOSE(context):
    context["FLOW_MODULES"]["CLOSE"].close_context(context)
