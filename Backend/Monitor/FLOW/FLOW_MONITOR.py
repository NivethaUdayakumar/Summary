import FLOW_ACTIONS

def main():
    context = FLOW_ACTIONS.CHECK_SYS_ARGS()
    try:
        while True:
            for MONITOR_ITEM in FLOW_ACTIONS.GET_MONITOR_ITEMS(context):
                MONITOR_ITEM_STATUS = FLOW_ACTIONS.GET_ITEM_STATUS(context, MONITOR_ITEM)
                FLOW_ACTIONS.PERFORM_STATUS_ACTION(context, MONITOR_ITEM_STATUS)
                FLOW_ACTIONS.UPDATE_TRACKER(context, MONITOR_ITEM_STATUS)
                FLOW_ACTIONS.UPDATE_STATE(context, MONITOR_ITEM_STATUS)
                FLOW_ACTIONS.UPDATE_LOG(context, MONITOR_ITEM_STATUS)
            FLOW_ACTIONS.SLEEP(context)
    finally:
        FLOW_ACTIONS.CLOSE(context)

if __name__ == "__main__":
    main()
