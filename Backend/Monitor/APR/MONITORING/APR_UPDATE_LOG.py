import logging
import os
from datetime import datetime, timedelta

import APR_VARS


def ensure_logger(context, log_file):
    """
    Function Name: ensure_logger
    Purpose: Create or rotate the APR batch logger so the current cycle writes to the right absolute log file.
    Input Params: context (dict), log_file (str | os.PathLike)
    Output: logger (logging.Logger)
    """
    logger = context.get("logger")
    if logger is None:
        logger = logging.getLogger(f"apr.monitor.{context['project_code']}")
        logger.setLevel(logging.INFO)
        logger.propagate = False
        context["logger"] = logger

    log_file_path = os.path.abspath(str(log_file))
    if context.get("logger_path") == log_file_path:
        return logger

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass

    handler = logging.FileHandler(log_file_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s", "%Y/%m/%d %H:%M:%S"))
    logger.addHandler(handler)
    context["logger_path"] = log_file_path
    return logger


def close_logger(context):
    """
    Function Name: close_logger
    Purpose: Close and detach all APR log handlers from the current runtime logger.
    Input Params: context (dict)
    Output: outputs (None)
    """
    logger = context.get("logger")
    if logger is None:
        return

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass

    context["logger_path"] = None


def remove_old_logs(log_dir, keep_days=None):
    """
    Function Name: remove_old_logs
    Purpose: Delete APR batch log files older than the configured retention window.
    Input Params: log_dir (str | os.PathLike), keep_days (int | None)
    Output: outputs (None)
    """
    absolute_log_dir = os.path.abspath(str(log_dir))
    if not os.path.isdir(absolute_log_dir):
        return

    keep_days = APR_VARS.get_setting("LOG_KEEP_DAYS") if keep_days is None else keep_days
    cutoff = datetime.now() - timedelta(days=int(keep_days))
    for name in os.listdir(absolute_log_dir):
        if not name.startswith("APR_") or not name.endswith(".log"):
            continue
        path = os.path.abspath(os.path.join(absolute_log_dir, name))
        try:
            if datetime.fromtimestamp(os.path.getmtime(path)) < cutoff:
                os.remove(path)
        except Exception:
            pass


def log_batch_submission(context, batch_id, item_count, submit_command="", batch_file_path=""):
    """
    Function Name: log_batch_submission
    Purpose: Write the batch submission event that records when a batch starts, what file it uses, and how many items it contains.
    Input Params: context (dict), batch_id (str), item_count (int), submit_command (str), batch_file_path (str)
    Output: outputs (None)
    """
    logger = context.get("logger")
    if logger is None:
        return
    logger.info(
        "batch_submitted | batch_id=%s | items=%s | batch_file=%s | command=%s",
        batch_id,
        item_count,
        batch_file_path,
        submit_command,
    )


def log_batch_completion(context, batch_id, item_count, success_count, failed_count, submit_command=""):
    """
    Function Name: log_batch_completion
    Purpose: Write the batch completion event with total, success, failure, and command details for the finished batch.
    Input Params: context (dict), batch_id (str), item_count (int), success_count (int), failed_count (int), submit_command (str)
    Output: outputs (None)
    """
    logger = context.get("logger")
    if logger is None:
        return
    logger.info(
        "batch_completed | batch_id=%s | items=%s | success=%s | failed=%s | command=%s",
        batch_id,
        item_count,
        success_count,
        failed_count,
        submit_command,
    )


def log_batch_termination(context, batch_id, item_count, completed_count, reset_count, submit_command="", lsf_job_id=""):
    """
    Function Name: log_batch_termination
    Purpose: Write the shutdown event for one interrupted batch, including how many items stayed completed versus were reset.
    Input Params: context (dict), batch_id (str), item_count (int), completed_count (int), reset_count (int), submit_command (str), lsf_job_id (str)
    Output: outputs (None)
    """
    logger = context.get("logger")
    if logger is None:
        return
    logger.info(
        "batch_terminated | batch_id=%s | items=%s | completed=%s | reset=%s | lsf_job_id=%s | command=%s",
        batch_id,
        item_count,
        completed_count,
        reset_count,
        lsf_job_id,
        submit_command,
    )


def update_log(_context, _file_item):
    """
    Function Name: update_log
    Purpose: Keep the flow update hook stable while APR stores only batch-level log records through the batch helpers.
    Input Params: _context (dict), _file_item (dict)
    Output: outputs (None)
    """
    return None
