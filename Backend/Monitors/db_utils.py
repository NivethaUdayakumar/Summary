import os
import re
import sqlite3
from typing import Any, Dict, List, Optional, Sequence

def _validate_identifier(name: str) -> str:
    """
    Allow only letters, numbers, and underscore for table and column names.
    """
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise ValueError(f"Invalid SQL identifier: {name}")
    return name


def _connect(db_path: str) -> sqlite3.Connection:
    return sqlite3.connect(db_path)


def create_db(db_path: str) -> Dict[str, Any]:
    """
    Creates a new SQLite database file if it does not exist.

    Input:
        db_path: str

    Output:
        {
            "success": bool,
            "message": str,
            "db_path": str
        }
    """
    try:
        conn = _connect(db_path)
        conn.close()
        return {
            "success": True,
            "message": "Database created or already exists",
            "db_path": db_path
        }
    except Exception as e:
        return {
            "success": False,
            "message": str(e),
            "db_path": db_path
        }


def delete_db(db_path: str) -> Dict[str, Any]:
    """
    Deletes the SQLite database file.

    Input:
        db_path: str

    Output:
        {
            "success": bool,
            "message": str,
            "db_path": str
        }
    """
    try:
        if os.path.exists(db_path):
            os.remove(db_path)
            return {
                "success": True,
                "message": "Database deleted",
                "db_path": db_path
            }
        return {
            "success": False,
            "message": "Database file not found",
            "db_path": db_path
        }
    except Exception as e:
        return {
            "success": False,
            "message": str(e),
            "db_path": db_path
        }


def create_table(
    db_path: str,
    table_name: str,
    columns: Dict[str, str]
) -> Dict[str, Any]:
    """
    Creates a table.

    Example columns:
        {
            "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
            "name": "TEXT NOT NULL",
            "age": "INTEGER",
            "email": "TEXT UNIQUE"
        }

    Output:
        {
            "success": bool,
            "message": str,
            "table": str,
            "sql": str
        }
    """
    try:
        table_name = _validate_identifier(table_name)

        column_defs = []
        for col_name, col_type in columns.items():
            col_name = _validate_identifier(col_name)
            column_defs.append(f"{col_name} {col_type}")

        sql = f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(column_defs)})"

        conn = _connect(db_path)
        cur = conn.cursor()
        cur.execute(sql)
        conn.commit()
        conn.close()

        return {
            "success": True,
            "message": "Table created or already exists",
            "table": table_name,
            "sql": sql
        }
    except Exception as e:
        return {
            "success": False,
            "message": str(e),
            "table": table_name
        }


def delete_table(db_path: str, table_name: str) -> Dict[str, Any]:
    """
    Deletes a table.

    Output:
        {
            "success": bool,
            "message": str,
            "table": str,
            "sql": str
        }
    """
    try:
        table_name = _validate_identifier(table_name)
        sql = f"DROP TABLE IF EXISTS {table_name}"

        conn = _connect(db_path)
        cur = conn.cursor()
        cur.execute(sql)
        conn.commit()
        conn.close()

        return {
            "success": True,
            "message": "Table deleted if it existed",
            "table": table_name,
            "sql": sql
        }
    except Exception as e:
        return {
            "success": False,
            "message": str(e),
            "table": table_name
        }


