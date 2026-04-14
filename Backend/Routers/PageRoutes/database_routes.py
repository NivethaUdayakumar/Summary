import json
import os
import sqlite3

TEMPLATE_DIR = os.path.join("AppData", "Templates")
MAX_PREVIEW_ROWS = 100

def ensure_parent_dir(file_path):
    parent = os.path.dirname(file_path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def connect_db(db_path):
    ensure_parent_dir(db_path)
    conn = sqlite3.connect(db_path, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout = 10000")
    return conn


def normalize_name(name):
    if not name:
        raise Exception("Name is required")
    if '"' in name or ';' in name:
        raise Exception("Invalid name")
    return name


def quote_identifier(name):
    return '"' + str(name).replace('"', '""') + '"'


def get_db_info(db_path):
    if not db_path:
        raise Exception("db_path is required")

    if not os.path.exists(db_path):
        ensure_parent_dir(db_path)
        sqlite3.connect(db_path).close()

    file_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0

    conn = connect_db(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = cur.fetchall()
    conn.close()

    return {
        "success": True,
        "info": {
            "db_path": db_path,
            "exists": True,
            "file_size_bytes": file_size,
            "table_count": len(tables)
        }
    }


def get_table_names(conn):
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
    return [{"name": row["name"]} for row in cur.fetchall()]


def get_create_sql(conn, table_name):
    table_name = normalize_name(table_name)
    cur = conn.cursor()
    cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name = ?", (table_name,))
    row = cur.fetchone()
    return row["sql"] if row and row["sql"] else ""


def get_table_schema(conn, table_name):
    table_name = normalize_name(table_name)
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({quote_identifier(table_name)})")
    cols = cur.fetchall()
    create_sql = get_create_sql(conn, table_name).upper()

    result_cols = []
    for row in cols:
        col_name = row["name"]
        auto = False

        pattern1 = f'"{col_name.upper()}" INTEGER PRIMARY KEY AUTOINCREMENT'
        pattern2 = f'{col_name.upper()} INTEGER PRIMARY KEY AUTOINCREMENT'

        if row["pk"] and "AUTOINCREMENT" in create_sql and (pattern1 in create_sql or pattern2 in create_sql):
            auto = True

        result_cols.append({
            "cid": row["cid"],
            "name": row["name"],
            "type": row["type"],
            "notnull": row["notnull"],
            "default_value": row["dflt_value"],
            "pk": row["pk"],
            "autoincrement": auto
        })

    return {
        "success": True,
        "schema": {
            "table_name": table_name,
            "columns": result_cols
        }
    }


def get_table_data(conn, table_name, limit=MAX_PREVIEW_ROWS):
    table_name = normalize_name(table_name)
    limit = max(1, int(limit))
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) AS cnt FROM {quote_identifier(table_name)}")
    total_rows = cur.fetchone()["cnt"]
    cur.execute(f"SELECT * FROM {quote_identifier(table_name)} LIMIT ?", (limit + 1,))
    rows = cur.fetchall()
    has_more = len(rows) > limit
    preview_rows = rows[:limit]
    return {
        "success": True,
        "rows": [dict(row) for row in preview_rows],
        "total_rows": total_rows,
        "displayed_rows": len(preview_rows),
        "row_limit": limit,
        "has_more": has_more
    }


def create_table_with_default_id(conn, table_name):
    table_name = normalize_name(table_name)
    cur = conn.cursor()
    cur.execute(f"CREATE TABLE IF NOT EXISTS {quote_identifier(table_name)} (id INTEGER PRIMARY KEY AUTOINCREMENT)")
    conn.commit()


def export_schema(conn):
    schema = {"tables": []}
    tables = get_table_names(conn)

    for table in tables:
        table_schema = get_table_schema(conn, table["name"])["schema"]
        schema["tables"].append(table_schema)

    return schema


def build_column_definition(data):
    column_name = normalize_name(data.get("column_name", ""))
    column_type = (data.get("column_type", "TEXT") or "TEXT").upper().strip()
    not_null = bool(data.get("not_null", False))
    primary_key = bool(data.get("primary_key", False))
    autoincrement = bool(data.get("autoincrement", False))
    default_value = data.get("default_value", "")

    parts = [quote_identifier(column_name), column_type]

    if primary_key:
        parts.append("PRIMARY KEY")

    if autoincrement:
        if column_type != "INTEGER" or not primary_key:
            raise Exception("AUTOINCREMENT requires INTEGER PRIMARY KEY")
        parts.append("AUTOINCREMENT")

    if not_null:
        parts.append("NOT NULL")

    if str(default_value).strip() != "":
        if column_type in ["INTEGER", "REAL", "NUMERIC"]:
            parts.append(f"DEFAULT {default_value}")
        else:
            escaped_default = str(default_value).replace("'", "''")
            parts.append(f"DEFAULT '{escaped_default}'")

    return " ".join(parts)


def add_column(conn, table_name, data):
    table_name = normalize_name(table_name)
    cur = conn.cursor()
    col_def = build_column_definition(data)

    if "PRIMARY KEY" in col_def or "AUTOINCREMENT" in col_def:
        rebuild_table_with_added_column(conn, table_name, col_def)
    else:
        cur.execute(f"ALTER TABLE {quote_identifier(table_name)} ADD COLUMN {col_def}")
        conn.commit()


def rebuild_table_with_added_column(conn, table_name, new_col_def):
    schema = get_table_schema(conn, table_name)["schema"]["columns"]

    old_cols_sql = []
    old_col_names = []

    for col in schema:
        part = [quote_identifier(col["name"]), col["type"] or "TEXT"]

        if col["pk"]:
            part.append("PRIMARY KEY")

        if col.get("autoincrement"):
            part.append("AUTOINCREMENT")

        if col["notnull"]:
            part.append("NOT NULL")

        if col["default_value"] is not None:
            part.append(f"DEFAULT {col['default_value']}")

        old_cols_sql.append(" ".join(part))
        old_col_names.append(quote_identifier(col["name"]))

    all_defs = old_cols_sql + [new_col_def]
    old_cols_csv = ", ".join(old_col_names)
    temp_name = f"{table_name}__temp_addcol"

    cur = conn.cursor()
    cur.execute(f"CREATE TABLE {quote_identifier(temp_name)} ({', '.join(all_defs)})")
    cur.execute(
        f"INSERT INTO {quote_identifier(temp_name)} ({old_cols_csv}) SELECT {old_cols_csv} FROM {quote_identifier(table_name)}"
    )
    cur.execute(f"DROP TABLE {quote_identifier(table_name)}")
    cur.execute(f"ALTER TABLE {quote_identifier(temp_name)} RENAME TO {quote_identifier(table_name)}")
    conn.commit()


def remove_column_sqlite(conn, table_name, column_name):
    table_name = normalize_name(table_name)
    column_name = normalize_name(column_name)

    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({quote_identifier(table_name)})")
    cols = cur.fetchall()

    remaining = [c for c in cols if c["name"] != column_name]

    if len(remaining) == len(cols):
        raise Exception("Column not found")

    if not remaining:
        raise Exception("Cannot remove all columns")

    create_sql = get_create_sql(conn, table_name).upper()
    temp_table = f"{table_name}__temp__rebuild"

    col_defs = []
    col_names = []

    for c in remaining:
        part = f'{quote_identifier(c["name"])} {c["type"] or "TEXT"}'

        if c["pk"]:
            part += " PRIMARY KEY"
            if "AUTOINCREMENT" in create_sql:
                part += " AUTOINCREMENT"

        if c["notnull"]:
            part += " NOT NULL"

        if c["dflt_value"] is not None:
            part += f' DEFAULT {c["dflt_value"]}'

        col_defs.append(part)
        col_names.append(quote_identifier(c["name"]))

    col_defs_sql = ", ".join(col_defs)
    col_names_sql = ", ".join(col_names)

    cur.execute(f"CREATE TABLE {quote_identifier(temp_table)} ({col_defs_sql})")
    cur.execute(
        f"INSERT INTO {quote_identifier(temp_table)} ({col_names_sql}) SELECT {col_names_sql} FROM {quote_identifier(table_name)}"
    )
    cur.execute(f"DROP TABLE {quote_identifier(table_name)}")
    cur.execute(f"ALTER TABLE {quote_identifier(temp_table)} RENAME TO {quote_identifier(table_name)}")
    conn.commit()


def cast_value_for_column(value, col_type):
    if value is None or value == "":
        return None

    t = str(col_type or "").upper()

    if "INT" in t:
        return int(value)

    if "REAL" in t or "FLOAT" in t or "DOUBLE" in t or "NUMERIC" in t or "DECIMAL" in t:
        return float(value)

    return value


def get_schema_map(conn, table_name):
    schema = get_table_schema(conn, table_name)["schema"]["columns"]
    return {c["name"]: c for c in schema}


def insert_record(conn, table_name, record):
    table_name = normalize_name(table_name)
    schema_map = get_schema_map(conn, table_name)

    cols = []
    vals = []

    for key, value in record.items():
        if key not in schema_map:
            continue
        cols.append(quote_identifier(key))
        vals.append(cast_value_for_column(value, schema_map[key]["type"]))

    if not cols:
        raise Exception("Record is empty")

    placeholders = ", ".join(["?"] * len(cols))
    cols_sql = ", ".join(cols)

    cur = conn.cursor()
    cur.execute(f"INSERT INTO {quote_identifier(table_name)} ({cols_sql}) VALUES ({placeholders})", vals)
    conn.commit()
    return cur.lastrowid


def build_where_clause(where, schema_map):
    if not where:
        return "", []

    parts = []
    values = []

    for key, value in where.items():
        if key not in schema_map:
            continue
        parts.append(f"{quote_identifier(key)} = ?")
        values.append(cast_value_for_column(value, schema_map[key]["type"]))

    if not parts:
        return "", []

    return " WHERE " + " AND ".join(parts), values


def update_record(conn, table_name, set_values, where):
    table_name = normalize_name(table_name)
    schema_map = get_schema_map(conn, table_name)

    if not set_values:
        raise Exception("set_values is empty")

    set_parts = []
    values = []

    for key, value in set_values.items():
        if key not in schema_map:
            continue
        set_parts.append(f"{quote_identifier(key)} = ?")
        values.append(cast_value_for_column(value, schema_map[key]["type"]))

    if not set_parts:
        raise Exception("No valid columns to update")

    where_sql, where_vals = build_where_clause(where, schema_map)

    if not where_sql:
        raise Exception("Update requires where condition")

    values.extend(where_vals)

    cur = conn.cursor()
    cur.execute(f"UPDATE {quote_identifier(table_name)} SET {', '.join(set_parts)}{where_sql}", values)
    conn.commit()
    return cur.rowcount


def delete_record(conn, table_name, where):
    table_name = normalize_name(table_name)
    schema_map = get_schema_map(conn, table_name)

    where_sql, values = build_where_clause(where, schema_map)

    if not where_sql:
        raise Exception("Delete requires where condition")

    cur = conn.cursor()
    cur.execute(f"DELETE FROM {quote_identifier(table_name)}{where_sql}", values)
    conn.commit()
    return cur.rowcount


def run_query(conn, sql, row_limit=MAX_PREVIEW_ROWS):
    if not str(sql).strip():
        raise Exception("SQL is required")

    row_limit = max(1, int(row_limit))
    cur = conn.cursor()
    cur.execute(sql)

    if cur.description:
        rows = cur.fetchmany(row_limit + 1)
        has_more = len(rows) > row_limit
        preview_rows = rows[:row_limit]
        message = f"Query executed. Showing {len(preview_rows)} row(s)."
        if has_more:
            message = f"{message} Preview limited to the first {row_limit} rows."
        return {
            "success": True,
            "rows": [dict(row) for row in preview_rows],
            "message": message,
            "displayed_rows": len(preview_rows),
            "row_limit": row_limit,
            "has_more": has_more
        }

    conn.commit()
    return {
        "success": True,
        "rows": [],
        "message": f"Query executed. Rows affected: {cur.rowcount}"
    }


def save_template(db_path, template_name):
    os.makedirs(TEMPLATE_DIR, exist_ok=True)

    conn = connect_db(db_path)
    schema = export_schema(conn)
    conn.close()

    if not template_name.endswith(".json"):
        template_name += ".json"

    template_path = os.path.join(TEMPLATE_DIR, template_name)
    with open(template_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2)

    return {
        "success": True,
        "template_name": template_name
    }


def list_templates():
    os.makedirs(TEMPLATE_DIR, exist_ok=True)
    return {
        "success": True,
        "templates": sorted([f for f in os.listdir(TEMPLATE_DIR) if f.endswith(".json")])
    }


def create_db_from_template(template_name, new_db_path):
    if not template_name.endswith(".json"):
        template_name += ".json"

    template_path = os.path.join(TEMPLATE_DIR, template_name)
    if not os.path.exists(template_path):
        raise Exception("Template not found")

    with open(template_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    ensure_parent_dir(new_db_path)
    conn = connect_db(new_db_path)
    cur = conn.cursor()

    for table in schema.get("tables", []):
        col_defs = []

        for col in table.get("columns", []):
            part = [quote_identifier(col["name"]), col.get("type") or "TEXT"]

            if col.get("pk"):
                part.append("PRIMARY KEY")

            if col.get("autoincrement"):
                part.append("AUTOINCREMENT")

            if col.get("notnull"):
                part.append("NOT NULL")

            if col.get("default_value") is not None:
                part.append(f'DEFAULT {col["default_value"]}')

            col_defs.append(" ".join(part))

        if not col_defs:
            col_defs = ['"id" INTEGER PRIMARY KEY AUTOINCREMENT']

        cur.execute(f"CREATE TABLE IF NOT EXISTS {quote_identifier(table['table_name'])} ({', '.join(col_defs)})")

    conn.commit()
    conn.close()

    return {
        "success": True,
        "new_db_path": new_db_path
    }


def handle_database_route(action, data):
    conn = None
    try:
        if action == "open":
            return get_db_info(data.get("db_path", ""))

        if action == "info":
            return get_db_info(data.get("db_path", ""))

        if action == "tables":
            conn = connect_db(data.get("db_path", ""))
            tables = get_table_names(conn)
            return {
                "success": True,
                "tables": tables,
                "preview_row_limit": MAX_PREVIEW_ROWS
            }

        if action == "table_schema":
            conn = connect_db(data.get("db_path", ""))
            return get_table_schema(conn, data.get("table_name", ""))

        if action == "table_data":
            conn = connect_db(data.get("db_path", ""))
            return get_table_data(conn, data.get("table_name", ""))

        if action == "create_table":
            conn = connect_db(data.get("db_path", ""))
            create_table_with_default_id(conn, data.get("table_name", ""))
            return {"success": True}

        if action == "delete_table":
            conn = connect_db(data.get("db_path", ""))
            table_name = normalize_name(data.get("table_name", ""))
            cur = conn.cursor()
            cur.execute(f"DROP TABLE IF EXISTS {quote_identifier(table_name)}")
            conn.commit()
            return {"success": True}

        if action == "add_column":
            conn = connect_db(data.get("db_path", ""))
            add_column(conn, data.get("table_name", ""), data)
            return {"success": True}

        if action == "remove_column":
            conn = connect_db(data.get("db_path", ""))
            remove_column_sqlite(conn, data.get("table_name", ""), data.get("column_name", ""))
            return {"success": True}

        if action == "insert_record":
            conn = connect_db(data.get("db_path", ""))
            rowid = insert_record(conn, data.get("table_name", ""), data.get("record", {}))
            return {"success": True, "last_row_id": rowid}

        if action == "update_record":
            conn = connect_db(data.get("db_path", ""))
            count = update_record(conn, data.get("table_name", ""), data.get("set_values", {}), data.get("where", {}))
            return {"success": True, "updated_count": count}

        if action == "delete_record":
            conn = connect_db(data.get("db_path", ""))
            count = delete_record(conn, data.get("table_name", ""), data.get("where", {}))
            return {"success": True, "deleted_count": count}

        if action == "query":
            conn = connect_db(data.get("db_path", ""))
            return run_query(conn, data.get("sql", ""))

        if action == "save_template":
            return save_template(data.get("db_path", ""), data.get("template_name", ""))

        if action == "list_templates":
            return list_templates()

        if action == "create_from_template":
            return create_db_from_template(data.get("template_name", ""), data.get("new_db_path", ""))

        return {
            "success": False,
            "error": f"Unknown action: {action}"
        }

    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except:
                pass
        return {
            "success": False,
            "error": str(e)
        }

    finally:
        if conn:
            try:
                conn.close()
            except:
                pass
