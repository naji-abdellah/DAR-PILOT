# DarPilot Compliance Note

**Version:** 1.0  
**Date:** 2026-11-22  
**Scope:** Moroccan Law 09-08 (Data Protection) & ISO/IEC 27001:2022  

---

## Disclaimer

> **This document is for educational/project demonstration purposes only.**  
> DarPilot uses **synthetic data only** — no real personal data is processed.  
> This compliance mapping is a **best-effort interpretation** by a student project team and **does not constitute legal advice**. Consult a qualified Moroccan data protection attorney for production deployments.

---

## 1. Morocco Law 09-08 (Loi 09-08 relative à la protection des personnes physiques à l'égard du traitement des données à caractère personnel)

### Overview
Law 09-08 (promulgated 2009, aligned with EU Directive 95/46/EC, predecessor to GDPR) establishes principles for personal data processing in Morocco. Enforced by the **CNDP (Commission Nationale de contrôle de la Protection des Données à caractère Personnel)**.

### Key Principles & DarPilot Implementation

| Article | Principle | DarPilot Implementation | Evidence |
|---------|-----------|------------------------|----------|
| **Art. 3** | Lawful, fair, transparent processing | • Synthetic data only — no real personal data<br>• Privacy notice in README<br>• Explicit consent for lead capture (user submits form) | `frontend/app/leads/new/form.tsx`, `data/generate_listings.py` |
| **Art. 4** | Purpose limitation | • Lead data used only for visit scheduling<br>• Listing data used only for RAG search<br>• No secondary use (marketing, profiling) | `backend/services.py` (`create_lead`, `create_visit`) |
| **Art. 5** | Data minimization | • Lead form collects only: name, phone, email, message<br>• No SSN, ID numbers, financial data<br>• PII redacted before LLM calls | `backend/routes.py` (`LeadCreate` model), `ai/agent.py` (`redact_pii`) |
| **Art. 6** | Accuracy | • Users can update leads via agent dashboard<br>• Agents can correct listing data | `frontend/app/dashboard/page.tsx` |
| **Art. 7** | Storage limitation | • No automated deletion policy implemented (demo)<br>• *Future: Retention schedule + automated purge* | — |
| **Art. 8** | Security of processing | • Bcrypt password hashing<br>• Parameterized SQL (no injection)<br>• TLS/HTTPS enforced<br>• Audit logging of all actions<br>• Security headers (CSP, HSTS, etc.) | `backend/auth.py`, `backend/database.py`, `backend/app.py`, `ai/agent.py` |
| **Art. 9** | Confidentiality | • Role-based access (admin/agent/viewer)<br>• Agents see only their listings/leads<br>• Admins see all<br>• JWT with short expiry (30 min) | `backend/auth.py`, `backend/services.py` (`get_lead_for_user`) |
| **Art. 10** | Data subject rights | • Access: Not implemented (demo)<br>• Rectification: Agent dashboard edit<br>• Erasure: Not implemented (demo)<br>• Objection: Not implemented (demo)<br>• *Future: Data subject portal* | `frontend/app/dashboard/page.tsx` |
| **Art. 11** | Automated decisions | • No fully automated decisions affecting rights<br>• Agent tool calls require human approval for visits<br>• RAG answers cite sources, refuse on low confidence | `ai/agent.py` (`book_visit` requires approval), `backend/routes.py` (`/ask`) |
| **Art. 12** | Transfer to third parties | • LLM providers (Gemini/OpenRouter) receive redacted prompts<br>• PII (phone, email) stripped before transmission<br>• No other third-party data sharing | `ai/agent.py` (`redact_pii`), `ai/llm.py` (`ResilientLLMClient`) |
| **Art. 13** | Prior authorization | • Not required for synthetic data demo<br>• *Production: CNDP declaration/authorization required* | — |

### CNDP Registration
- **Status:** Not registered (demo project, synthetic data)
- **Production requirement:** Declaration to CNDP before processing real personal data (Art. 22-24)
- **DPO:** Not appointed (demo) — required for production (Art. 25)

---

## 2. ISO/IEC 27001:2022 Mapping

DarPilot implements controls from **Annex A** of ISO 27001:2022. This is a **selective implementation** suitable for a demo project.

