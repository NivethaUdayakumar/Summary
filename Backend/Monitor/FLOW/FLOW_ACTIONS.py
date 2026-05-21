import sys

try:
    from Backend.Monitor.FLOW import FLOW_CONTEXT_BUILDER
except ModuleNotFoundError:
    import FLOW_CONTEXT_BUILDER


def BUILD_FLOW_CONTEXT():
    """
    Function Name: BUILD_FLOW_CONTEXT
    Purpose: Build the runtime context for the requested flow and project.
    Input Params: outputs (None)
    Output: context (dict)
    """
    if len(sys.argv) != 3:
        print("Usage: python FLOW_MONITOR.py <FLOW> <PROJECT_CODE>")
        sys.exit(1)
    return FLOW_CONTEXT_BUILDER.build_context(sys.argv[1], sys.argv[2])


def SHOULD_EXIT(context):
    """
    Function Name: SHOULD_EXIT
    Purpose: Delegate the shared shutdown check to the selected flow sleep module.
    Input Params: context (dict)
    Output: should_exit (bool)
    """
    return context["FLOW_MODULES"]["SLEEP"].should_exit(context)


def GET_MONITOR_ITEMS(context):
    """
    Function Name: GET_MONITOR_ITEMS
    Purpose: Ask the selected flow monitor-items module for the current list of items to process in this cycle.
    Input Params: context (dict)
    Output: monitor_items (list)
    """
    return context["FLOW_MODULES"]["MONITOR_ITEMS"].get_monitor_items(context)


def GET_ITEM_STATUS(context, monitor_item):
    """
    Function Name: GET_ITEM_STATUS
    Purpose: Build the status payload for one monitor item using the selected flow item-status module.
    Input Params: context (dict), monitor_item (dict)
    Output: item_status (dict)
    """
    return context["FLOW_MODULES"]["ITEM_STATUS"].get_item_status(context, monitor_item)


def PERFORM_STATUS_ACTION(context, file_item):
    """
    Function Name: PERFORM_STATUS_ACTION
    Purpose: Delegate one monitor item's status-driven action handling to the selected flow status-action module.
    Input Params: context (dict), file_item (dict)
    Output: outputs (None)
    """
    context["FLOW_MODULES"]["STATUS_ACTION"].perform_status_action(context, file_item)


def UPDATE_DB(context, file_item):
    """
    Function Name: UPDATE_DB
    Purpose: Forward one monitor item to the selected flow database-update module for database persistence.
    Input Params: context (dict), file_item (dict)
    Output: outputs (None)
    """
    context["FLOW_MODULES"]["UPDATE_DB"].update_db(context, file_item)

def SLEEP(context):
    """
    Function Name: SLEEP
    Purpose: Run the selected flow sleep module between monitor cycles.
    Input Params: context (dict)
    Output: outputs (None)
    """
    context["FLOW_MODULES"]["SLEEP"].sleep_monitor(context)


def CLOSE(context):
    """
    Function Name: CLOSE
    Purpose: Run the selected flow close module so monitor resources are always cleaned up on exit.
    Input Params: context (dict)
    Output: outputs (None)
    """
    context["FLOW_MODULES"]["CLOSE"].close_context(context)
