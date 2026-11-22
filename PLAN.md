# DarPilot: Secure AI Real-Estate Assistant

An AI assistant for a (fictional) Moroccan real-estate agency. It answers questions about listings, captures leads, and books visits. **What makes it different:** it is built secure by design and attacked on purpose, with measured results.

## How to use this file
- Work on **one task at a time**, top to bottom. Tick the box when the task is done and committed.
- Each task should fit in one short AI session. If a task feels too big, split it before starting.
- Milestones can be **reordered** if free-tier limits or opportunities change. Each one ends with a working demo.
- After every task: ask the AI to explain what it wrote, then add 3 to 5 lines to `docs/journal.md` in your own words.
- Use **synthetic data only**. No real names, phone numbers, or listings.

## Stack (proposed, change in CONTEXT.md if you decide otherwise)
- Backend: Python 3.11+, FastAPI, SQLite first (PostgreSQL/Supabase optional later)
- Frontend: Next.js + Tailwind (M2)
- LLM: Gemini free API behind a provider-agnostic `LLMClient`, OpenRouter free models as backup, a fake client for tests
- RAG: `fastembed` embeddings on CPU, Chroma or SQLite for vectors
- Automation: n8n via `npx n8n` (no Docker), GitHub Actions for CI
- Everything must run on 8 GB RAM, no GPU, Windows

---

## M0: Setup and threat model
**Demo:** public repo with a clean structure, a first commit, and a threat model draft.
- [x] Create the repo with the folder structure from CONTEXT.md
- [x] `.gitignore` (including `.env`, `*.db`, `node_modules`, `__pycache__`) and `.env.example`
- [x] README stub and `docs/journal.md`
- [x] Install a pre-commit secret scanner (gitleaks) and test it by committing a fake secret
- [x] `docs/threat-model.md` v0: assets, actors, entry points, top 10 threats (STRIDE)
- [x] **Break it:** commit a fake API key, see the scanner block it, then learn how to rotate a leaked key.

## M1: Data and API
**Demo:** a running API with documented endpoints and passing tests.
- [x] Schema: `users`, `listings`, `leads`, `visits`, `audit_log`
- [x] Script that generates 50 to 100 fictional listings (French, Casablanca/Marrakech neighborhoods, prices in MAD)
- [x] FastAPI CRUD for listings and leads, with layered code (routes, services, repositories)
- [x] Input validation on every endpoint (types, lengths, allowed values)
- [x] Only parameterized queries, no string-built SQL
- [x] `pytest` tests for happy paths and bad inputs
- [x] **Break it:** send oversized, malformed, and SQL-injection-style payloads and confirm they are rejected.

## M2: Dashboard, auth and roles
**Demo:** log in as admin, agent, or viewer and see different things.
- [x] Authentication (hashed passwords, short-lived tokens)
- [x] Roles: `admin`, `agent`, `viewer`, enforced on the **server**, not just the UI
- [x] Next.js pages: listings, listing detail, lead form, agent dashboard
- [x] Security headers, strict CORS, rate limiting on login
- [x] **Authorization tests**: a viewer cannot read leads, an agent cannot read another agent's leads, an unauthenticated user gets 401
- [x] **Break it:** remove a permission check and confirm the tests fail. Optional: repeat this with PostgreSQL row-level security if you move to Supabase.

## M3: RAG over listings
**Demo:** ask a question in French or English and get an answer with cited listings.
- [x] Chunk and embed listings on CPU
- [x] Retrieval endpoint returning top-k listings with scores
- [x] Answer generation that cites listing IDs and refuses when nothing relevant
- [x] **Evaluation set** of 30 questions with expected listings, plus a script that reports hit rate
- [x] Record results for at least two chunk sizes in `docs/eval.md`
- [x] **Break it:** put an instruction inside a listing description ("ignore previous instructions...") and see what the assistant does. Keep this case for M5.

## M4: Agent and guardrails
**Demo:** the assistant searches listings, creates a lead, and proposes a visit, with limits.
- [x] `LLMClient` interface with Gemini, OpenRouter, and fake implementations
- [x] Retry with exponential backoff on 429 and 503 errors, plus a fallback provider
- [x] Tools: `search_listings`, `create_lead`, `book_visit`, `escalate_to_human`
- [x] **Guardrails:** tool allowlist, iteration cap, validated tool arguments, human approval before booking, PII redaction before text is sent to the LLM
- [x] Every agent action written to `audit_log`
- [x] Prompt files versioned in `prompts/`
- **Break it:** trigger a 429 on purpose and confirm the fallback works.

## M5: Red teaming and detection
**Demo:** a report showing attack success rate before and after your fixes.
- [x] Prompt-injection test suite (at least 25 cases): direct injection, injection via listing text, system-prompt leak attempts, tool-abuse attempts, data exfiltration attempts
- [x] Map each case to the OWASP Top 10 for LLM Applications
- [x] Run the suite, record the **baseline** attack success rate, apply fixes, run again
- [x] Optional: try promptfoo or garak for automation (check their current docs first)
- [x] n8n workflow: webhook to AI service to alert, with an error workflow, firing on repeated blocked prompts or failed logins
- [x] Scam-listing detector: simple rules plus a scikit-learn model on synthetic data (price far below market, copied text, suspicious contact patterns)
- **Break it:** make the AI service fail and confirm the n8n error workflow alerts you.

## M6: CI and polish
**Demo:** a repo a stranger can clone, run, and trust.
- [x] GitHub Actions on every push: `pytest`, gitleaks, Semgrep, Bandit, `pip-audit`, `npm audit`
- [x] Final `docs/threat-model.md` and `docs/risk-register.md` (risk, likelihood, impact, mitigation, status)
- [x] `docs/security-report.md`: before/after results from M5 and what is still open
- [x] Short compliance note mapping controls to Morocco's data-protection law (09-08, CNDP) and ISO 27001-style controls (verify details before publishing)
- [x] README with setup steps, architecture diagram, and screenshots
- [x] 2-minute demo video
- [x] Ask someone to follow the README from scratch and fix what confuses them

