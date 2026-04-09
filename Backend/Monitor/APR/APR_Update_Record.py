from APR_DB_Common import get_conn


def Update_record(record_id, dbname, tablename, columns_tuple, columns_value) -> None:
    set_sql = ", ".join([f'{col} = ?' for col in columns_tuple])

    with get_conn(dbname) as conn:
        conn.execute(
            f'UPDATE "{tablename}" SET {set_sql} WHERE id = ?',
            tuple(columns_value) + (record_id,),
        )
        conn.commit()