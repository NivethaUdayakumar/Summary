import time
from pathlib import Path


def data_processing_code(filepath: str) -> None:
    """
    Replace this with your real re extraction logic.
    This function is intentionally standalone so it can run in background.
    """
    path = Path(filepath)
    time.sleep(2)
    output_marker = path.with_suffix(path.suffix + ".processed")
    output_marker.write_text(f"Processed: {path.name}\n", encoding="utf-8")