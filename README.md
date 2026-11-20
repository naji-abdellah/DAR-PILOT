# DarPilot 🇲🇦

DarPilot is a secure-by-design AI assistant for a fictional Moroccan real-estate agency. It answers questions about property listings using RAG, captures leads, and books visits through a tool-using AI agent.

## Core Focus: Secure-by-Design AI Engineering
- **Threat Modeling**: Systematic STRIDE evaluation of LLM & web application risks.
- **Authorization & Access Control**: Server-enforced role-based access control (RBAC).
- **Adversarial Robustness**: Red-teaming with prompt injection benchmark suites.
- **Guardrails & Auditing**: Strict tool argument validation, iteration caps, and detailed action audit logging.
- **Automated CI Security**: Automated secret scanning (Gitleaks), static analysis (Semgrep/Bandit), and dependency auditing.

## Architecture & Stack
- **Backend**: FastAPI, Python 3.11+, SQLite
- **Frontend**: Next.js + Tailwind CSS
- **LLM**: Gemini API / OpenRouter with fallback mechanisms
- **RAG**: `fastembed` embeddings (CPU-optimized), Chroma / SQLite
- **Automation**: n8n, GitHub Actions

## Getting Started
See [CONTEXT.md](./CONTEXT.md) and [PLAN.md](./PLAN.md) for project guidelines and implementation progress.
