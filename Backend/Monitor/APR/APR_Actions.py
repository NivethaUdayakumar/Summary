import sys

import APR_Utils


def CHECK_SYS_ARGS():
    if len(sys.argv) != 2:
        print("Usage: python3 APR.py <project_code>")
        sys.exit(1)
    return APR_Utils.build_context(sys.argv[1])


def SHOULD_EXIT(_context):
    return APR_Utils.should_stop()


def GET_MONITOR_FILES(context):
    return APR_Utils.get_monitor_files(context)


def GET_FILE_STATUS(context, log_path):
    return APR_Utils.get_file_item(context, log_path)


def PERFORM_STATUS_ACTION(context, file_item):
    APR_Utils.perform_status_action(context, file_item)


def UPDATE_APR_TRACKER(context, file_item):
    APR_Utils.update_apr_tracker(context, file_item)


def UPDATE_APR_STATE(context, file_item):
    APR_Utils.update_apr_state(context, file_item)


def UPDATE_APR_LOG(context, file_item):
    APR_Utils.update_apr_log(context, file_item)


def SLEEP(_context):
    APR_Utils.sleep_monitor()


def CLOSE(context):
    APR_Utils.close_context(context)
