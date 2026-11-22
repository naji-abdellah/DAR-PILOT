# DarPilot Threat Model (v1.0 - Final)

This document outlines the threat model for DarPilot, a fictional real-estate AI assistant. The focus is on **secure-by-design AI engineering**, covering prompt injection, RAG security, and traditional web vulnerabilities.

---

## Assets

1. **User Data (Leads):** Names, phone numbers, and visit requests submitted via the frontend.
2. **Property Listings:** Synthetic property descriptions (French/Moroccan cities), prices, and agent assignments.
3. **LLM Credentials & System Prompts:** API keys for Gemini/OpenRouter, system instructions, and internal tool schemas.
4. **Audit Logs:** Records of agent actions, tool calls, and security events.
5. **Agent Tool Access:** Scoped permissions allowing `search_listings`, `create_lead`, `book_visit`, and `escalate_to_human`.

---

## Actors

1. **External Unauthenticated User:** Public visitors browsing listings or attempting to exploit the frontend/RAG.
2. **External Authenticated User (Viewer):** General audience, read-only access to listing details.
3. **Agent (Real Estate Agent):** Staff managing listings and leads; restricted to their assigned property inventory.
4. **Admin:** Staff with elevated privileges to manage users, all listings, and audit logs.
5. **External LLM Provider:** Third-party API (Gemini/OpenRouter) used for inference and embeddings.
6. **Malicious Attacker:** Actor attempting prompt injection, data exfiltration, privilege escalation, or resource exhaustion.

---

## Entry Points

1. **Frontend (Next.js + Tailwind):**
   - Public listing browsing and lead capture form.
   - Agent dashboard for managing visits and interacting with the assistant.
2. **Backend API (FastAPI):**
   - Public routes: `GET /listings`, `POST /leads`, `POST /visits`, `POST /ask`.
   - Authenticated routes: `POST /agent/chat` (LLM tool-calling), `/admin/users`, `POST /security/blocked-prompt`, `POST /security/ai-error`.
3. **RAG Pipeline & Vector Store (SQLite):**
   - Ingestion of synthetic listing descriptions (potential injection payload carrier).
   - Retrieval queries embedding user questions and listing chunks.
4. **LLM Interaction Layer:**
   - Free-tier API calls to Gemini/OpenRouter via `LLMClient` interface.
   - System prompt containing tool definitions and safety rules.
5. **Database (SQLite):**
   - Parameterized queries for `users`, `listings`, `leads`, `visits`, `audit_log`, `rag_chunks`.

---

## Top 10 Threats (STRIDE) — Status After M5

| # | Threat | STRIDE Category | Status | Mitigation Implemented |
|---|--------|-----------------|--------|------------------------|
| 1 | **Prompt Injection in Listings (Indirect RAG Injection)** | **Tampering** | **MITIGATED** | • Input validation with 30+ regex patterns (M5)<br>• PII redaction before LLM call (M4)<br>• Template-based FakeLLMClient for tests (M3)<br>• Explicit guardrails blocking instruction overrides, roleplay, pattern injection |
| 2 | **System Prompt & Tool Schema Leakage** | **Information Disclosure** | **MITIGATED** | • Injection detection patterns for prompt echo/leak attempts (M5)<br>• System prompt not included in user-visible context<br>• FakeLLMClient refuses system prompt requests (M3)<br>• Adversarial tests verify 100% block rate (M5) |
| 3 | **SQL Injection via Legacy Queries** | **Tampering** | **MITIGATED** | • 100% parameterized queries (`?` placeholders) — no string interpolation (M1)<br>• Pydantic validation on all endpoints (M1)<br>• Database CHECK constraints (M1)<br>• Tests confirm payloads stored literally, never executed (M1) |
| 4 | **Unauthorized Cross-Agent Lead Access (IDOR)** | **Information Disclosure** | **MITIGATED** | • Server-side RBAC on every endpoint (M2)<br>• `require_role` and `get_current_user` dependencies (M2)<br>• `get_lead_for_user` service checks listing ownership (M2)<br>• Authorization tests: viewer→403, agent→own only, admin→all (M2) |
| 5 | **Role Escalation (Viewer to Agent/Admin)** | **Elevation of Privilege** | **MITIGATED** | • JWT with `role` claim, short-lived (30 min), HS256 (M2)<br>• Server-side role checks on every mutating endpoint (M2)<br>• Invalid/expired token → 401 (M2)<br>• Regression tests: removing permission check breaks tests (M2) |
| 6 | **Resource Exhaustion / Cost Flooding (429 Abuse)** | **Denial of Service** | **PARTIAL** | • Input length limit: 2000 chars (M5)<br>• Iteration cap: 5 tool calls per conversation (M4)<br>• Exponential backoff + fallback provider chain (M4)<br>• Rate limiting on login: 5/min default (M2)<br>• *Future: API gateway rate limiting, request queuing* |
| 7 | **PII Leakage to Third-Party LLM** | **Information Disclosure** | **MITIGATED** | • PII redaction (phone, email) before LLM call (M4)<br>• FakeLLMClient used in tests/CI — no real API calls (M3/M4)<br>• Audit logs exclude PII fields (M4)<br>• *Future: On-premise LLM option* |
| 8 | **Unvalidated Agent Tool Execution** | **Tampering** | **MITIGATED** | • Tool allowlist: only 4 tools permitted (M4)<br>• JSON Schema validation on every tool call (M4)<br>• Human approval required for `book_visit` (M4)<br>• Input validation before tool execution (M4/M5)<br>• All actions logged to `audit_log` (M4) |
| 9 | **Spoofing via Stolen JWT/Tokens** | **Spoofing** | **MITIGATED** | • Short-lived tokens (30 min), `iat`/`exp` validation (M2)<br>• Secure cookie/HttpOnly for token storage (M2)<br>• CORS locked to configured origins (M2)<br>• Security headers: CSP, X-Frame-Options, Referrer-Policy (M2) |
| 10 | **Repudiation of Agent Actions** | **Repudiation** | **MITIGATED** | • Every tool invocation logged to `audit_log` with user_id, tool, args, success/failure (M4)<br>• Structured JSON details for forensic analysis (M4)<br>• Failed/blocked tools also logged (M4/M5)<br>• n8n alerting on repeated blocked prompts (M5) |

