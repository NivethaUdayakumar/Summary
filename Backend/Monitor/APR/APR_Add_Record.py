from Backend.Monitor.APR.APR_DB_Common import get_conn


def Add_record(dbname, tablename, columns_tuple, columns_value) -> int:
    columns_sql = ", ".join(columns_tuple)
    placeholders = ", ".join(["?"] * len(columns_tuple))

    with get_conn(dbname) as conn:
        cur = conn.execute(
            f"""
            INSERT INTO {tablename} ({columns_sql})
            VALUES ({placeholders})
            """,
            tuple(columns_value),
        )
        conn.commit()
        return cur.lastrowid