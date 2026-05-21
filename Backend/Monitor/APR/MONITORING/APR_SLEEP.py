import signal
import time

from Backend.Monitor.APR import APR_VARS


STOP_REQUESTED = {"value": False}


def reset_stop_request():
    """
    Function Name: reset_stop_request
    Purpose: Clear the APR monitor stop flag before a new runtime starts.
    Input Params: outputs (None)
    Output: outputs (None)
    """
    STOP_REQUESTED["value"] = False


def request_stop(*_args):
    """
    Function Name: request_stop
    Purpose: Mark the APR monitor runtime for shutdown when an OS signal is received.
    Input Params: _args (tuple)
    Output: outputs (None)
    """
    if STOP_REQUESTED["value"]:
        return

    STOP_REQUESTED["value"] = True

    # Exit the active monitor loop immediately so FLOW_MONITOR.main() reaches
    # its finally block and runs close_context() in the live monitor process.
    if _args:
        raise SystemExit(0)


def install_signal_handlers():
    """
    Function Name: install_signal_handlers
    Purpose: Register the APR monitor stop handler for the supported process termination signals.
    Input Params: outputs (None)
    Output: outputs (None)
    """
    for signal_name in ("SIGINT", "SIGTERM", "SIGBREAK"):
        signal_value = getattr(signal, signal_name, None)
        if signal_value is not None:
            signal.signal(signal_value, request_stop)


def should_exit(_context=None):
    """
    Function Name: should_exit
    Purpose: Report whether the APR monitor runtime has received a stop request.
    Input Params: _context (dict | None)
    Output: should_stop (bool)
    """
    return STOP_REQUESTED["value"]


def sleep_monitor(_context=None):
    """
    Function Name: sleep_monitor
    Purpose: Sleep between APR monitor cycles while still checking once per second for a stop request.
    Input Params: _context (dict | None)
    Output: outputs (None)
    """
    for _ in range(int(APR_VARS.get_setting("POLL_SECONDS", 60))):
        if should_exit():
            return
        time.sleep(1)
