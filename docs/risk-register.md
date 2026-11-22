# DarPilot Risk Register

**Version:** 1.0  
**Date:** 2026-11-22  
**Owner:** DarPilot Security Team  

This register documents all identified risks, their assessment, mitigations, and current status. Risks are derived from the threat model (STRIDE) and adversarial testing results.

---

## Risk Scoring Methodology

| Likelihood | Score | Impact | Score |
|------------|-------|--------|-------|
| Very High  | 5     | Critical (data breach, full compromise) | 5 |
| High       | 4     | High (major functionality loss) | 4 |
| Medium     | 3     | Medium (partial loss, recoverable) | 3 |
| Low        | 2     | Low (minor inconvenience) | 2 |
| Very Low   | 1     | Negligible | 1 |

**Risk Score = Likelihood × Impact** (1–25)

| Risk Level | Score Range | Action |
|------------|-------------|--------|
| Critical   | 20–25       | Immediate mitigation required |
| High       | 12–19       | Mitigate within sprint |
| Medium     | 6–11        | Mitigate within release |
| Low        | 1–5         | Accept with monitoring |

---

## Risk Register

| ID | Risk Description | Likelihood | Impact | Score | Level | Mitigation | Status | Residual Risk |
|----|------------------|------------|--------|-------|-------|------------|--------|---------------|
| **R-01** | Prompt injection via malicious listing text (indirect RAG injection) | 4 | 5 | 20 | Critical | • 30+ regex patterns for injection detection<br>• Input validation before LLM call<br>• PII redaction<br>• Template-based FakeLLMClient for tests<br>• 27 adversarial tests (100% pass) | **MITIGATED** | Low — new patterns may emerge; monitored via n8n alerts |
| **R-02** | System prompt / tool schema leakage to user | 3 | 5 | 15 | High | • Injection detection for prompt echo/leak<br>• System prompt excluded from user context<br>• FakeLLMClient refuses system prompt requests<br>• Adversarial tests verify block | **MITIGATED** | Low — LLM behavior can be non-deterministic |
| **R-03** | SQL injection via unparameterized queries | 2 | 5 | 10 | Medium | • 100% parameterized queries (`?` placeholders)<br>• Pydantic validation on all endpoints<br>• Database CHECK constraints<br>• Tests confirm payloads stored literally | **MITIGATED** | Very Low — no string interpolation anywhere |
| **R-04** | Cross-agent lead access (IDOR) | 3 | 4 | 12 | High | • Server-side RBAC on every endpoint<br>• `require_role` + ownership checks<br>• Authorization tests: viewer→403, agent→own only<br>• Regression tests catch removed checks | **MITIGATED** | Low — logic bugs possible but tested |
| **R-05** | Role escalation (viewer → agent/admin) | 2 | 5 | 10 | Medium | • Short-lived JWT with role claim<br>• Server-side role enforcement<br>• Invalid/expired token → 401<br>• Regression tests | **MITIGATED** | Very Low |
| **R-06** | LLM cost flooding / DoS via free-tier abuse | 3 | 3 | 9 | Medium | • Input length limit (2000 chars)<br>• Iteration cap (5 tool calls)<br>• Exponential backoff + fallback provider<br>• Login rate limiting (5/min)<br>• *Future: API gateway rate limiting* | **PARTIAL** | Medium — free-tier limits are hard constraint |
| **R-07** | PII leakage to third-party LLM provider | 2 | 5 | 10 | Medium | • PII redaction (phone, email) before LLM call<br>• FakeLLMClient used in tests/CI<br>• Audit logs exclude PII<br>• *Future: On-premise LLM option* | **MITIGATED** | Low — redaction may miss edge cases |
| **R-08** | Unvalidated agent tool execution (hallucination/abuse) | 3 | 4 | 12 | High | • Tool allowlist (4 tools only)<br>• JSON Schema validation on every call<br>• Human approval for `book_visit`<br>• All actions logged to audit_log | **MITIGATED** | Low |
| **R-09** | Spoofing via stolen JWT/token | 2 | 4 | 8 | Medium | • Short-lived tokens (30 min)<br>• Secure/HttpOnly cookies<br>• CORS locked to configured origins<br>• Security headers (CSP, X-Frame-Options) | **MITIGATED** | Low |
| **R-10** | Repudiation of agent actions (no audit trail) | 2 | 3 | 6 | Medium | • Every tool call logged to `audit_log`<br>• Structured JSON details (tool, args, success/error)<br>• Failed/blocked tools also logged<br>• n8n alerts on repeated blocked prompts | **MITIGATED** | Very Low |
| **R-11** | Scam/fraudulent listings in database | 3 | 4 | 12 | High | • Rule-based detector: price anomalies, duplicates, suspicious contacts/text<br>• ML anomaly detection (Isolation Forest + TF-IDF)<br>• 16 tests covering all detection rules | **MITIGATED** | Low — new scam patterns require rule updates |
| **R-12** | LLM provider outage / API key rotation | 3 | 3 | 9 | Medium | • ResilientLLMClient: Gemini → OpenRouter → Fake fallback<br>• 429/503 exponential backoff with jitter<br>• n8n error workflow alerts on AI service failure | **PARTIAL** | Medium — simultaneous provider outage possible |
| **R-13** | Data poisoning via synthetic listings | 2 | 3 | 6 | Medium | • Synthetic data only (no real user data)<br>• Duplicate/near-duplicate detection<br>• Embeddings recomputed on rebuild | **MITIGATED** | Low |
| **R-14** | Zero-day prompt injection bypass | 3 | 4 | 12 | High | • Monitoring blocked prompts via n8n<br>• Regex patterns updated iteratively<br>• Adversarial test suite run on every change | **ACCEPTED WITH MONITORING** | Medium — unknown unknowns |
| **R-15** | SQLite concurrency bottleneck | 2 | 2 | 4 | Low | • Acceptable for demo scale<br>• PostgreSQL migration path documented<br>• WAL mode enabled | **ACCEPTED** | Low |

