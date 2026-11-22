"""Service layer for DarPilot business logic.

This layer sits between routes and repositories. It validates inputs
beyond what Pydantic does (e.g., length limits, allowed values) and
enforces authorization rules. All SQL is in repositories.py — none here.
"""

from __future__ import annotations

import os
import json
from typing import Any, Dict, List, Optional

import requests

from backend import auth
from backend import repositories

# ── Validation constants ───────────────────────────────────────────────

MAX_TITLE_LEN = 200
MAX_DESCRIPTION_LEN = 5000
MAX_NAME_LEN = 100
MAX_PHONE_LEN = 20
MAX_EMAIL_LEN = 255
MAX_MESSAGE_LEN = 2000
MAX_CITY_LEN = 50
MAX_NEIGHBORHOOD_LEN = 50
MAX_PROPERTY_TYPE_LEN = 30
MAX_NOTES_LEN = 1000
MIN_PRICE_MAD = 0
MAX_PRICE_MAD = 100_000_000

VALID_PROPERTY_TYPES = ("Apartment", "Villa", "Studio", "Riad")


def _validate_required_string(value: str, field: str, max_len: int) -> str:
    """Validate a required string field: non-empty, max length."""
    if not value or not value.strip():
        raise ValueError(f"{field} is required and cannot be empty")
    stripped = value.strip()
    if len(stripped) > max_len:
        raise ValueError(f"{field} exceeds maximum length of {max_len} characters")
    return stripped


def _validate_optional_string(value: Optional[str], field: str, max_len: int) -> Optional[str]:
    """Validate an optional string field: if provided, max length."""
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    if len(stripped) > max_len:
        raise ValueError(f"{field} exceeds maximum length of {max_len} characters")
    return stripped


def _validate_price(price: int) -> int:
    """Validate price is within bounds."""
    if not isinstance(price, int):
        raise TypeError("price_mad must be an integer")
    if price < MIN_PRICE_MAD or price > MAX_PRICE_MAD:
        raise ValueError(f"price_mad must be between {MIN_PRICE_MAD} and {MAX_PRICE_MAD}")
    return price


def _validate_property_type(prop_type: str) -> str:
    """Validate property type against allowed list."""
    stripped = prop_type.strip()
    if stripped not in VALID_PROPERTY_TYPES:
        raise ValueError(
            f"property_type must be one of: {VALID_PROPERTY_TYPES}"
        )
    return stripped


# ── User service ───────────────────────────────────────────────────────

def register_user(username: str, email: str, password_hash: str, role: str = "agent") -> Dict[str, Any]:
    """Create a new user after validating inputs."""
    username = _validate_required_string(username, "username", 50)
    email = _validate_required_string(email, "email", MAX_EMAIL_LEN)
    if "@" not in email:
        raise ValueError("Invalid email format")
    if role not in repositories.VALID_ROLES:
        raise ValueError(f"Invalid role: {role!r}. Must be one of: {repositories.VALID_ROLES}")
    user_id = repositories.create_user(username, email, password_hash, role)
    return {"id": user_id, "username": username, "email": email, "role": role}


def get_user(username: str) -> Optional[Dict[str, Any]]:
    """Fetch user by username."""
    return repositories.get_user_by_username(username)


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Fetch user by ID."""
    return repositories.get_user_by_id(user_id)


def register_user_account(
    username: str, email: str, password: str, role: str = "agent"
) -> Dict[str, Any]:
    """Create a new user, hashing the password server-side."""
    username = _validate_required_string(username, "username", 50)
    email = _validate_required_string(email, "email", MAX_EMAIL_LEN)
    if "@" not in email:
        raise ValueError("Invalid email format")
    if role not in repositories.VALID_ROLES:
        raise ValueError(f"Invalid role: {role!r}. Must be one of: {repositories.VALID_ROLES}")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    password_hash = auth.hash_password(password)
    user_id = repositories.create_user(username, email, password_hash, role)
    return {"id": user_id, "username": username, "email": email, "role": role}


def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Verify credentials and return the user, or None on failure."""
    user = repositories.get_user_by_username(username)
    if user is None:
        return None
    if not auth.verify_password(password, user["password_hash"]):
        return None
    return user


# ── Listing service ────────────────────────────────────────────────────

