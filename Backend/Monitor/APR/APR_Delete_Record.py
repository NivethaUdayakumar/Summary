from APR_DB_Common import get_conn


def Delete_record(record_id: int, dbname: str, tablename: str) -> None:
    with get_conn(dbname) as conn:
        conn.execute(
            f'DELETE FROM "{tablename}" WHERE id = ?',
            (record_id,),
        )
        conn.commit()