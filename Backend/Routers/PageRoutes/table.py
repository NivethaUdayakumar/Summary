from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[3]

def resolve_db_path(db_location: str):
    if not db_location:
        raise ValueError('db_location is required')
    path = Path(db_location)
    return path if path.is_absolute() else (ROOT / db_location).resolve()

def get_connection(db_location: str):
    db_path = resolve_db_path(db_location)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def create_table(data: dict):
    db_location = data.get('db_location')
    table_name = data.get('table_name')
    columns = data.get('columns')
    if not table_name:
        return {'success': False, 'error': 'table_name is required'}
    if not isinstance(columns, dict) or not columns:
        return {'success': False, 'error': 'columns must be a non-empty object'}
    column_defs = ', '.join(f'{name} {dtype}' for name, dtype in columns.items())
    with get_connection(db_location) as conn:
        conn.execute(f'CREATE TABLE IF NOT EXISTS {table_name} ({column_defs})')
        conn.commit()
    return {'success': True, 'table_name': table_name, 'db_location': db_location}

def delete_table(data: dict):
    db_location = data.get('db_location')
    table_name = data.get('table_name')
    if not table_name:
        return {'success': False, 'error': 'table_name is required'}
    with get_connection(db_location) as conn:
        conn.execute(f'DROP TABLE IF EXISTS {table_name}')
        conn.commit()
    return {'success': True, 'table_name': table_name, 'db_location': db_location}

def query_table(data: dict):
    db_location = data.get('db_location')
    query = data.get('query')
    params = data.get('params', [])
    if not query:
        return {'success': False, 'error': 'query is required'}
    with get_connection(db_location) as conn:
        cursor = conn.execute(query, params or [])
        rows = [dict(row) for row in cursor.fetchall()]
    return {'success': True, 'query': query, 'rows': rows}

def insert_record(data: dict):
    db_location = data.get('db_location')
    table_name = data.get('table_name')
    record = data.get('record')
    if not table_name or not isinstance(record, dict) or not record:
        return {'success': False, 'error': 'table_name and record are required'}
    columns = ', '.join(record.keys())
    placeholders = ', '.join('?' for _ in record)
    values = tuple(record.values())
    with get_connection(db_location) as conn:
        conn.execute(
            f'INSERT INTO {table_name} ({columns}) VALUES ({placeholders})',
            values,
        )
        conn.commit()
    return {'success': True, 'table_name': table_name, 'db_location': db_location}

def update_record(data: dict):
    db_location = data.get('db_location')
    table_name = data.get('table_name')
    updates = data.get('updates') or data.get('record')
    criteria = data.get('criteria')
    if not table_name or not isinstance(updates, dict) or not updates:
        return {'success': False, 'error': 'table_name and updates are required'}
    if not isinstance(criteria, dict) or not criteria:
        return {'success': False, 'error': 'criteria is required'}
    assignments = ', '.join(f'{key} = ?' for key in updates)
    conditions = ' AND '.join(f'{key} = ?' for key in criteria)
    values = tuple(updates.values()) + tuple(criteria.values())
    with get_connection(db_location) as conn:
        cursor = conn.execute(
            f'UPDATE {table_name} SET {assignments} WHERE {conditions}',
            values,
        )
        conn.commit()
    return {
        'success': True,
        'table_name': table_name,
        'db_location': db_location,
        'updated_count': cursor.rowcount,
    }

def delete_record(data: dict):
    db_location = data.get('db_location')
    table_name = data.get('table_name')
    criteria = data.get('criteria') or data.get('record')
    if not table_name or not isinstance(criteria, dict) or not criteria:
        return {'success': False, 'error': 'table_name and criteria are required'}
    conditions = ' AND '.join(f"{key} = ?" for key in criteria)
    values = tuple(criteria.values())
    with get_connection(db_location) as conn:
        conn.execute(f'DELETE FROM {table_name} WHERE {conditions}', values)
        conn.commit()
    return {'success': True, 'table_name': table_name, 'db_location': db_location}
