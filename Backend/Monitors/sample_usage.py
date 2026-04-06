from pprint import pprint

from db_utils import (
    create_db,
    delete_db,
    create_table,
    delete_table,
    query_table,
    insert_record,
    delete_record,
    update_record,
)

DB_PATH = "sample_app.db"
TABLE_NAME = "users"


def line():
    print("\n" + "=" * 70 + "\n")


print("1. create_db")
print("Sample input")
print('create_db("sample_app.db")')
result = create_db(DB_PATH)
print("Sample output")
pprint(result)
line()


print("2. create_table")
print("Sample input")
print("""
create_table(
    "sample_app.db",
    "users",
    {
        "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
        "name": "TEXT NOT NULL",
        "age": "INTEGER",
        "email": "TEXT UNIQUE"
    }
)
""")
result = create_table(
    DB_PATH,
    TABLE_NAME,
    {
        "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
        "name": "TEXT NOT NULL",
        "age": "INTEGER",
        "email": "TEXT UNIQUE"
    }
)
print("Sample output")
pprint(result)
line()


print("3. insert_record")
print("Sample input")
print("""
insert_record(
    "sample_app.db",
    "users",
    {
        "name": "Alice",
        "age": 25,
        "email": "alice@example.com"
    }
)
""")
result = insert_record(
    DB_PATH,
    TABLE_NAME,
    {
        "name": "Alice",
        "age": 25,
        "email": "alice@example.com"
    }
)
print("Sample output")
pprint(result)
line()


print("4. insert_record again")
result = insert_record(
    DB_PATH,
    TABLE_NAME,
    {
        "name": "Bob",
        "age": 30,
        "email": "bob@example.com"
    }
)
pprint(result)
line()


print("5. query_table all rows")
print("Sample input")
print("""
query_table(
    "sample_app.db",
    "users"
)
""")
result = query_table(DB_PATH, TABLE_NAME)
print("Sample output")
pprint(result)
line()


print("6. query_table with filter")
print("Sample input")
print("""
query_table(
    "sample_app.db",
    "users",
    columns=["id", "name", "age"],
    where={"age": 25},
    order_by="id DESC",
    limit=5
)
""")
result = query_table(
    DB_PATH,
    TABLE_NAME,
    columns=["id", "name", "age"],
    where={"age": 25},
    order_by="id DESC",
    limit=5
)
print("Sample output")
pprint(result)
line()


print("7. update_record")
print("Sample input")
print("""
update_record(
    "sample_app.db",
    "users",
    updates={"age": 26},
    where={"name": "Alice"}
)
""")
result = update_record(
    DB_PATH,
    TABLE_NAME,
    updates={"age": 26},
    where={"name": "Alice"}
)
print("Sample output")
pprint(result)
line()


print("8. query_table after update")
result = query_table(DB_PATH, TABLE_NAME)
pprint(result)
line()


print("9. delete_record")
print("Sample input")
print("""
delete_record(
    "sample_app.db",
    "users",
    where={"name": "Bob"}
)
""")
result = delete_record(
    DB_PATH,
    TABLE_NAME,
    where={"name": "Bob"}
)
print("Sample output")
pprint(result)
line()


print("10. query_table after delete")
result = query_table(DB_PATH, TABLE_NAME)
pprint(result)
line()


print("11. delete_table")
print("Sample input")
print('delete_table("sample_app.db", "users")')
result = delete_table(DB_PATH, TABLE_NAME)
print("Sample output")
pprint(result)
line()


print("12. delete_db")
print("Sample input")
print('delete_db("sample_app.db")')
result = delete_db(DB_PATH)
print("Sample output")
pprint(result)
line()