---

## Risk Treatment Summary

| Treatment | Count | Risks |
|-----------|-------|-------|
| **Mitigated** | 10 | R-01, R-02, R-03, R-04, R-05, R-07, R-08, R-09, R-10, R-11, R-13 |
| **Partial** | 3 | R-06, R-12 |
| **Accepted with Monitoring** | 1 | R-14 |
| **Accepted** | 1 | R-15 |

**Total:** 15 risks

---

## Key Performance Indicators (KPIs)

| KPI | Target | Current | Measurement |
|-----|--------|---------|-------------|
| Adversarial defense rate | 100% | 100% (27/27) | Automated test suite |
| SQL injection block rate | 100% | 100% | Automated tests |
| Authorization test pass rate | 100% | 100% | Automated tests |
| Mean time to detect (blocked prompts) | < 5 min | Real-time | n8n webhook + email |
| Mean time to detect (AI service error) | < 2 min | Real-time | n8n error workflow |
| Scam detection recall | > 90% | 100% on synthetic | Test suite |
| Secret leak detection | 100% | 100% | gitleaks pre-commit + CI |
| Dependency vulnerability scan | Weekly | On every push | GitHub Actions |

---

## Review Schedule

| Review | Frequency | Participants | Artifacts |
|--------|-----------|--------------|-----------|
| Risk register review | Monthly | Security lead, Dev lead | Updated risk register |
| Adversarial test run | On every PR | CI pipeline | Test reports |
| Dependency audit | Weekly | CI pipeline | pip-audit, npm audit |
| Threat model review | Quarterly | Security team, Architect | Updated threat model |
| Penetration test | Annually (or major release) | External tester | Pentest report |

---

*Document approved by: Security Lead*  
*Next review: 2026-12-22*