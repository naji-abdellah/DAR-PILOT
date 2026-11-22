"""M3 RAG unit tests: chunking, embedding storage, semantic search, refusal.

Run against a throwaway SQLite database (DARPILOT_DB_PATH), never the real
darpilot.db.
"""

import os
import sqlite3
import tempfile

os.environ["DARPILOT_DB_PATH"] = tempfile.mkstemp(suffix=".db")[1]

import pytest  # noqa: E402

from backend.database import DB_PATH, init_db  # noqa: E402
from backend import repositories  # noqa: E402
from ai import rag  # noqa: E402


@pytest.fixture(autouse=True)
def clean_db():
    init_db()
    with sqlite3.connect(str(DB_PATH)) as conn:
        for table in ("visits", "leads", "listings", "audit_log", "users", "rag_chunks"):
            conn.execute(f"DELETE FROM {table}")
        # Reset auto-increment counters
        conn.execute("DELETE FROM sqlite_sequence")
        conn.commit()
    yield


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from backend.app import app

    return TestClient(app)


def _seed():
    """Seed two listings + one agent, build the RAG index, return villa id."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
        ("rag_eval_agent", "a@e.com", "h", "agent"),
    )
    agent_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        """INSERT INTO listings
           (title, description, price_mad, city, neighborhood, property_type, status, agent_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        ("Villa in Palmeraie", "Luxury villa with pool in Palmeraie, Marrakech.",
         4500000, "Marrakech", "Palmeraie", "Villa", "available", agent_id),
    )
    villa_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        """INSERT INTO listings
           (title, description, price_mad, city, neighborhood, property_type, status, agent_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        ("Studio in Gueliz", "Compact studio near shops in Gueliz, Marrakech.",
         700000, "Marrakech", "Gueliz", "Studio", "sold", agent_id),
    )
    conn.commit()
    conn.close()
    rag.build_index(repositories.get_all_listings(), chunk_size=60)
    return villa_id


def test_chunk_text_splits_on_word_boundary():
    chunks = rag.chunk_text("one two three four five six", max_words=2)
    assert chunks == ["one two", "three four", "five six"]


def test_chunk_text_empty():
    assert rag.chunk_text("") == []
    assert rag.chunk_text("   ") == []


def test_search_returns_most_similar_listing():
    villa_id = _seed()
    results = rag.search("villa with pool in Marrakech", top_k=3)
    # Only 2 listings are seeded, so at most 2 results are returned.
    assert 1 <= len(results) <= 2
    assert results[0]["listing_id"] == villa_id
    assert results[0]["score"] > 0.5


def test_search_scores_low_for_unrelated_query():
    _seed()
    results = rag.search("xqzpl qwer unrelated nonsense", top_k=3)
    # Unrelated queries get low cosine similarity (< refusal threshold 0.60).
    assert results
    assert all(r["score"] < 0.60 for r in results)


def test_search_scores_in_valid_range():
    _seed()
    results = rag.search("villa pool Marrakech", top_k=2)
    for r in results:
        assert 0.0 <= r["score"] <= 1.0
        assert "listing_id" in r and "chunk_text" in r and "title" in r


def test_ask_refuses_unrelated_question(client):
    resp = client.post("/ask", json={"question": "xqzpl qwer unrelated nonsense"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["refused"] is True
    assert body["sources"] == []
    assert "couldn't find" in body["answer"] or "trouv" in body["answer"]


def test_ask_answers_relevant_question(client):
    villa_id = _seed()
    resp = client.post("/ask", json={"question": "villa with pool in Marrakech"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["refused"] is False
    assert len(body["sources"]) >= 1
    assert body["sources"][0]["id"] == villa_id
    assert f"[id: {villa_id}]" in body["answer"]
