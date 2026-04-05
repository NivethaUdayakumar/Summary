from pathlib import Path
import re
import sqlite3

ROOT = Path(__file__).resolve().parents[3]
IDENTIFIER_PATTERN = re.compile(r'^[A-Za-z_][A-Za-z0-9_-]*$')

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

def is_valid_identifier(value: str):
    return isinstance(value, str) and bool(IDENTIFIER_PATTERN.fullmatch(value))

def quote_identifier(value: str):
    if not is_valid_identifier(value):
        raise ValueError(f'invalid identifier: {value}')
    return f'"{value}"'

def table_exists(conn, table_name: str):
    cursor = conn.execute(
        'SELECT name FROM sqlite_master WHERE type = ? AND name = ?',
        ('table', table_name),
    )
    return cursor.fetchone() is not None

def get_table_schema(conn, table_name: str):
    cursor = conn.execute(f'PRAGMA table_info({quote_identifier(table_name)})')
    return [
        {
            'name': row['name'],
            'type': row['type'],
            'nullable': not bool(row['notnull']),
            'default_value': row['dflt_value'],
            'primary_key': bool(row['pk']),
        }
        for row in cursor.fetchall()
    ]

def read_table(data: dict):
    db_location = data.get('db_location')
    table_name = data.get('table_name')

    if not db_location:
        return {'success': False, 'error': 'db_location is required'}

    if not table_name:
        return {'success': False, 'error': 'table_name is required'}

    if not is_valid_identifier(table_name):
        return {'success': False, 'error': 'invalid table_name'}

    try:
        with get_connection(db_location) as conn:
            if not table_exists(conn, table_name):
                return {'success': False, 'error': f'table not found: {table_name}'}

            columns = get_table_schema(conn, table_name)
            if not columns:
                return {'success': False, 'error': f'no columns found for table: {table_name}'}

            quoted_table_name = quote_identifier(table_name)
            quoted_column_names = ', '.join(quote_identifier(column['name']) for column in columns)
            cursor = conn.execute(f'SELECT {quoted_column_names} FROM {quoted_table_name}')
            rows = [dict(row) for row in cursor.fetchall()]
    except (OSError, ValueError, sqlite3.Error) as error:
        return {'success': False, 'error': str(error)}

    return {
        'success': True,
        'db_location': db_location,
        'table_name': table_name,
        'columns': columns,
        'rows': rows,
    }

def create_table(data: dict):
    db_location = data.get('db_location')
    table_name = data.get('table_name')
    columns = data.get('columns')
    if not db_location:
        return {'success': False, 'error': 'db_location is required'}
    if not table_name:
        return {'success': False, 'error': 'table_name is required'}
    if not is_valid_identifier(table_name):
        return {'success': False, 'error': 'invalid table_name'}
    if not isinstance(columns, dict) or not columns:
        return {'success': False, 'error': 'columns must be a non-empty object'}
    try:
        column_defs = ', '.join(f'{quote_identifier(name)} {dtype}' for name, dtype in columns.items())
        with get_connection(db_location) as conn:
            conn.execute(f'CREATE TABLE IF NOT EXISTS {quote_identifier(table_name)} ({column_defs})')
            conn.commit()
    except (OSError, ValueError, sqlite3.Error) as error:
        return {'success': False, 'error': str(error)}
    return {'success': True, 'table_name': table_name, 'db_location': db_location}

def delete_table(data: dict):
    db_location = data.get('db_location')
    table_name = data.get('table_name')
    if not db_location:
        return {'success': False, 'error': 'db_location is required'}
    if not table_name:
        return {'success': False, 'error': 'table_name is required'}
    if not is_valid_identifier(table_name):
        return {'success': False, 'error': 'invalid table_name'}
    try:
        with get_connection(db_location) as conn:
            conn.execute(f'DROP TABLE IF EXISTS {quote_identifier(table_name)}')
            conn.commit()
    except (OSError, ValueError, sqlite3.Error) as error:
        return {'success': False, 'error': str(error)}
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
    if not db_location:
        return {'success': False, 'error': 'db_location is required'}
    if not table_name or not isinstance(record, dict) or not record:
        return {'success': False, 'error': 'table_name and record are required'}
    if not is_valid_identifier(table_name):
        return {'success': False, 'error': 'invalid table_name'}
    try:
        columns = ', '.join(quote_identifier(name) for name in record.keys())
        placeholders = ', '.join('?' for _ in record)
        values = tuple(record.values())
        with get_connection(db_location) as conn:
            conn.execute(
                f'INSERT INTO {quote_identifier(table_name)} ({columns}) VALUES ({placeholders})',
                values,
            )
            conn.commit()
    except (OSError, ValueError, sqlite3.Error) as error:
        return {'success': False, 'error': str(error)}
    return {'success': True, 'table_name': table_name, 'db_location': db_location}

def update_record(data: dict):
    db_location = data.get('db_location')
    table_name = data.get('table_name')
    updates = data.get('updates') or data.get('record')
    criteria = data.get('criteria')
    if not db_location:
        return {'success': False, 'error': 'db_location is required'}
    if not table_name or not isinstance(updates, dict) or not updates:
        return {'success': False, 'error': 'table_name and updates are required'}
    if not isinstance(criteria, dict) or not criteria:
        return {'success': False, 'error': 'criteria is required'}
    if not is_valid_identifier(table_name):
        return {'success': False, 'error': 'invalid table_name'}
    try:
        assignments = ', '.join(f'{quote_identifier(key)} = ?' for key in updates)
        conditions = ' AND '.join(f'{quote_identifier(key)} = ?' for key in criteria)
        values = tuple(updates.values()) + tuple(criteria.values())
        with get_connection(db_location) as conn:
            cursor = conn.execute(
                f'UPDATE {quote_identifier(table_name)} SET {assignments} WHERE {conditions}',
                values,
            )
            conn.commit()
    except (OSError, ValueError, sqlite3.Error) as error:
        return {'success': False, 'error': str(error)}
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
    if not db_location:
        return {'success': False, 'error': 'db_location is required'}
    if not table_name or not isinstance(criteria, dict) or not criteria:
        return {'success': False, 'error': 'table_name and criteria are required'}
    if not is_valid_identifier(table_name):
        return {'success': False, 'error': 'invalid table_name'}
    try:
        conditions = ' AND '.join(f'{quote_identifier(key)} = ?' for key in criteria)
        values = tuple(criteria.values())
        with get_connection(db_location) as conn:
            conn.execute(f'DELETE FROM {quote_identifier(table_name)} WHERE {conditions}', values)
            conn.commit()
    except (OSError, ValueError, sqlite3.Error) as error:
        return {'success': False, 'error': str(error)}
    return {'success': True, 'table_name': table_name, 'db_location': db_location}
