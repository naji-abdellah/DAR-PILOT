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
- [ ] Script that generates 50 to 100 fictional listings (French, Casablanca/Marrakech neighborhoods, prices in MAD)
- [ ] FastAPI CRUD for listings and leads, with layered code (routes, services, repositories)
- [ ] Input validation on every endpoint (types, lengths, allowed values)
- [ ] Only parameterized queries, no string-built SQL
- [ ] `pytest` tests for happy paths and bad inputs
- **Break it:** send oversized, malformed, and SQL-injection-style payloads and confirm they are rejected.

## M2: Dashboard, auth and roles
**Demo:** log in as admin, agent, or viewer and see different things.
- [ ] Authentication (hashed passwords, short-lived tokens)
- [ ] Roles: `admin`, `agent`, `viewer`, enforced on the **server**, not just the UI
- [ ] Next.js pages: listings, listing detail, lead form, agent dashboard
- [ ] Security headers, strict CORS, rate limiting on login
- [ ] **Authorization tests**: a viewer cannot read leads, an agent cannot read another agent's leads, an unauthenticated user gets 401
- **Break it:** remove a permission check and confirm the tests fail. Optional: repeat this with PostgreSQL row-level security if you move to Supabase.

## M3: RAG over listings
**Demo:** ask a question in French or English and get an answer with cited listings.
- [ ] Chunk and embed listings on CPU
- [ ] Retrieval endpoint returning top-k listings with scores
- [ ] Answer generation that cites listing IDs and refuses when nothing relevant is found
- [ ] **Evaluation set** of 30 questions with expected listings, plus a script that reports hit rate
- [ ] Record results for at least two chunk sizes in `docs/eval.md`
- **Break it:** put an instruction inside a listing description ("ignore previous instructions...") and see what the assistant does. Keep this case for M5.

## M4: Agent and guardrails
**Demo:** the assistant searches listings, creates a lead, and proposes a visit, with limits.
- [ ] `LLMClient` interface with Gemini, OpenRouter, and fake implementations
- [ ] Retry with exponential backoff on 429 and 503 errors, plus a fallback provider
- [ ] Tools: `search_listings`, `create_lead`, `book_visit`, `escalate_to_human`
- [ ] **Guardrails:** tool allowlist, iteration cap, validated tool arguments, human approval before booking, PII redaction before text is sent to the LLM
- [ ] Every agent action written to `audit_log`
- [ ] Prompt files versioned in `prompts/`
- **Break it:** trigger a 429 on purpose and confirm the fallback works.

## M5: Red teaming and detection
**Demo:** a report showing attack success rate before and after your fixes.
- [ ] Prompt-injection test suite (at least 25 cases): direct injection, injection via listing text, system-prompt leak attempts, tool-abuse attempts, data exfiltration attempts
- [ ] Map each case to the OWASP Top 10 for LLM Applications
- [ ] Run the suite, record the **baseline** attack success rate, apply fixes, run again
- [ ] Optional: try promptfoo or garak for automation (check their current docs first)
- [ ] n8n workflow: webhook to AI service to alert, with an error workflow, firing on repeated blocked prompts or failed logins
- [ ] Scam-listing detector: simple rules plus a scikit-learn model on synthetic data (price far below market, copied text, suspicious contact patterns)
- **Break it:** make the AI service fail and confirm the n8n error workflow alerts you.

## M6: CI and polish
**Demo:** a repo a stranger can clone, run, and trust.
- [ ] GitHub Actions on every push: `pytest`, gitleaks, Semgrep, Bandit, `pip-audit`, `npm audit`
- [ ] Final `docs/threat-model.md` and `docs/risk-register.md` (risk, likelihood, impact, mitigation, status)
- [ ] `docs/security-report.md`: before/after results from M5 and what is still open
- [ ] Short compliance note mapping controls to Morocco's data-protection law (09-08, CNDP) and ISO 27001-style controls (verify details before publishing)
- [ ] README with setup steps, architecture diagram, and screenshots
- [ ] 2-minute demo video
- [ ] Ask someone to follow the README from scratch and fix what confuses them

---

## Rules for AI sessions
- Start each session with: "Read CONTEXT.md and PLAN.md, then do only task X."
- After each task: run tests, review the diff for security issues, commit.
- Never accept code you cannot explain. Ask the AI to explain it, then re-explain it in the journal.
- If the model starts looping or changing unrelated files, stop, roll back with git, and restart with a smaller task.

## Open decisions
- [ ] SQLite only, or move to PostgreSQL/Supabase for row-level security? (decide at M2)
- [ ] Chroma or SQLite for vectors? (decide at M3)
- [ ] Which offer or goal this project targets (affects what to polish)