---

## Additional Threats Identified in M5

| # | Threat | Category | Status | Mitigation |
|---|--------|----------|--------|------------|
| 11 | **Scam/Fraudulent Listings** | **Tampering / Fraud** | **MITIGATED** | • Rule-based detector: price anomalies, duplicate content, suspicious contacts (M5)<br>• ML anomaly detection (Isolation Forest + TF-IDF) on synthetic data (M5)<br>• 16 tests covering all detection rules (M5) |
| 12 | **Prompt Injection via Conversation History** | **Tampering** | **MITIGATED** | • Iteration cap prevents infinite loops (M4)<br>• History length limit (M4)<br>• Each turn validated independently (M5) |
| 13 | **LLM Provider Outage / Key Rotation** | **Availability** | **PARTIAL** | • ResilientLLMClient: Gemini → OpenRouter → Fake fallback chain (M4)<br>• 429/503 exponential backoff with jitter (M4)<br>• n8n error workflow alerts on AI service failure (M5) |
| 14 | **Data Poisoning via Synthetic Listings** | **Integrity** | **MITIGATED** | • Synthetic data only — no real user data in training/embeddings (M1-M5)<br>• Duplicate/near-duplicate detection in scam scanner (M5)<br>• Embeddings recomputed on index rebuild (M3) |

---

## Mitigation Summary by Milestone

| Milestone | Key Security Controls Implemented |
|-----------|-----------------------------------|
| **M0** | Repo structure, `.gitignore`, gitleaks pre-commit hook, threat model v0 |
| **M1** | Parameterized SQL, Pydantic validation, CHECK constraints, rate limiting, SQLi tests |
| **M2** | Bcrypt + JWT auth, RBAC (admin/agent/viewer), CORS, security headers, authz tests |
| **M3** | RAG with citation, refusal on low score, FakeLLMClient, eval suite (94% hit rate) |
| **M4** | Agent with 4 tools, guardrails (allowlist, iteration cap, arg validation, human approval, PII redaction), audit logging, versioned prompts |
| **M5** | 27 adversarial tests (OWASP LLM Top 10), 100% defense rate, n8n alerting, scam detector (rules + ML) |

---

## Residual Risks (Accepted with Monitoring)

1. **Free-tier LLM rate limits** — May cause degraded UX during high traffic. Monitored via n8n alerts.
2. **Zero-day prompt injection** — New attack patterns may bypass current regex. Addressed by monitoring blocked prompts via n8n and updating patterns.
3. **SQLite single-writer bottleneck** — Acceptable for demo scale; PostgreSQL migration path documented.
4. **No WAF/API Gateway** — For production, would add Cloudflare/ModSecurity layer.

---

## Verification Evidence

- **122 automated tests pass** (pytest + CI)
- **Adversarial suite**: 27/27 attacks blocked (100% defense rate)
- **Authorization tests**: All RBAC scenarios verified
- **SQLi tests**: All injection payloads stored literally
- **Gitleaks**: Pre-commit + CI secret scanning
- **Bandit/Semgrep/pip-audit/npm audit**: CI security scanning

---

*Version: 1.0 | Date: 2026-11-22 | Status: Final*

---

**Next review:** After M6 CI pipeline validation and external penetration test.