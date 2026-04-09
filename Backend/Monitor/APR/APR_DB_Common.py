import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def utc_now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def ensure_parent(path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def get_conn(dbname: str | Path) -> sqlite3.Connection:
    ensure_parent(dbname)
    conn = sqlite3.connect(str(dbname))
    conn.row_factory = sqlite3.Row
    return conn


def row_to_dict(row):
    return dict(row) if row else None


def json_dumps_safe(value) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)