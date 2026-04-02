from pathlib import Path
import sqlite3

DB_PATH = Path(__file__).resolve().parents[3] / 'AppData' / 'App.db'

def get_connection():
    return sqlite3.connect(DB_PATH)

def row_to_user(row):
    if row is None:
        return None
    return {'user_id': row[0], 'role': row[1], 'password': row[2]}

def get_user(user_id: str):
    with get_connection() as conn:
        cursor = conn.execute(
            'SELECT user_id, role, password FROM users WHERE user_id = ?', (user_id,)
        )
        return row_to_user(cursor.fetchone())

def create_user(user_id: str, role: str, password: str):
    with get_connection() as conn:
        conn.execute(
            'INSERT INTO users (user_id, role, password) VALUES (?, ?, ?)',
            (user_id, role, password),
        )
        conn.commit()

def validate_user(user_id: str, password: str):
    user = get_user(user_id)
    return user if user and user['password'] == password else None

def get_all_users():
    with get_connection() as conn:
        cursor = conn.execute('SELECT user_id, role FROM users ORDER BY user_id')
        return [{'user_id': row[0], 'role': row[1]} for row in cursor.fetchall()]

def update_user_role(user_id: str, role: str):
    with get_connection() as conn:
        cursor = conn.execute(
            'UPDATE users SET role = ? WHERE user_id = ?',
            (role, user_id),
        )
        conn.commit()
        return cursor.rowcount > 0

def update_user_password(user_id: str, password: str):
    with get_connection() as conn:
        cursor = conn.execute(
            'UPDATE users SET password = ? WHERE user_id = ?',
            (password, user_id),
        )
        conn.commit()
        return cursor.rowcount > 0

def delete_user(user_id: str):
    with get_connection() as conn:
        cursor = conn.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
        conn.commit()
        return cursor.rowcount > 0