| Control | Title | Implementation Status | Evidence |
|---------|-------|----------------------|----------|
| **A.5.1** | Policies for information security | ✅ Partial | Security headers, RBAC, audit logging documented in code |
| **A.5.2** | Information security roles | ✅ Partial | Admin/Agent/Viewer roles defined; no formal RACI |
| **A.5.3** | Segregation of duties | ✅ | Dev/test/prod separation via CI; admin vs agent vs viewer |
| **A.5.4** | Management responsibilities | ❌ | Demo project — no formal management structure |
| **A.5.5** | Contact with authorities | ❌ | No CNDP contact established |
| **A.5.6** | Contact with special interest groups | ❌ | N/A |
| **A.5.7** | Threat intelligence | ✅ | Adversarial test suite (27 cases), OWASP LLM Top 10 mapping |
| **A.5.8** | Information security in project management | ✅ | Secure-by-design milestones M0-M6, threat model |
| **A.5.9** | Inventory of assets | ✅ | Threat model lists assets (leads, listings, LLM creds, audit logs, tools) |
| **A.5.10** | Acceptable use of assets | ❌ | No formal policy (demo) |
| **A.5.11** | Return of assets | ❌ | N/A |
| **A.5.12** | Classification of information | ✅ | Synthetic vs real data distinction; PII vs non-PII |
| **A.5.13** | Labelling of information | ❌ | No formal labelling |
| **A.5.14** | Information transfer | ✅ | PII redacted before LLM transfer; HTTPS enforced |
| **A.5.15** | Access control policy | ✅ | RBAC implemented in code |
| **A.5.16** | Identity management | ✅ | User registration, JWT tokens, bcrypt |
| **A.5.17** | Authentication information | ✅ | Bcrypt hashing, short-lived JWT, secure cookies |
| **A.5.18** | Access rights | ✅ | `require_role` dependency, ownership checks |
| **A.5.19** | Information security in supplier relationships | ✅ | LLM provider fallback chain; free-tier only |
| **A.5.20** | Incident management | ✅ | n8n alerting on blocked prompts, failed logins, AI errors |
| **A.5.21** | Information security continuity | ✅ | FakeLLMClient fallback; resilient LLM client chain |
| **A.5.22** | Compliance | ✅ Partial | This document; CNDP mapping |
| **A.5.23** | Information security reviews | ✅ | CI pipeline runs on every push |
| **A.6.1** | Internal organization | ❌ | Demo — single developer |
| **A.6.2** | Mobile devices | ❌ | N/A |
| **A.6.3** | Teleworking | ❌ | N/A |
| **A.7.1** | Screening | ❌ | N/A |
| **A.7.2** | Terms and conditions | ❌ | N/A |
| **A.7.3** | Security awareness | ✅ | Developer learning journal, threat model |
| **A.7.4** | Disciplinary process | ❌ | N/A |
| **A.7.5** | Termination | ❌ | N/A |
| **A.7.6** | Confidentiality agreements | ❌ | N/A |
| **A.8.1** | User endpoint devices | ❌ | N/A |
| **A.8.2** | Privileged access | ✅ | Admin role separate from agent/viewer |
| **A.8.3** | Information access restriction | ✅ | RBAC + ownership checks |
| **A.8.4** | Source code access | ✅ | GitHub private repo (assumed); gitleaks on commit |
| **A.8.5** | Secure authentication | ✅ | Bcrypt + JWT + secure cookies |
| **A.8.6** | Capacity management | ❌ | SQLite demo scale; no monitoring |
| **A.8.7** | Malware protection | ❌ | Dependency scanning (pip-audit, npm audit) |
| **A.8.8** | Technical vulnerability management | ✅ | CI pipeline: Bandit, Semgrep, pip-audit, npm audit |
| **A.8.9** | Configuration management | ✅ | `.env.example`, `.gitignore`, Docker-free |
| **A.8.10** | Information deletion | ❌ | No retention policy (demo) |
| **A.8.11** | Data masking | ✅ | PII redaction before LLM calls |
| **A.8.12** | Data leakage prevention | ✅ | PII redaction, audit logs, n8n alerts |
| **A.8.13** | Information backup | ❌ | No backup strategy (demo) |
| **A.8.14** | Redundancy | ❌ | Single SQLite file; no HA |
| **A.8.15** | Logging | ✅ | `audit_log` table, structured JSON, n8n webhooks |
| **A.8.16** | Monitoring | ✅ | n8n workflows, CI pipeline reports |
| **A.8.17** | Clock synchronization | ✅ | SQLite `datetime('now')`, JWT `iat`/`exp` |
| **A.8.18** | Protection against malware | ✅ | Dependency scanning, no external executables |
| **A.8.19** | Installation of software | ✅ | `requirements.txt`, `package.json`, CI installs |
| **A.8.20** | Network controls | ✅ | CORS locked, security headers, localhost dev |
| **A.8.21** | Secure network engineering | ❌ | No network segmentation (demo) |
| **A.8.22** | Web application security | ✅ | FastAPI + Pydantic validation, CSP, rate limiting |
| **A.8.23** | API security | ✅ | Parameterized queries, RBAC, rate limiting, input validation |
| **A.8.24** | Secure coding | ✅ | Type hints, small functions, parameterized SQL, no eval |
| **A.8.25** | Secure development lifecycle | ✅ | Milestone-based (M0-M6), threat model, adversarial tests |
| **A.8.26** | Application security testing | ✅ | 122 automated tests, adversarial suite, CI pipeline |
| **A.8.27** | Secure system architecture | ✅ | Layered (routes/services/repositories), RAG isolation |
| **A.8.28** | Secure coding environment | ✅ | GitHub Actions, gitleaks pre-commit |
| **A.8.29** | Outsourced development | ❌ | N/A |
| **A.8.30** | System change control | ✅ | Git + PR + CI pipeline |
| **A.8.31** | Separation of environments | ✅ | Dev/test use throwaway DB; CI isolation |
| **A.8.32** | Information security incident management | ✅ | n8n alerts, audit logs, structured details |

