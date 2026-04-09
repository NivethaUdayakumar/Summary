from pathlib import Path

from APR_DB_Common import json_dumps_safe, utc_now_str


INSERT_COLUMNS = (
    "record_key",
    "filepath",
    "filename",
    "project_code",
    "status",
    "file_size",
    "modified_time",
    "created_at",
    "updated_at",
    "hidden",
    "metadata_json",
)


def Get_values_for_record(project_code: str, filepath: str, status: str = "failed", hidden: int = 0):
    path = Path(filepath).resolve()
    stat = path.stat()

    metadata = {
        "parent": str(path.parent),
        "suffix": path.suffix,
    }

    values_tuple = (
        str(path),
        str(path),
        path.name,
        project_code,
        status,
        stat.st_size,
        stat.st_mtime,
        utc_now_str(),
        utc_now_str(),
        hidden,
        json_dumps_safe(metadata),
    )

    return INSERT_COLUMNS, values_tuple