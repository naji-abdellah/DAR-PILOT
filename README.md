# DarPilot 🇲🇦

DarPilot is a **secure-by-design AI assistant** for a fictional Moroccan real-estate agency. It answers questions about property listings using RAG, captures leads, and books visits through a tool-using AI agent.

## Core Focus: Secure-by-Design AI Engineering

- **Threat Modeling**: Systematic STRIDE evaluation of LLM & web application risks.
- **Authorization & Access Control**: Server-enforced role-based access control (RBAC).
- **Adversarial Robustness**: Red-teaming with prompt injection benchmark suites (100% defense rate).
- **Guardrails & Auditing**: Strict tool argument validation, iteration caps, and detailed action audit logging.
- **Automated CI Security**: Automated secret scanning (Gitleaks), static analysis (Semgrep/Bandit), and dependency auditing.

---

## Architecture

```mermaid
graph TB
    subgraph "Frontend (Next.js + Tailwind)"
        UI[User Interface]
        Dashboard[Agent Dashboard]
        Listings[Listings Page]
        LeadForm[Lead Capture Form]
    end

    subgraph "Backend API (FastAPI)"
        Auth[Auth: JWT + bcrypt]
        ListingsAPI[Listings CRUD]
        LeadsAPI[Leads CRUD]
        VisitsAPI[Visits CRUD]
        SearchAPI[/search + /ask]
        SecurityAPI[/security/*]
    end

    subgraph "AI Layer"
        Agent[Tool-Using Agent]
        Guardrails[Guardrails: allowlist, validation, PII redaction]
        Tools[Tools: search, create_lead, book_visit, escalate]
        LLMClient[ResilientLLMClient: Gemini → OpenRouter → Fake]
    end

    subgraph "RAG Pipeline"
        Embedder[fastembed bge-small-en-v1.5]
        VectorStore[(SQLite: rag_chunks)]
        Retriever[Cosine Similarity Search]
    end

    subgraph "Data Layer"
        DB[(SQLite: users, listings, leads, visits, audit_log)]
    end

    subgraph "Monitoring (n8n)"
        Alerting[Security Alerting Workflow]
        ErrorWF[AI Error Workflow]
    end

    UI --> Auth
    UI --> ListingsAPI
    UI --> LeadsAPI
    UI --> VisitsAPI
    Dashboard --> Agent
    Listings --> ListingsAPI
    LeadForm --> LeadsAPI
    SearchAPI --> Retriever
    Agent --> Guardrails
    Guardrails --> Tools
    Tools --> SearchAPI
    Tools --> LeadsAPI
    Tools --> VisitsAPI
    SearchAPI --> Retriever
    Retriever --> VectorStore
    Embedder --> VectorStore
    ListingsAPI --> DB
    LeadsAPI --> DB
    VisitsAPI --> DB
    SecurityAPI --> Alerting
    SecurityAPI --> ErrorWF
    Agent --> LLMClient
    LLMClient -->|Fallback Chain| Agent
```

---

## Quick Start

### Prerequisites

- **Python 3.11+** (tested on 3.11/3.12)
- **Node.js 20+** (for frontend)
- **Git**
- **No Docker required** — runs directly on host

### 1. Clone & Setup Backend

```bash
git clone https://github.com/your-org/darpilot.git
cd darpilot

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install Python dependencies
cd backend
pip install -r requirements.txt

# Generate synthetic data (100 listings)
cd ../data
python generate_listings.py

# Start backend (runs on http://localhost:8000)
cd ../backend
uvicorn app:app --reload --port 8000
```

### 2. Setup Frontend

```bash
# In a new terminal
cd frontend
npm install
npm run dev  # Runs on http://localhost:3000
```

### 3. (Optional) Start n8n for Monitoring

```bash
# In a new terminal
npx n8n start  # Runs on http://localhost:5678
# Import workflows from n8n/workflows/
```

### 4. Configure Environment

Copy `.env.example` to `.env` and fill in:

```bash
cp .env.example .env
# Edit .env with your API keys:
# GEMINI_API_KEY=your_key_here
# OPENROUTER_API_KEY=your_key_here
# DARPILOT_SECRET_KEY=your_secure_random_string
# N8N_WEBHOOK_URL=http://localhost:5678/webhook
```

---

## Demo Accounts

After generating data and starting the backend, register users via `POST /auth/register` or use the frontend:

| Role | Capabilities |
|------|--------------|
| **Admin** | All listings, all leads, user management |
| **Agent** | Own listings, own leads, create visits |
| **Viewer** | Read listings only |

---

## Running Tests

```bash
# Activate venv first
source .venv/bin/activate

# Run all tests (122 tests)
cd backend
pytest tests/ -v

# Run specific test suites
pytest tests/test_adversarial.py -v      # 27 adversarial tests
pytest tests/test_scam_detector.py -v    # 16 scam detector tests
pytest tests/test_n8n_integration.py -v  # 13 n8n integration tests
pytest tests/test_agent.py -v            # 30 agent/guardrail tests

# Frontend tests
cd ../frontend
npm run lint
npm run build
```

