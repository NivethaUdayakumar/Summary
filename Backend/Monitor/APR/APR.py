import APR_Actions

def main():
    context = APR_Actions.CHECK_SYS_ARGS()
    while not APR_Actions.SHOULD_EXIT(context):
        for monitor_file in APR_Actions.GET_MONITOR_FILES(context):
            file_item = APR_Actions.GET_FILE_STATUS(context, monitor_file)
            APR_Actions.PERFORM_STATUS_ACTION(context, file_item)
            APR_Actions.UPDATE_APR_TRACKER(context, file_item)
            APR_Actions.UPDATE_APR_STATE(context, file_item)
            APR_Actions.UPDATE_APR_LOG(context, file_item)
        APR_Actions.SLEEP(context)
    APR_Actions.CLOSE(context)

if __name__ == "__main__":
    main()