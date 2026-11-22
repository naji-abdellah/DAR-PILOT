"""M1/M2 API tests: CRUD happy paths, bad inputs, and authorization.

Tests run against a throwaway SQLite database pointed at by the
``DARPILOT_DB_PATH`` environment variable, so the real ``darpilot.db`` is
never touched and tests are isolated from one another.

Every request that reaches the database uses parameterized queries, so
SQL-injection-style payloads are stored literally and never executed.
"""

import os
import tempfile

os.environ["DARPILOT_DB_PATH"] = tempfile.mkstemp(suffix=".db")[1]
# Auth module requires a secret key; use a throwaway value for tests only.
os.environ["DARPILOT_SECRET_KEY"] = "test-secret-do-not-use-in-production"
# High login rate limit so the test suite isn't throttled (5/min is for prod).
os.environ["DARPILOT_LOGIN_RATE_LIMIT"] = "100/minute"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.app import app  # noqa: E402
from backend.database import DB_PATH, init_db  # noqa: E402

TABLES = ("visits", "leads", "listings", "audit_log", "users")


@pytest.fixture(autouse=True)
def clean_db():
    """Recreate the schema and wipe all rows before each test."""
    init_db()
    import sqlite3

    with sqlite3.connect(str(DB_PATH)) as conn:
        for table in TABLES:
            conn.execute(f"DELETE FROM {table}")
        conn.commit()
    yield


@pytest.fixture
def client():
    return TestClient(app)


