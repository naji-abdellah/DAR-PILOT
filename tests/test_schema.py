"""Tests for the M1 database schema.

Verifies that all required tables exist and that CHECK/NOT NULL
constraints reject invalid data. Every insert uses parameterized
queries via `?` placeholders.
"""

import os
import sys
import sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.database import init_db, DB_PATH


def test_all_required_tables_exist():
    """users, listings, leads, visits, audit_log must all be present."""
    init_db()
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = {r[0] for r in cursor.fetchall()}
    conn.close()

    expected = {"users", "listings", "leads", "visits", "audit_log"}
    assert expected.issubset(tables), f"Missing tables: {expected - tables}"


def test_users_check_constraint_rejects_invalid_role():
    """Inserting a user with an invalid role must raise IntegrityError."""
    init_db()
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (username, email, password_hash, role) "
            "VALUES (?, ?, ?, ?)",
            ("bob", "bob@example.com", "hash", "superuser"),
        )
        conn.commit()
        assert False, "Expected IntegrityError for invalid role"
    except sqlite3.IntegrityError:
        conn.rollback()
    finally:
        conn.close()


def test_listings_price_mad_check_constraint_rejects_negative():
    """Negative price_mad must be rejected by CHECK constraint."""
    init_db()
    # Create a valid agent first
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
        ("agent1", "agent1@example.com", "hash", "agent"),
    )
    agent_id = cursor.lastrowid
    conn.commit()

    try:
        cursor.execute(
            "INSERT INTO listings (title, description, price_mad, city, property_type, status, agent_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("Bad", "desc", -1000, "Casablanca", "apartment", "available", agent_id),
        )
        conn.commit()
        assert False, "Expected IntegrityError for negative price"
    except sqlite3.IntegrityError:
        conn.rollback()
    finally:
        conn.close()


def test_parameterized_insert_and_select():
    """A parameterized insert followed by a select must round-trip."""
    init_db()
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
        ("alice", "alice@example.com", "hash", "viewer"),
    )
    user_id = cursor.lastrowid

    cursor.execute(
        "INSERT INTO leads (name, phone, email, message, listing_id, status) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("Youssef", "0612345678", "youssef@example.com", "Interested in listing", None, "new"),
    )
    lead_id = cursor.lastrowid
    conn.commit()

    cursor.execute("SELECT name, status FROM leads WHERE id = ?", (lead_id,))
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == "Youssef"
    assert row[1] == "new"

    conn.close()