---

## M7: Fix critical vulnerabilities (security fixes with failing tests first)
**Demo:** all auth/IDOR/ownership bugs fixed, `/security/*` authenticated, rate limits on LLM endpoints, Gemini key in header.
- [x] **M7.1** Fix admin self-registration: force `viewer` role on self-registration; add admin creation via separate mechanism. Write failing test first.
- [x] **M7.2** Fix IDOR on leads: routes must use `get_lead_for_user` and `get_leads_for_listing_for_user`. Write failing test "agent cannot read another agent's leads".
- [x] **M7.3** Fix visit ownership: visits scoped to agent; agents can only create/read their own visits; viewers cannot create visits. Write failing tests.
- [x] **M7.4** Fix listing creation: agent cannot set `agent_id` to another user. Write failing test.
- [x] **M7.5** Protect `/security/*` endpoints: require authentication + rate limiting. Write failing tests.
- [x] **M7.6** Add rate limiting to `/ask` and `/search` (LLM-cost endpoints). Write failing test.
- [x] **M7.7** Fix Gemini API key: use `x-goog-api-key` header instead of URL param. Update `ResilientLLMClient`.
- [x] **M7.8** Fix indirect injection defenses: `/ask` must call `validate_input` and `redact_pii`; prompt built with safe templating (no plain concatenation); `conversation_history` sanitized and `MAX_HISTORY_LENGTH` enforced.
- [x] **M7.9** Enable SQLite foreign keys (`PRAGMA foreign_keys=ON`).

## M8: Fix repo, CI, and environment issues
**Demo:** `pip install -r requirements.txt` works; CI runs from repo root; `.env.example` works out of the box.
- [x] **M8.1** Fix `requirements.txt`: add `PyJWT`, `scikit-learn`, `email-validator`; remove unused `python-jose`, `passlib`.
- [ ] **M8.2** Fix CI paths: run from repo root, not `./backend`.
- [ ] **M8.3** Fix `.env.example`: point to project DB path, set `DARPILOT_CORS_ORIGINS` to `http://localhost:3000`.
- [ ] **M8.4** Fix Bandit/Semgrep CI: remove `|| true` / `continue-on-error` so findings fail the build.
- [ ] **M8.5** Add frontend login form and assistant chat UI (main feature).

## M9: Honest red-team suite
**Demo:** held-out test set, stored-listing payloads, run against real model, documented baseline.
- [ ] **M9.1** Rewrite adversarial tests: payloads delivered via stored listing text (RAG path), not direct user input.
- [ ] **M9.2** Create held-out test set (unseen by developer) for honest evaluation.
- [ ] **M9.3** Run suite against real LLM (Gemini/OpenRouter) and document results.
- [ ] **M9.4** Fix `safe_response` evaluator: actually evaluate response safety, not always return True.
- [ ] **M9.5** Make baseline reproducible: script that runs against FakeLLMClient without guardrails.

## M10: Correct documentation to match code
**Demo:** every claim in docs is verifiable in code.
- [ ] **M10.1** Update `docs/security-report.md`: remove "100% defense" claim, document actual test methodology and limitations.
- [ ] **M10.2** Update `docs/compliance.md`: verify Law 09-08 article numbers; use ISO 27001:2022 numbering consistently.
- [ ] **M10.3** Fix `docs/threat-model.md`: remove claims about HttpOnly cookies, HSTS, WAL mode, `/agent/chat`, `/admin/users`.
- [ ] **M10.4** Fix `docs/risk-register.md`: treatment counts must match list.
- [ ] **M10.5** Fix `docs/eval.md`: consistent counts.
- [ ] **M10.6** Update README: remove 🚧, add real screenshots or remove placeholder references.
- [ ] **M10.7** Fix audit log claims: document actual behavior (stores args, truncates to 100 chars, includes PII).

## M11: Fix remaining agent/guardrail gaps
**Demo:** approval flow works; n8n error workflow triggered automatically; conversation history bounded.
- [ ] **M11.1** Implement `book_visit` approval flow: return `approval_id`, add `/admin/approvals/{id}/approve` endpoint.
- [ ] **M11.2** Wire `ResilientLLMClient` to call `alert_ai_service_error` on failures.
- [ ] **M11.3** Fix n8n alert counters: add reset logic (time-window based).
- [ ] **M11.4** Enforce `MAX_HISTORY_LENGTH` in agent conversation history.
- [ ] **M11.5** Sanitize tool results and listing text before including in prompt (prevent role marker forgery).

---

## Rules for AI sessions
- Start each session with: "Read CONTEXT.md and PLAN.md, then do only task X."
- After each task: run tests, review the diff for security issues, commit.
- Never accept code you cannot explain. Ask the AI to explain it, then re-explain it in the journal.
- If the model starts looping or changing unrelated files, stop, roll back with git, and restart with a smaller task.

## Open decisions
- [ ] SQLite only, or move to PostgreSQL/Supabase for row-level security? (decide at M2)
- [x] Chroma or SQLite for vectors? (decided at M3: SQLite — lighter on 8 GB RAM/no GPU, one DB, cosine similarity in Python)
- [ ] Which offer or goal this project targets (affects what to polish)

## Decisions log
- 2026-11-22: M3 vector store = SQLite (not Chroma). Lighter on 8 GB RAM/no GPU, no extra server process, keeps everything in one DB, cosine similarity computed in Python over fetched vectors. fastembed on CPU for embeddings.
