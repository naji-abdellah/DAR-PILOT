"""M4 Agent tests: tools, guardrails, PII redaction, audit logging, retry/fallback."""

import os
import tempfile

os.environ["DARPILOT_DB_PATH"] = tempfile.mkstemp(suffix=".db")[1]
os.environ["DARPILOT_SECRET_KEY"] = "test-secret-do-not-use-in-production"
os.environ["DARPILOT_LOGIN_RATE_LIMIT"] = "100/minute"
os.environ["DARPILOT_RAG_THRESHOLD"] = "0.60"

import pytest  # noqa: E402

from backend.database import DB_PATH, init_db  # noqa: E402
from backend import repositories  # noqa: E402
from backend import services  # noqa: E402
from ai import rag  # noqa: E402
from ai.llm import FakeLLMClient, ResilientLLMClient  # noqa: E402
from ai.agent import (  # noqa: E402
    Agent,
    SearchListingsTool,
    CreateLeadTool,
    BookVisitTool,
    EscalateToHumanTool,
    redact_pii,
    log_agent_action,
    TOOLS,
    ALLOWED_TOOLS,
    MAX_ITERATIONS,
    ToolResult,
)


@pytest.fixture(autouse=True)
def clean_db():
    init_db()
    import sqlite3

    with sqlite3.connect(str(DB_PATH)) as conn:
        for table in ("visits", "leads", "listings", "audit_log", "users", "rag_chunks"):
            conn.execute(f"DELETE FROM {table}")
        # Reset auto-increment counters
        conn.execute("DELETE FROM sqlite_sequence")
        conn.commit()
    yield


