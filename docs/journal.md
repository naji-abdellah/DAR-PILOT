# DarPilot Learning Journal

This journal records learning progress, security insights, architectural decisions, and reflections as DarPilot is built.

---

## M0: Project Setup & Security Baseline

### Task: Repository Setup
- Initialized Git repository and directory structure (`backend`, `frontend`, `ai`, `prompts`, `tests`, `data`, `docs`, `.github/workflows`).
- Configured `.gitignore` to prevent secret leaks, database files, and build artifacts from being committed.
- Added `.env.example` as a safe template for local environment configuration.
- Created project stub documentation (`README.md`, `docs/journal.md`).

### Task: Secret Scanning Pre-Commit Hook
- Downloaded `gitleaks` v8.23.3 binary into `~/.local/bin`.
- Installed `pre-commit` via `uv` as a backup secret-scan tool.
- Created `.git/hooks/pre-commit` running `gitleaks protect --staged`.
- **Verified the hook works:** staged a file containing a fake Google-style API key (`AIzaSyD-0a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p`) and attempted a commit. The hook caught the leaked key, reported `leaks found: 1`, and blocked the commit.
- Removed the test secret file and confirmed clean commits now pass.

### Task: Threat Model v0
- Wrote `docs/threat-model.md` with STRIDE analysis:
  - **Assets:** user leads, synthetic listings, LLM credentials/system prompts, audit logs, agent tool access.
  - **Actors:** unauthenticated users, viewers, agents, admins, LLM provider, malicious attacker.
  - **Entry points:** Next.js frontend, FastAPI backend, RAG pipeline, LLM client layer, SQLite database.
  - **Top 10 threats:** indirect prompt injection via listings, system prompt leakage, SQL injection, IDOR cross-agent access, role escalation, DoS via LLM cost flooding, PII to third-party LLMs, unvalidated tool execution, spoofing via stolen tokens, repudiation of agent actions.
- Noted mitigations to be implemented across milestones M1-M5.

---

## M1: Data and API

### Task: Database Schema
- Created `backend/schema.sql` defining 5 tables: `users`, `listings`, `leads`, `visits`, `audit_log`.
- Enforced security constraints:
  - **Parameterized Queries**: All SQL execution uses `?` placeholders via `sqlite3.Row` context managers.
  - **Data Integrity**: Implemented `CHECK` constraints on `role`, `status`, and `price_mad` to reject invalid data at the database level.
  - **Foreign Keys**: Defined relationships between `listings` and `users`, and `leads`/`visits` and `listings`.
- Created `backend/database.py` for safe connection management.
- Added `tests/test_schema.py` to verify table existence and constraint enforcement (e.g., rejecting invalid roles and negative prices).
- Ran tests successfully: `4 passed in 0.12s`.

---

*Last updated: 2026-11-20*
