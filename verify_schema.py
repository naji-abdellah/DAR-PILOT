"""Verify the schema was created correctly."""
import sqlite3
import sys
sys.path.insert(0, '.')

from backend.database import init_db, DB_PATH

init_db()
print(f"DB path: {DB_PATH}")

conn = sqlite3.connect(str(DB_PATH))
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [r[0] for r in cursor.fetchall()]
print("Tables:", tables)

expected = ['users', 'listings', 'leads', 'visits', 'audit_log']
missing = [t for t in expected if t not in tables]
if missing:
    print(f"ERROR: Missing tables: {missing}")
    sys.exit(1)
print("All 5 required tables present.")
conn.close()