def _seed_data():
    """Seed test data: 1 agent, 2 listings, build RAG index."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
        ("test_agent", "agent@test.com", "hash", "agent"),
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
    studio_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    conn.commit()
    conn.close()

    rag.build_index(repositories.get_all_listings(), chunk_size=60)
    return villa_id, studio_id


# ── Tool Validation Tests ────────────────────────────────────────────────

def test_search_listings_tool_valid():
    _seed_data()
    tool = SearchListingsTool()
    args = tool.validate_args({"query": "villa marrakech", "top_k": 3})
    assert args == {"query": "villa marrakech", "top_k": 3}


def test_search_listings_tool_invalid_query():
    tool = SearchListingsTool()
    with pytest.raises(ValueError, match="query is required"):
        tool.validate_args({"query": ""})
    with pytest.raises(ValueError, match="exceeds maximum length"):
        tool.validate_args({"query": "x" * 201})


def test_search_listings_tool_invalid_top_k():
    tool = SearchListingsTool()
    with pytest.raises(ValueError, match="top_k must be an integer between 1 and 10"):
        tool.validate_args({"query": "test", "top_k": 0})
    with pytest.raises(ValueError, match="top_k must be an integer between 1 and 10"):
        tool.validate_args({"query": "test", "top_k": 11})


def test_create_lead_tool_valid():
    tool = CreateLeadTool()
    args = tool.validate_args({
        "name": "Youssef Benali",
        "email": "youssef@example.com",
        "phone": "0612345678",
        "message": "Interested",
        "listing_id": 1,
    })
    assert args["name"] == "Youssef Benali"
    assert args["email"] == "youssef@example.com"


def test_create_lead_tool_invalid_email():
    tool = CreateLeadTool()
    with pytest.raises(ValueError, match="valid email is required"):
        tool.validate_args({"name": "Test", "email": "not-an-email"})


def test_create_lead_tool_missing_name():
    tool = CreateLeadTool()
    with pytest.raises(ValueError, match="name is required"):
        tool.validate_args({"email": "test@example.com"})


def test_book_visit_tool_valid():
    tool = BookVisitTool()
    args = tool.validate_args({
        "lead_id": 1,
        "listing_id": 1,
        "scheduled_at": "2026-01-15T10:00:00",
        "notes": "Please call before",
    })
    assert args["lead_id"] == 1
    assert args["scheduled_at"] == "2026-01-15T10:00:00"


def test_book_visit_tool_invalid_scheduled_at():
    tool = BookVisitTool()
    with pytest.raises(ValueError, match="scheduled_at is required"):
        tool.validate_args({"lead_id": 1, "listing_id": 1, "scheduled_at": ""})
    with pytest.raises(ValueError, match="must be a valid datetime string"):
        tool.validate_args({"lead_id": 1, "listing_id": 1, "scheduled_at": "short"})


def test_escalate_to_human_tool_valid():
    tool = EscalateToHumanTool()
    args = tool.validate_args({
        "reason": "Complex negotiation",
        "summary": "User wants to negotiate price",
    })
    assert args["reason"] == "Complex negotiation"


# ── Tool Execution Tests ─────────────────────────────────────────────────

def test_search_listings_tool_execution():
    _seed_data()
    tool = SearchListingsTool()
    result = tool.execute({"query": "villa with pool", "top_k": 3})
    assert result.success
    assert isinstance(result.data, list)
    assert len(result.data) >= 1


def test_create_lead_tool_execution():
    _seed_data()
    tool = CreateLeadTool()
    result = tool.execute({
        "name": "Test Lead",
        "email": "lead@test.com",
        "message": "Interested in villa",
    })
    assert result.success
    assert result.data["id"] == 1
    assert result.data["name"] == "Test Lead"


def test_create_lead_tool_duplicate_email():
    _seed_data()
    tool = CreateLeadTool()
    tool.execute({"name": "Lead 1", "email": "same@test.com"})
    result = tool.execute({"name": "Lead 2", "email": "same@test.com"})
    # Should succeed (leads can have same email)
    assert result.success


def test_book_visit_tool_execution():
    _seed_data()
    # First create a lead
    lead_tool = CreateLeadTool()
    lead_result = lead_tool.execute({
        "name": "Visitor",
        "email": "visitor@test.com",
        "listing_id": 1,
    })
    lead_id = lead_result.data["id"]

    tool = BookVisitTool()
    result = tool.execute({
        "lead_id": lead_id,
        "listing_id": 1,
        "scheduled_at": "2026-01-15T10:00:00",
    })
    assert result.success
    assert result.data["lead_id"] == lead_id


def test_escalate_to_human_tool_execution():
    tool = EscalateToHumanTool()
    result = tool.execute({"reason": "Need human help"})
    assert result.success
    assert result.data["escalated"] is True


# ── Guardrails Tests ─────────────────────────────────────────────────────

def test_tool_allowlist_blocks_unknown_tool():
    """Test that unknown tools are not in the allowlist."""
    assert "malicious_tool" not in ALLOWED_TOOLS
    assert "search_listings" in ALLOWED_TOOLS
    assert "create_lead" in ALLOWED_TOOLS
    assert "book_visit" in ALLOWED_TOOLS
    assert "escalate_to_human" in ALLOWED_TOOLS


def test_iteration_cap():
    _seed_data()
    # Create an agent that will keep calling tools
    agent = Agent(llm_client=FakeLLMClient(), max_iterations=2)
    # The fake client doesn't make tool calls, so this just tests the cap exists
    assert agent.max_iterations == 2
    assert MAX_ITERATIONS == 5


def test_pii_redaction_phone():
    text = "Call me at 0612345678 or 06 12 34 56 78"
    redacted = redact_pii(text)
    assert "[PHONE]" in redacted
    assert "0612345678" not in redacted


def test_pii_redaction_email():
    text = "Email me at youssef@example.com"
    redacted = redact_pii(text)
    assert "[EMAIL]" in redacted
    assert "youssef@example.com" not in redacted


def test_pii_redaction_multiple():
    text = "Contact: 0612345678, email: test@example.com"
    redacted = redact_pii(text)
    assert "[PHONE]" in redacted
    assert "[EMAIL]" in redacted


def test_human_approval_required_for_booking():
    _seed_data()
    agent = Agent(llm_client=FakeLLMClient(), require_human_approval_for_booking=True)
    # Try to execute book_visit tool directly
    tool = TOOLS["book_visit"]
    # First create a lead
    lead_tool = TOOLS["create_lead"]
    lead_result = lead_tool.execute({
        "name": "Visitor",
        "email": "visitor@test.com",
        "listing_id": 1,
    })
    lead_id = lead_result.data["id"]

    # Execute book_visit through agent's internal method
    result = agent._execute_tool("book_visit", {
        "lead_id": lead_id,
        "listing_id": 1,
        "scheduled_at": "2026-01-15T10:00:00",
    }, user_id=1)

    assert not result.success
    assert "HUMAN_APPROVAL_REQUIRED" in result.error


def test_argument_validation_rejects_oversized():
    tool = SearchListingsTool()
    with pytest.raises(ValueError, match="exceeds maximum length"):
        tool.validate_args({"query": "x" * 300})


def test_argument_validation_rejects_invalid_types():
    tool = BookVisitTool()
    with pytest.raises(ValueError, match="lead_id must be a positive integer"):
        tool.validate_args({"lead_id": "not-an-int", "listing_id": 1, "scheduled_at": "2026-01-15T10:00:00"})


# ── Audit Logging Tests ──────────────────────────────────────────────────

def test_audit_log_records_tool_execution():
    _seed_data()
    tool = SearchListingsTool()
    result = tool.execute({"query": "villa", "top_k": 3})

    log_agent_action(1, "tool_executed", "search_listings", {"query": "villa"}, result)

    # Check audit_log was written
    import sqlite3
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM audit_log WHERE action = ?", ("tool_executed",))
    rows = cursor.fetchall()
    conn.close()

    assert len(rows) == 1
    assert rows[0]["user_id"] == 1
    assert rows[0]["table_name"] == "agent_actions"


def test_audit_log_records_blocked_tool():
    _seed_data()
    result = ToolResult(success=False, error="Tool not allowed")
    log_agent_action(1, "tool_blocked", "malicious_tool", {}, result)

    import sqlite3
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM audit_log WHERE action = ?", ("tool_blocked",))
    rows = cursor.fetchall()
    conn.close()

    assert len(rows) == 1
    import json
    details = json.loads(rows[0]["details"])
    assert details["tool"] == "malicious_tool"
    assert details["success"] is False


# ── LLM Client Fallback Tests ────────────────────────────────────────────

def test_fake_llm_client_works():
    client = FakeLLMClient()
    prompt = "Listings:\n- [id: 1] Villa in Palmeraie\nQuestion: villa marrakech"
    answer = client.generate(prompt)
    assert "[id: 1]" in answer


def test_resilient_client_falls_back_to_fake():
    # No API keys set, should use fake client
    client = ResilientLLMClient()
    # The last provider in the chain is FakeLLMClient
    assert len(client.providers) >= 1
    assert isinstance(client.providers[-1], FakeLLMClient)

    prompt = "Listings:\n- [id: 1] Villa in Palmeraie\nQuestion: villa marrakech"
    answer = client.generate(prompt)
    assert "[id: 1]" in answer


def test_fake_llm_refuses_when_no_listings():
    client = FakeLLMClient()
    prompt = "Listings:\n\nQuestion: villa marrakech"
    answer = client.generate(prompt)
    assert "couldn't find" in answer.lower() or "trouv" in answer.lower()


# ── Agent Integration Tests ──────────────────────────────────────────────

def test_agent_answers_without_tools():
    _seed_data()
    agent = Agent(llm_client=FakeLLMClient())
    result = agent.run("Hello, how are you?")
    assert "answer" in result
    assert isinstance(result["answer"], str)


def test_agent_handles_conversation_history():
    _seed_data()
    agent = Agent(llm_client=FakeLLMClient())
    history = [
        {"role": "user", "content": "I want a villa in Marrakech"},
        {"role": "assistant", "content": "I'll search for villas."},
    ]
    result = agent.run("Show me more details", conversation_history=history)
    assert "answer" in result


def test_agent_tool_results_included():
    _seed_data()
    agent = Agent(llm_client=FakeLLMClient())
    result = agent.run("Search for villa in Marrakech", user_id=1)
    assert "tool_calls" in result
    # The fake LLM doesn't make tool calls, so this will be empty
    # This test ensures the structure is correct


# Import sqlite3 for audit tests
import sqlite3