import FLOW_ACTIONS

def main():
    """
    Function Name: main
    Purpose: Run the shared FLOW monitor loop until the selected monitor flow requests shutdown, then always execute close handling.
    Input Params: outputs (None)
    Output: outputs (None)
    """
    context = FLOW_ACTIONS.BUILD_FLOW_CONTEXT()
    try:
        while not FLOW_ACTIONS.SHOULD_EXIT(context):
            for monitor_item in FLOW_ACTIONS.GET_MONITOR_ITEMS(context):
                monitor_item_status = FLOW_ACTIONS.GET_ITEM_STATUS(context, monitor_item)
                FLOW_ACTIONS.PERFORM_STATUS_ACTION(context, monitor_item_status)
                FLOW_ACTIONS.UPDATE_DB(context, monitor_item_status)
            FLOW_ACTIONS.SLEEP(context)
    finally:
        FLOW_ACTIONS.CLOSE(context)

if __name__ == "__main__":
    main()