def register_and_login(client, username="alice", password="Password123!", role="agent"):
    """Register a user and return (client, auth_headers, user_id)."""
    client.post(
        "/auth/register",
        json={"username": username, "email": f"{username}@example.com", "password": password, "role": role},
    )
    resp = client.post(
        "/auth/login",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ── Listings ──────────────────────────────────────────────────────────


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_create_listing_happy(client):
    headers = register_and_login(client)
    payload = {
        "title": "Modern Apartment in Maarif",
        "description": "Bright 2-bedroom apartment.",
        "price_mad": 1200000,
        "city": "Casablanca",
        "neighborhood": "Maarif",
        "property_type": "Apartment",
    }
    resp = client.post("/listings", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["id"] == 1
    assert data["title"] == "Modern Apartment in Maarif"
    assert data["status"] == "available"
    assert data["agent_id"] is not None


def test_create_listing_with_agent(client):
    headers = register_and_login(client, username="samir", role="agent")
    payload = {
        "title": "Villa in Palmeraie",
        "price_mad": 4500000,
        "city": "Marrakech",
        "neighborhood": "Palmeraie",
        "property_type": "Villa",
    }
    resp = client.post("/listings", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    assert resp.json()["agent_id"] is not None


def test_list_listings(client):
    headers = register_and_login(client)
    client.post("/listings", json={
        "title": "A", "price_mad": 100000, "city": "Casablanca",
        "neighborhood": "Anfa", "property_type": "Studio",
    }, headers=headers)
    client.post("/listings", json={
        "title": "B", "price_mad": 200000, "city": "Marrakech",
        "neighborhood": "Gueliz", "property_type": "Apartment", "status": "sold",
    }, headers=headers)
    resp = client.get("/listings")
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    resp = client.get("/listings", params={"status": "available"})
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["title"] == "A"


def test_get_listing(client):
    headers = register_and_login(client)
    create = client.post("/listings", json={
        "title": "Studio in Gueliz", "price_mad": 700000,
        "city": "Marrakech", "neighborhood": "Gueliz",
        "property_type": "Studio",
    }, headers=headers)
    listing_id = create.json()["id"]

    resp = client.get(f"/listings/{listing_id}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Studio in Gueliz"

    resp = client.get("/listings/99999")
    assert resp.status_code == 404


# ── Bad inputs: listings ──────────────────────────────────────────────


def test_create_listing_invalid_status(client):
    headers = register_and_login(client)
    resp = client.post("/listings", json={
        "title": "X", "price_mad": 100, "city": "Casablanca",
        "neighborhood": "Anfa", "property_type": "Apartment",
        "status": "reserved",
    }, headers=headers)
    assert resp.status_code == 422, resp.text


def test_create_listing_negative_price(client):
    headers = register_and_login(client)
    resp = client.post("/listings", json={
        "title": "X", "price_mad": -500, "city": "Casablanca",
        "neighborhood": "Anfa", "property_type": "Apartment",
    }, headers=headers)
    assert resp.status_code == 422, resp.text


def test_create_listing_oversized_title(client):
    headers = register_and_login(client)
    resp = client.post("/listings", json={
        "title": "x" * 201, "price_mad": 100, "city": "Casablanca",
        "neighborhood": "Anfa", "property_type": "Apartment",
    }, headers=headers)
    assert resp.status_code == 422, resp.text


def test_create_listing_missing_required(client):
    headers = register_and_login(client)
    resp = client.post("/listings", json={
        "price_mad": 100, "city": "Casablanca",
        "neighborhood": "Anfa", "property_type": "Apartment",
    }, headers=headers)
    assert resp.status_code == 422, resp.text


def test_create_listing_invalid_property_type(client):
    headers = register_and_login(client)
    resp = client.post("/listings", json={
        "title": "X", "price_mad": 100, "city": "Casablanca",
        "neighborhood": "Anfa", "property_type": "Castle",
    }, headers=headers)
    assert resp.status_code == 422, resp.text


# ── Leads ─────────────────────────────────────────────────────────────


def test_create_lead_happy(client):
    resp = client.post("/leads", json={
        "name": "Youssef Benali",
        "phone": "0612345678",
        "email": "youssef@example.com",
        "message": "Interested in this listing.",
    })
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["id"] == 1
    assert data["status"] == "new"


def test_get_lead(client):
    create = client.post("/leads", json={
        "name": "Youssef Benali", "email": "youssef@example.com",
        "message": "Hi",
    })
    lead_id = create.json()["id"]

    headers = register_and_login(client)
    resp = client.get(f"/leads/{lead_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Youssef Benali"

    resp = client.get("/leads/99999", headers=headers)
    assert resp.status_code == 404


def test_leads_for_listing(client):
    headers = register_and_login(client)
    listing = client.post("/listings", json={
        "title": "Riad in Medina", "price_mad": 3000000,
        "city": "Marrakech", "neighborhood": "Medina",
        "property_type": "Riad",
    }, headers=headers).json()

    client.post("/leads", json={
        "name": "Lead 1", "email": "a@example.com", "listing_id": listing["id"],
    })
    client.post("/leads", json={
        "name": "Lead 2", "email": "b@example.com", "listing_id": listing["id"],
    })

    resp = client.get(f"/leads/listing/{listing['id']}", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


# ── Bad inputs: leads ─────────────────────────────────────────────────


def test_create_lead_bad_email(client):
    resp = client.post("/leads", json={
        "name": "Youssef", "email": "not-an-email", "message": "Hi",
    })
    assert resp.status_code == 422, resp.text


def test_create_lead_missing_name(client):
    resp = client.post("/leads", json={
        "email": "a@example.com", "message": "Hi",
    })
    assert resp.status_code == 422, resp.text


# ── Security: SQL injection ───────────────────────────────────────────


def test_sql_injection_listing_title_stored_literally(client):
    """Injection payload in a title must be stored as-is, never executed."""
    headers = register_and_login(client)
    payload = {
        "title": "Apartment'; DROP TABLE listings; --",
        "price_mad": 100000,
        "city": "Casablanca",
        "neighborhood": "Anfa",
        "property_type": "Apartment",
    }
    resp = client.post("/listings", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    assert resp.json()["title"] == "Apartment'; DROP TABLE listings; --"

    # The listings table must still exist and be queryable afterwards.
    resp = client.get("/listings")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["title"] == "Apartment'; DROP TABLE listings; --"


def test_sql_injection_in_listing_id(client):
    """Non-integer / injection path params are rejected, never executed."""
    # Public endpoint: FastAPI int conversion rejects non-integers (422).
    resp = client.get("/listings/1 OR 1=1")
    assert resp.status_code == 422, resp.text
    resp = client.get("/listings/abc")
    assert resp.status_code == 422, resp.text

    # Protected endpoint: injection attempt is met with 401 (auth required),
    # the query is never executed.
    resp = client.get("/leads/listing/1; DELETE FROM listings")
    assert resp.status_code == 401, resp.text


# ── Authorization ──────────────────────────────────────────────────────


def test_unauthenticated_create_listing_rejected(client):
    """No token → 401 on protected write endpoint."""
    resp = client.post("/listings", json={
        "title": "X", "price_mad": 100, "city": "Casablanca",
        "neighborhood": "Anfa", "property_type": "Apartment",
    })
    assert resp.status_code == 401, resp.text


def test_unauthenticated_read_lead_rejected(client):
    """No token → 401 on protected read endpoint."""
    resp = client.get("/leads/1")
    assert resp.status_code == 401, resp.text


def test_viewer_cannot_create_listing(client):
    """Viewer role → 403 on create-listing (agent/admin only)."""
    headers = register_and_login(client, username="viewer1", role="viewer")
    resp = client.post("/listings", json={
        "title": "X", "price_mad": 100, "city": "Casablanca",
        "neighborhood": "Anfa", "property_type": "Apartment",
    }, headers=headers)
    assert resp.status_code == 403, resp.text


def test_agent_can_create_listing(client):
    """Agent role → 201 on create-listing."""
    headers = register_and_login(client, username="agent1", role="agent")
    resp = client.post("/listings", json={
        "title": "X", "price_mad": 100, "city": "Casablanca",
        "neighborhood": "Anfa", "property_type": "Apartment",
    }, headers=headers)
    assert resp.status_code == 201, resp.text


def test_admin_can_create_listing(client):
    """Admin role → 201 on create-listing."""
    headers = register_and_login(client, username="admin1", role="admin")
    resp = client.post("/listings", json={
        "title": "X", "price_mad": 100, "city": "Casablanca",
        "neighborhood": "Anfa", "property_type": "Apartment",
    }, headers=headers)
    assert resp.status_code == 201, resp.text


def test_viewer_cannot_read_leads(client):
    """Viewer role → 403 on reading leads (agent/admin only)."""
    headers = register_and_login(client, username="viewer2", role="viewer")
    resp = client.get("/leads/1", headers=headers)
    assert resp.status_code == 403, resp.text


def test_invalid_token_rejected(client):
    """Malformed bearer token → 401."""
    resp = client.get("/leads/1", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401, resp.text


def test_expired_token_rejected(client):
    """Expired token → 401."""
    import datetime as _dt
    from backend import auth
    token = auth.create_access_token(user_id=1, role="agent")
    # Force expiry into the past by re-encoding with exp=0.
    import jwt
    expired = jwt.encode({"sub": "1", "role": "agent", "iat": 0, "exp": 0},
                         auth.SECRET_KEY, algorithm=auth.ALGORITHM)
    resp = client.get("/leads/1", headers={"Authorization": f"Bearer {expired}"})
    assert resp.status_code == 401, resp.text