---

## 3. Gap Analysis & Remediation Plan

### High Priority (Production Readiness)

| Gap | Risk | Remediation | Timeline |
|-----|------|-------------|----------|
| No CNDP declaration | Legal non-compliance | Register with CNDP before processing real data | Pre-launch |
| No Data Protection Officer | Legal requirement (Art. 25) | Appoint DPO | Pre-launch |
| No data subject rights portal | Art. 10 rights unenforceable | Build self-service portal (access, rectify, erase) | Sprint 1 |
| No retention/deletion policy | Art. 7 violation | Implement automated purge (e.g., 2 years for leads) | Sprint 1 |
| No formal security policies | ISO A.5.1 | Document policies (access, acceptable use, incident response) | Sprint 2 |
| No backup/DR strategy | ISO A.8.13, A.8.14 | Implement automated SQLite backup + DR test | Sprint 2 |
| No vulnerability management SLA | ISO A.8.8 | Define patching SLAs (critical: 72h, high: 7d) | Sprint 2 |
| No penetration testing | ISO A.8.26 | Annual third-party pentest | Annual |

### Medium Priority

| Gap | Remediation | Timeline |
|-----|-------------|----------|
| Formal risk assessment process | Implement quarterly risk reviews | Sprint 3 |
| Supplier security assessment (LLM providers) | Document provider security posture | Sprint 3 |
| Business continuity plan | Define RTO/RPO, test failover | Sprint 3 |
| Security awareness training | Annual training for all developers | Ongoing |

---

## 4. Verification Evidence

| Artifact | Location | Standard |
|----------|----------|----------|
| Threat model (STRIDE) | `docs/threat-model.md` | ISO A.5.7, A.5.8, A.8.27 |
| Risk register | `docs/risk-register.md` | ISO A.5.7, A.5.12 |
| Security report | `docs/security-report.md` | ISO A.5.7, A.8.26 |
| Adversarial test suite | `tests/test_adversarial.py` | ISO A.5.7, A.8.26 |
| CI security pipeline | `.github/workflows/ci.yml` | ISO A.8.8, A.8.26, A.8.28 |
| Gitleaks pre-commit | `.git/hooks/pre-commit` | ISO A.8.4, A.8.28 |
| Audit logging | `backend/services.py`, `ai/agent.py` | ISO A.8.15, Law 09-08 Art. 8 |
| PII redaction | `ai/agent.py` | Law 09-08 Art. 5, 8, 12 |
| RBAC implementation | `backend/auth.py`, `backend/routes.py` | Law 09-08 Art. 9, ISO A.5.15, A.5.18 |
| Adversarial defense rate | 100% (27/27) | ISO A.5.7, A.8.26 |

---

## 5. Attestation

This compliance note was prepared by the DarPilot project team as part of a student learning exercise in secure AI engineering. It represents a **good-faith effort** to map implemented controls to Moroccan Law 09-08 and ISO 27001:2022.

**Prepared by:** DarPilot Security Team  
**Date:** 2026-11-22  
**Next review:** 2026-12-22

> **Reminder:** This document is for educational purposes. Production deployment requires legal review by qualified Moroccan counsel and CNDP registration.