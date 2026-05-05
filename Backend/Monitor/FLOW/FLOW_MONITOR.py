import FLOW_ACTIONS


def main():
    context = FLOW_ACTIONS.CHECK_SYS_ARGS()
    try:
        while not FLOW_ACTIONS.SHOULD_EXIT(context):
            for monitor_item in FLOW_ACTIONS.GET_MONITOR_ITEMS(context):
                monitor_item_status = FLOW_ACTIONS.GET_ITEM_STATUS(context, monitor_item)
                FLOW_ACTIONS.PERFORM_STATUS_ACTION(context, monitor_item_status)
                FLOW_ACTIONS.UPDATE_TRACKER(context, monitor_item_status)
                FLOW_ACTIONS.UPDATE_STATE(context, monitor_item_status)
                FLOW_ACTIONS.UPDATE_LOG(context, monitor_item_status)
            FLOW_ACTIONS.SLEEP(context)
    finally:
        FLOW_ACTIONS.CLOSE(context)


if __name__ == "__main__":
    main()
