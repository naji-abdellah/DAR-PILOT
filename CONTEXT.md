# CONTEXT: read this before doing anything

## Project
DarPilot is an AI assistant for a **fictional** Moroccan real-estate agency. It answers questions about listings (RAG), captures leads, and books visits through a tool-using agent. The main goal is to show **secure-by-design AI engineering**: threat model, authorization tests, prompt-injection red teaming with measured results, guardrails, monitoring, and CI security checks.

The owner is a student learning AI and cybersecurity. The AI writes most of the code. The owner reviews it, learns from it, and must be able to explain every part.

## Constraints
- Windows laptop, **8 GB RAM, no GPU**. Keep memory use low.
- **Free tools only.** No paid APIs, no cloud billing.
- **No Docker** unless the owner asks. Run services directly (`uvicorn`, `npm run dev`, `npx n8n`).
- Free LLM tiers (Gemini, OpenRouter) have rate limits and can return 429 or 503 errors. Always handle them with retries and a fallback provider.
- **Synthetic data only.** Free-tier providers may use prompts for training, so never send real or confidential data.

## Stack
- Backend: Python 3.11+, FastAPI, SQLite (PostgreSQL optional later), `pytest`
- Frontend: Next.js + Tailwind
- LLM access: through an `LLMClient` interface (Gemini, OpenRouter, fake for tests)
- RAG: `fastembed` on CPU, Chroma or SQLite
- Automation: n8n via `npx n8n`, GitHub Actions

## Folder structure
```
darpilot/
  backend/        FastAPI app (routes, services, repositories, models)
  frontend/       Next.js app
  ai/             LLMClient, RAG, agent, guardrails
  prompts/        versioned prompt files
  tests/          pytest tests (unit, authorization, adversarial)
  data/           synthetic data generators (no real data)
  docs/           threat-model.md, risk-register.md, eval.md, security-report.md, journal.md
  .github/workflows/
  PLAN.md
  CONTEXT.md
  .env.example
```

## Coding conventions
- Small functions, clear names, type hints in Python.
- Layered code: routes call services, services call repositories. No SQL inside routes.
- Every new feature gets at least one test. Bug fixes get a regression test.
- Keep dependencies few and well known. Ask before adding a heavy one (anything that needs PyTorch or a GPU).

## Security rules (non-negotiable)
1. **Never** put secrets in code, tests, logs, or commits. Use `.env` (git-ignored) and keep `.env.example` updated.
2. Validate all input on the server: types, lengths, allowed values.
3. Use parameterized queries only. Never build SQL from strings.
4. Enforce authorization on the server for every endpoint. The UI is not a security control.
5. Least privilege: agent tools get only the access they need, and every tool argument is validated.
6. Treat all LLM input and output as untrusted, including listing text pulled from the database.
7. Log agent actions to `audit_log`, without logging secrets or personal data.
8. Do not invent library names. If unsure a package exists, say so and check before using it.

## How the AI should work
- Read `PLAN.md` and do **only the task the owner names**. Do not start the next task.
- Work in **small steps**. Before editing, say which files you will change.
- Do not touch unrelated files. Do not read or modify `.env`.
- After coding: run the tests, then give a short list of what changed and any security concerns you noticed.
- Explain new concepts briefly in plain language, since the owner is learning.
- When a task is done, update its checkbox in `PLAN.md`.
- If you hit a rate-limit or loop, stop and report instead of retrying endlessly.

## Decisions log
(Add dated entries here when the owner decides something, for example "SQLite for now, revisit at M2".)
