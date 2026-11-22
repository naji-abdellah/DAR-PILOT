"""SQLite connection management for DarPilot.

All database access goes through ``get_connection()``. Connections use
``sqlite3.Row`` so results are accessible by column name, and every
parameter is passed via ``?`` placeholders — never interpolated into
SQL strings.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path


def _get_db_path() -> Path:
    """Get the database path, reading from env var each time for test isolation."""
    return Path(os.environ.get("DARPILOT_DB_PATH", Path(__file__).resolve().parent.parent / "darpilot.db"))


@contextmanager
def get_connection():
    """Yield an open SQLite connection, closing it when done."""
    conn = sqlite3.connect(str(_get_db_path()))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db(schema_path: str | Path | None = None) -> None:
    """Create tables from the SQL schema file if they do not exist."""
    if schema_path is None:
        schema_path = Path(__file__).resolve().parent / "schema.sql"
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    with get_connection() as conn:
        conn.executescript(schema_sql)
        conn.commit()


# Backward compatibility: DB_PATH as a property-like object
class _DBPath:
    def __str__(self):
        return str(_get_db_path())
    def __fspath__(self):
        return str(_get_db_path())

DB_PATH = _DBPath()
