import os
import time

from Backend.Monitor.APR.APR_Config import FILE_STABLE_SECONDS


def Get_file_status(filepath: str) -> str:
    try:
        stat1 = os.stat(filepath)
        time.sleep(1)
        stat2 = os.stat(filepath)

        same_size = stat1.st_size == stat2.st_size
        same_mtime = int(stat1.st_mtime) == int(stat2.st_mtime)
        old_enough = (time.time() - stat2.st_mtime) >= FILE_STABLE_SECONDS

        if same_size and same_mtime and old_enough:
            return "complete"
        return "failed"
    except FileNotFoundError:
        return "failed"
    except OSError:
        return "failed"