def insert_record(
    db_path: str,
    table_name: str,
    record: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Inserts one row.

    Example record:
        {
            "name": "Alice",
            "age": 25,
            "email": "alice@example.com"
        }

    Output:
        {
            "success": bool,
            "message": str,
            "table": str,
            "row_id": int | None,
            "sql": str,
            "values": list
        }
    """
    try:
        table_name = _validate_identifier(table_name)
        if not record:
            raise ValueError("record cannot be empty")

        columns = [_validate_identifier(col) for col in record.keys()]
        placeholders = ", ".join(["?"] * len(columns))
        col_sql = ", ".join(columns)
        values = list(record.values())

        sql = f"INSERT INTO {table_name} ({col_sql}) VALUES ({placeholders})"

        conn = _connect(db_path)
        cur = conn.cursor()
        cur.execute(sql, values)
        conn.commit()
        row_id = cur.lastrowid
        conn.close()

        return {
            "success": True,
            "message": "Record inserted",
            "table": table_name,
            "row_id": row_id,
            "sql": sql,
            "values": values
        }
    except Exception as e:
        return {
            "success": False,
            "message": str(e),
            "table": table_name,
            "row_id": None
        }


def query_table(
    db_path: str,
    table_name: str,
    columns: Optional[List[str]] = None,
    where: Optional[Dict[str, Any]] = None,
    order_by: Optional[str] = None,
    limit: Optional[int] = None
) -> Dict[str, Any]:
    """
    Queries rows from a table.

    Example:
        columns=["id", "name", "age"]
        where={"age": 25}
        order_by="id DESC"
        limit=5

    Output:
        {
            "success": bool,
            "message": str,
            "table": str,
            "count": int,
            "rows": list[dict],
            "sql": str,
            "values": list
        }
    """
    try:
        table_name = _validate_identifier(table_name)

        if columns:
            select_cols = ", ".join(_validate_identifier(c) for c in columns)
        else:
            select_cols = "*"

        sql = f"SELECT {select_cols} FROM {table_name}"
        values: List[Any] = []

        if where:
            clauses = []
            for col, val in where.items():
                col = _validate_identifier(col)
                clauses.append(f"{col} = ?")
                values.append(val)
            sql += " WHERE " + " AND ".join(clauses)

        if order_by:
            order_parts = order_by.strip().split()
            if len(order_parts) == 1:
                col = _validate_identifier(order_parts[0])
                sql += f" ORDER BY {col}"
            elif len(order_parts) == 2:
                col = _validate_identifier(order_parts[0])
                direction = order_parts[1].upper()
                if direction not in {"ASC", "DESC"}:
                    raise ValueError("order_by direction must be ASC or DESC")
                sql += f" ORDER BY {col} {direction}"
            else:
                raise ValueError("Invalid order_by format")

        if limit is not None:
            if limit < 0:
                raise ValueError("limit must be non negative")
            sql += " LIMIT ?"
            values.append(limit)

        conn = _connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(sql, values)
        rows = [dict(row) for row in cur.fetchall()]
        conn.close()

        return {
            "success": True,
            "message": "Query executed",
            "table": table_name,
            "count": len(rows),
            "rows": rows,
            "sql": sql,
            "values": values
        }
    except Exception as e:
        return {
            "success": False,
            "message": str(e),
            "table": table_name,
            "count": 0,
            "rows": []
        }


def update_record(
    db_path: str,
    table_name: str,
    updates: Dict[str, Any],
    where: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Updates rows.

    Example:
        updates={"age": 26, "email": "new@example.com"}
        where={"id": 1}

    Output:
        {
            "success": bool,
            "message": str,
            "table": str,
            "rows_updated": int,
            "sql": str,
            "values": list
        }
    """
    try:
        table_name = _validate_identifier(table_name)
        if not updates:
            raise ValueError("updates cannot be empty")
        if not where:
            raise ValueError("where cannot be empty for safety")

        set_clauses = []
        where_clauses = []
        values: List[Any] = []

        for col, val in updates.items():
            col = _validate_identifier(col)
            set_clauses.append(f"{col} = ?")
            values.append(val)

        for col, val in where.items():
            col = _validate_identifier(col)
            where_clauses.append(f"{col} = ?")
            values.append(val)

        sql = f"""
            UPDATE {table_name}
            SET {', '.join(set_clauses)}
            WHERE {' AND '.join(where_clauses)}
        """.strip()

        conn = _connect(db_path)
        cur = conn.cursor()
        cur.execute(sql, values)
        conn.commit()
        rows_updated = cur.rowcount
        conn.close()

        return {
            "success": True,
            "message": "Record updated",
            "table": table_name,
            "rows_updated": rows_updated,
            "sql": sql,
            "values": values
        }
    except Exception as e:
        return {
            "success": False,
            "message": str(e),
            "table": table_name,
            "rows_updated": 0
        }


def delete_record(
    db_path: str,
    table_name: str,
    where: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Deletes rows.

    Example:
        where={"id": 1}

    Output:
        {
            "success": bool,
            "message": str,
            "table": str,
            "rows_deleted": int,
            "sql": str,
            "values": list
        }
    """
    try:
        table_name = _validate_identifier(table_name)
        if not where:
            raise ValueError("where cannot be empty for safety")

        clauses = []
        values: List[Any] = []

        for col, val in where.items():
            col = _validate_identifier(col)
            clauses.append(f"{col} = ?")
            values.append(val)

        sql = f"DELETE FROM {table_name} WHERE {' AND '.join(clauses)}"

        conn = _connect(db_path)
        cur = conn.cursor()
        cur.execute(sql, values)
        conn.commit()
        rows_deleted = cur.rowcount
        conn.close()

        return {
            "success": True,
            "message": "Record deleted",
            "table": table_name,
            "rows_deleted": rows_deleted,
            "sql": sql,
            "values": values
        }
    except Exception as e:
        return {
            "success": False,
            "message": str(e),
            "table": table_name,
            "rows_deleted": 0
        }