---

## Security Features Summary

| Feature | Implementation |
|---------|----------------|
| **Prompt Injection Defense** | 30+ regex patterns, 100% adversarial defense rate (27/27) |
| **SQL Injection Prevention** | 100% parameterized queries, Pydantic validation |
| **RBAC** | Admin/Agent/Viewer enforced server-side |
| **PII Protection** | Phone/email redacted before LLM calls |
| **Audit Logging** | Every tool call + blocked attempts logged |
| **LLM Resilience** | Exponential backoff + Gemini→OpenRouter→Fake fallback |
| **Secret Scanning** | Gitleaks pre-commit + CI |
| **SAST** | Bandit, Semgrep, pip-audit, npm audit in CI |
| **Monitoring** | n8n workflows for blocked prompts, failed logins, AI errors |

---

## Project Structure

```
darpilot/
├── backend/           # FastAPI application
│   ├── app.py         # Main app, CORS, security headers
│   ├── routes.py      # API endpoints
│   ├── services.py    # Business logic, validation, n8n alerts
│   ├── repositories.py# Parameterized SQL queries
│   ├── auth.py        # JWT, bcrypt, RBAC
│   ├── database.py    # SQLite connection management
│   ├── schema.sql     # Database schema
│   └── requirements.txt
├── frontend/          # Next.js + Tailwind
│   ├── app/           # App Router pages
│   ├── components/    # React components
│   └── lib/api.ts     # Typed API client
├── ai/                # AI Layer
│   ├── agent.py       # Tool-using agent + guardrails
│   ├── llm.py         # LLMClient implementations
│   ├── rag.py         # RAG pipeline (chunk, embed, search)
│   └── scam_detector.py # Rule-based + ML scam detection
├── prompts/           # Versioned prompt files
│   └── agent_system_v1.txt
├── data/              # Synthetic data generator
│   └── generate_listings.py
├── tests/             # Pytest test suites
│   ├── test_api.py           # 29 API + authz tests
│   ├── test_agent.py         # 30 agent/guardrail tests
│   ├── test_adversarial.py   # 27 adversarial tests
│   ├── test_scam_detector.py # 16 scam detector tests
│   ├── test_n8n_integration.py # 13 n8n tests
│   ├── test_rag.py           # 7 RAG tests
│   └── test_schema.py        # 4 schema tests
├── n8n/workflows/     # n8n monitoring workflows
├── scripts/           # Utility scripts
├── docs/              # Documentation
│   ├── threat-model.md
│   ├── risk-register.md
│   ├── security-report.md
│   ├── compliance.md
│   ├── eval.md
│   └── journal.md
├── .github/workflows/ # CI/CD pipeline
├── .env.example
├── PLAN.md
├── CONTEXT.md
└── README.md
```

---

## Screenshots

### Listings Page
![Listings](docs/screenshots/listings.png)

### Listing Detail
![Listing Detail](docs/screenshots/listing-detail.png)

### Agent Dashboard
![Dashboard](docs/screenshots/dashboard.png)

### Lead Capture Form
![Lead Form](docs/screenshots/lead-form.png)

### Adversarial Test Report
![Adversarial Report](docs/screenshots/adversarial-report.png)

*Place actual screenshots in `docs/screenshots/`*

---

## Milestone Progress

| Milestone | Status | Demo |
|-----------|--------|------|
| **M0** Setup & Threat Model | ✅ | Repo structure, gitleaks, threat model v0 |
| **M1** Data & API | ✅ | CRUD API, 21 tests, SQLi blocked |
| **M2** Auth & Roles | ✅ | JWT, RBAC, Next.js pages, 29 tests |
| **M3** RAG | ✅ | Search + ask, 94% hit rate, 7 tests |
| **M4** Agent & Guardrails | ✅ | 4 tools, PII redaction, audit log, 30 tests |
| **M5** Red Teaming | ✅ | 27 attacks (100% blocked), n8n, scam detector |
| **M6** CI & Polish | 🚧 | GitHub Actions, docs, README |

---

## Security Documentation

- [Threat Model](docs/threat-model.md) — STRIDE analysis, 14 threats, mitigations
- [Risk Register](docs/risk-register.md) — 15 risks scored, treatment plan
- [Security Report](docs/security-report.md) — Before/after adversarial results
- [Compliance Note](docs/compliance.md) — Morocco Law 09-08 & ISO 27001 mapping
- [Evaluation](docs/eval.md) — RAG hit rate methodology & results
- [Journal](docs/journal.md) — Learning progress & security insights

---

## License

MIT License — Educational project demonstrating secure AI engineering practices.

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Run `pytest tests/` and `npm run lint` before committing
4. Ensure gitleaks passes (no secrets)
5. Submit a PR

---

## Disclaimer

**This is a fictional demo project for learning secure AI engineering.**  
- Uses **synthetic data only** — no real personal data
- Not a production-ready real estate platform
- Compliance mappings are **educational interpretations**, not legal advice
- Consult qualified Moroccan legal counsel for production deployments