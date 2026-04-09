from APR_DB_Common import get_conn


def Get_record_id(key: str, dbname: str, tablename: str):
    with get_conn(dbname) as conn:
        row = conn.execute(
            f'SELECT id FROM "{tablename}" WHERE record_key = ?',
            (key,),
        ).fetchone()
        return row["id"] if row else None