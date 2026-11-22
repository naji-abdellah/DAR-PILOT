"""Repository layer for DarPilot database access.

All functions use parameterized queries (``?`` placeholders) via
``database.get_connection()``. No raw SQL strings are built from user
input, which blocks SQL injection.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional

from backend.database import get_connection

VALID_ROLES = ("admin", "agent", "viewer")
VALID_LISTING_STATUSES = ("available", "sold", "pending")
VALID_LEAD_STATUSES = ("new", "contacted", "closed")
VALID_VISIT_STATUSES = ("scheduled", "completed", "cancelled")


def _row_to_dict(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
    """Convert an ``sqlite3.Row`` into a plain dict (or ``None``)."""
    return dict(row) if row is not None else None


def _rows_to_dicts(rows: List[sqlite3.Row]) -> List[Dict[str, Any]]:
    """Convert a list of ``sqlite3.Row`` into plain dicts."""
    return [dict(r) for r in rows]


# ── Users ────────────────────────────────────────────────────────────────

def create_user(username: str, email: str, password_hash: str, role: str = "agent") -> int:
    """Insert a new user and return the generated ``id``."""
    if role not in VALID_ROLES:
        raise ValueError(f"Invalid role: {role!r}. Must be one of: {VALID_ROLES}")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
            (username, email, password_hash, role),
        )
        user_id = cursor.lastrowid
        conn.commit()
    return user_id


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """Fetch a user row by username. Returns ``None`` if not found."""
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        return _row_to_dict(cursor.fetchone())


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a user row by primary key. Returns ``None`` if not found."""
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        return _row_to_dict(cursor.fetchone())

def create_listing(
    title: str,
    description: str,
    price_mad: int,
    city: str,
    neighborhood: str,
    property_type: str,
    status: str = "available",
    agent_id: Optional[int] = None,
) -> int:
    """Insert a new listing and return the generated ``id``."""
    if status not in VALID_LISTING_STATUSES:
        raise ValueError(f"Invalid status: {status!r}. Must be one of: {VALID_LISTING_STATUSES}")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO listings
               (title, description, price_mad, city, neighborhood, property_type, status, agent_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (title, description, price_mad, city, neighborhood, property_type, status, agent_id),
        )
        listing_id = cursor.lastrowid
        conn.commit()
    return listing_id


def get_listing_by_id(listing_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a listing row by primary key. Returns ``None`` if not found."""
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM listings WHERE id = ?", (listing_id,))
        return _row_to_dict(cursor.fetchone())


def get_listings_by_agent(agent_id: int) -> List[Dict[str, Any]]:
    """Return all listings assigned to an agent."""
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM listings WHERE agent_id = ?", (agent_id,))
        return _rows_to_dicts(cursor.fetchall())


def get_listings_by_status(status: str) -> List[Dict[str, Any]]:
    """Return all listings with the given status."""
    if status not in VALID_LISTING_STATUSES:
        raise ValueError(f"Invalid status: {status!r}")
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM listings WHERE status = ?", (status,))
        return _rows_to_dicts(cursor.fetchall())


def get_all_listings() -> List[Dict[str, Any]]:
    """Return all listings, ordered by id."""
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM listings ORDER BY id")
        return _rows_to_dicts(cursor.fetchall())

# ── Leads ────────────────────────────────────────────────────────────────

def create_lead(
    name: str,
    phone: Optional[str],
    email: str,
    message: str,
    listing_id: Optional[int],
    status: str = "new",
) -> int:
    """Insert a new lead and return the generated ``id``."""
    if status not in VALID_LEAD_STATUSES:
        raise ValueError(f"Invalid lead status: {status!r}. Must be one of: {VALID_LEAD_STATUSES}")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO leads (name, phone, email, message, listing_id, status)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (name, phone, email, message, listing_id, status),
        )
        lead_id = cursor.lastrowid
        conn.commit()
    return lead_id


def get_lead_by_id(lead_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a lead row by primary key. Returns ``None`` if not found."""
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM leads WHERE id = ?", (lead_id,))
        return _row_to_dict(cursor.fetchone())


def get_leads_by_listing(listing_id: int) -> List[Dict[str, Any]]:
    """Return all leads for a given listing."""
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM leads WHERE listing_id = ?", (listing_id,))
        return _rows_to_dicts(cursor.fetchall())


# ── Visits ───────────────────────────────────────────────────────────────

def create_visit(
    lead_id: int,
    listing_id: int,
    scheduled_at: str,
    status: str = "scheduled",
    notes: Optional[str] = None,
) -> int:
    """Insert a new visit record and return the generated ``id``."""
    if status not in VALID_VISIT_STATUSES:
        raise ValueError(f"Invalid visit status: {status!r}. Must be one of: {VALID_VISIT_STATUSES}")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO visits (lead_id, listing_id, scheduled_at, status, notes)
               VALUES (?, ?, ?, ?, ?)""",
            (lead_id, listing_id, scheduled_at, status, notes),
        )
        visit_id = cursor.lastrowid
        conn.commit()
    return visit_id


def get_visit_by_id(visit_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a visit row by primary key. Returns ``None`` if not found."""
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM visits WHERE id = ?", (visit_id,))
        return _row_to_dict(cursor.fetchone())


# ── Audit Log ────────────────────────────────────────────────────────────

def log_action(
    user_id: Optional[int],
    action: str,
    table_name: str,
    record_id: Optional[int],
    details: Optional[str] = None,
) -> int:
    """Append an entry to the ``audit_log`` and return the generated ``id``."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO audit_log (user_id, action, table_name, record_id, details)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, action, table_name, record_id, details),
        )
        log_id = cursor.lastrowid
        conn.commit()
    return log_id