def create_listing(
    title: str,
    description: str,
    price_mad: int,
    city: str,
    neighborhood: str,
    property_type: str,
    status: str = "available",
    agent_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Create a listing after validating all inputs."""
    title = _validate_required_string(title, "title", MAX_TITLE_LEN)
    description = _validate_optional_string(description, "description", MAX_DESCRIPTION_LEN) or ""
    price_mad = _validate_price(price_mad)
    city = _validate_required_string(city, "city", MAX_CITY_LEN)
    neighborhood = _validate_optional_string(neighborhood, "neighborhood", MAX_NEIGHBORHOOD_LEN) or ""
    property_type = _validate_property_type(property_type)
    if status not in repositories.VALID_LISTING_STATUSES:
        raise ValueError(f"Invalid status: {status!r}. Must be one of: {repositories.VALID_LISTING_STATUSES}")
    if agent_id is not None and not isinstance(agent_id, int):
        raise TypeError("agent_id must be an integer or None")
    listing_id = repositories.create_listing(
        title, description, price_mad, city, neighborhood, property_type, status, agent_id
    )
    return {
        "id": listing_id,
        "title": title,
        "description": description,
        "price_mad": price_mad,
        "city": city,
        "neighborhood": neighborhood,
        "property_type": property_type,
        "status": status,
        "agent_id": agent_id,
    }


def get_listing(listing_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a listing by ID."""
    return repositories.get_listing_by_id(listing_id)


def get_listings_by_agent(agent_id: int) -> List[Dict[str, Any]]:
    """Return all listings for an agent."""
    if not isinstance(agent_id, int):
        raise TypeError("agent_id must be an integer")
    return repositories.get_listings_by_agent(agent_id)


def get_listings_by_status(status: str) -> List[Dict[str, Any]]:
    """Return all listings with the given status."""
    if status not in repositories.VALID_LISTING_STATUSES:
        raise ValueError(f"Invalid status: {status!r}")
    return repositories.get_listings_by_status(status)


def get_listings() -> List[Dict[str, Any]]:
    """Return all listings."""
    return repositories.get_all_listings()

def create_lead(
    name: str,
    phone: Optional[str],
    email: str,
    message: str,
    listing_id: Optional[int],
    status: str = "new",
) -> Dict[str, Any]:
    """Create a new lead after validating inputs."""
    name = _validate_required_string(name, "name", MAX_NAME_LEN)
    phone = _validate_optional_string(phone, "phone", MAX_PHONE_LEN) or ""
    email = _validate_required_string(email, "email", MAX_EMAIL_LEN)
    if "@" not in email:
        raise ValueError("Invalid email format")
    message = _validate_optional_string(message, "message", MAX_MESSAGE_LEN) or ""
    if listing_id is not None and not isinstance(listing_id, int):
        raise TypeError("listing_id must be an integer or None")
    if status not in repositories.VALID_LEAD_STATUSES:
        raise ValueError(f"Invalid status: {status!r}. Must be one of: {repositories.VALID_LEAD_STATUSES}")
    lead_id = repositories.create_lead(name, phone, email, message, listing_id, status)
    return {
        "id": lead_id,
        "name": name,
        "phone": phone,
        "email": email,
        "message": message,
        "listing_id": listing_id,
        "status": status,
    }


def get_lead_by_id(lead_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a lead by ID."""
    if not isinstance(lead_id, int):
        raise TypeError("lead_id must be an integer")
    return repositories.get_lead_by_id(lead_id)


def get_leads_by_listing(listing_id: int) -> List[Dict[str, Any]]:
    """Return all leads for a given listing."""
    if not isinstance(listing_id, int):
        raise TypeError("listing_id must be an integer")
    return repositories.get_leads_by_listing(listing_id)


def get_lead_for_user(lead_id: int, current_user: dict) -> Optional[Dict[str, Any]]:
    """Fetch a lead if the user may see it: admin, or the agent who owns its listing.

    Returns ``None`` when the lead does not exist or the agent is not the listing
    owner. Using ``None`` (404) rather than 403 for cross-agent access avoids
    confirming that the lead exists (IDOR mitigation).
    """
    if not isinstance(lead_id, int):
        raise TypeError("lead_id must be an integer")
    lead = repositories.get_lead_by_id(lead_id)
    if lead is None:
        return None
    if current_user.get("role") == "admin":
        return lead
    listing_id = lead.get("listing_id")
    if listing_id is not None:
        listing = repositories.get_listing_by_id(listing_id)
        if listing and listing.get("agent_id") == current_user.get("id"):
            return lead
    return None


def get_leads_for_listing_for_user(
    listing_id: int, current_user: dict
) -> List[Dict[str, Any]]:
    """Return leads for a listing if the user may see them: admin, or the agent
    who owns the listing. Returns an empty list for unauthorized agents."""
    if not isinstance(listing_id, int):
        raise TypeError("listing_id must be an integer")
    if current_user.get("role") == "admin":
        return repositories.get_leads_by_listing(listing_id)
    listing = repositories.get_listing_by_id(listing_id)
    if listing and listing.get("agent_id") == current_user.get("id"):
        return repositories.get_leads_by_listing(listing_id)
    return []


def create_visit(
    lead_id: int,
    listing_id: int,
    scheduled_at: str,
    status: str = "scheduled",
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a visit record after validating inputs."""
    if not isinstance(lead_id, int):
        raise TypeError("lead_id must be an integer")
    if not isinstance(listing_id, int):
        raise TypeError("listing_id must be an integer")
    scheduled_at = _validate_required_string(scheduled_at, "scheduled_at", 50)
    # Basic ISO-like date check (lenient for simplicity)
    if len(scheduled_at) < 10:
        raise ValueError("scheduled_at must be a valid datetime string (e.g., 2026-01-15T10:00:00)")
    if status not in repositories.VALID_VISIT_STATUSES:
        raise ValueError(f"Invalid visit status: {status!r}. Must be one of: {repositories.VALID_VISIT_STATUSES}")
    notes = _validate_optional_string(notes, "notes", MAX_NOTES_LEN) or ""
    visit_id = repositories.create_visit(lead_id, listing_id, scheduled_at, status, notes)
    return {
        "id": visit_id,
        "lead_id": lead_id,
        "listing_id": listing_id,
        "scheduled_at": scheduled_at,
        "status": status,
        "notes": notes,
    }


def get_visit_by_id(visit_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a visit by ID."""
    if not isinstance(visit_id, int):
        raise TypeError("visit_id must be an integer")
    return repositories.get_visit_by_id(visit_id)


def log_action(
    user_id: Optional[int],
    action: str,
    table_name: str,
    record_id: Optional[int],
    details: Optional[str] = None,
) -> int:
    """Log an action to the audit log."""
    if user_id is not None and not isinstance(user_id, int):
        raise TypeError("user_id must be an integer or None")
    action = _validate_required_string(action, "action", 50)
    table_name = _validate_required_string(table_name, "table_name", 50)
    if record_id is not None and not isinstance(record_id, int):
        raise TypeError("record_id must be an integer or None")
    details = _validate_optional_string(details, "details", 2000) or ""
    return repositories.log_action(user_id, action, table_name, record_id, details)


# ── n8n Alerting ──────────────────────────────────────────────────────────

N8N_WEBHOOK_URL = os.environ.get("N8N_WEBHOOK_URL", "http://localhost:5678/webhook")


def _send_n8n_webhook(endpoint: str, payload: Dict[str, Any]) -> bool:
    """Send a webhook to n8n. Returns True if successful, False otherwise."""
    url = f"{N8N_WEBHOOK_URL}/{endpoint}"
    try:
        resp = requests.post(url, json=payload, timeout=5)
        return resp.status_code == 200
    except Exception:
        # Never let alerting break the main flow
        return False


def alert_blocked_prompt(
    user_id: Optional[int],
    attack_type: str,
    payload: str,
    ip: Optional[str] = None,
) -> bool:
    """Send blocked prompt alert to n8n."""
    return _send_n8n_webhook("security/blocked-prompt", {
        "user_id": user_id,
        "attack_type": attack_type,
        "payload": payload[:500],  # Truncate for safety
        "ip": ip,
        "timestamp": __import__("datetime").datetime.now().isoformat(),
    })


def alert_failed_login(
    username: str,
    ip: Optional[str] = None,
) -> bool:
    """Send failed login alert to n8n."""
    return _send_n8n_webhook("security/failed-login", {
        "username": username,
        "ip": ip,
        "timestamp": __import__("datetime").datetime.now().isoformat(),
    })


def alert_ai_service_error(
    endpoint: str,
    error: str,
) -> bool:
    """Send AI service error alert to n8n (error workflow)."""
    return _send_n8n_webhook("ai-service/error", {
        "endpoint": endpoint,
        "error": error[:500],
        "timestamp": __import__("datetime").datetime.now().isoformat(),
    })

