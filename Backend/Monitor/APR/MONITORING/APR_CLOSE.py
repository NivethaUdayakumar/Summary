def close_context(context):
    """
    Function Name: close_context
    Purpose: Close the APR SQLite writer cleanly before the shared FLOW monitor exits.
    Input Params: context (dict)
    Output: outputs (None)
    """
    writer = context.get("db_writer")
    if writer is None:
        return

    try:
        writer.close()
    except Exception:
        pass
