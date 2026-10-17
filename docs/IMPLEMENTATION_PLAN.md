# Implementation Plan

Priority: Correctness → Capital Safety → Realistic Execution → Measurable
Performance → Reliability → UI → Optimisation.

| Phase | Scope | Exit criteria | Status |
|---|---|---|---|
| 0 | Spec review | Owner approval | ✅ 2026-10-17 |
| 1 | Research and architecture docs; repo scaffold; CI with secret scanning | Docs merged; CI green | ✅ this branch |
| 2a | Public-data layer: discovery and rollover, official index poller, BBO poller, data health, Postgres recorder, read-only API | Recorder runs unattended; tests green; live smoke run recorded | ✅ this branch (see README for results) |
| 2b | Authenticated markets WS → local L2 book, integrity checks, WS-vs-REST reconciliation | Revised (REST is CDN-cached, see RESEARCH_AUDIT §1.4a): 0 invalid frames; ≥99% of REST BBO values corroborated by WS history once history is sufficient; 24 h soak | ✅ implemented and live-tested (≤12 min runs); 24 h soak pending |
| 2c | Next.js terminal UI on real data (header, BTC chart, 15m/1h panels, book, data-health) | Playwright e2e; no fixture data reachable in prod build | needs Node ≥20 locally |
| 3 | Fee engine (versioned, Decimal, banker's rounding, cumulative cap); paper execution (long/short sweep on one book, maker queue model, 4 profiles, latency, 5 s stopgap rejection); central risk engine; ledger; settlement; restart recovery | 20 required test classes pass; restart-recovery test | — |
| 4 | Strategy framework; B baseline calibration on public history; A as an incremental feature; C once data exists; replay engine; walk-forward reports | Reports with conservative profile and bootstrap CIs | — |
| 5 | Smart Money: document UNAVAILABLE for US | Doc only | — |
| 6 | QA: stress, recovery, security review, PR with test report | Owner review | — |

## Local prerequisites found on this machine (2026-10-17)

- Python 3.13.5 ✅
- PostgreSQL 17 (Homebrew) ✅. Not running as a service. `scripts/dev-db.sh` runs a project-local cluster on port 54329.
- **Docker: not installed.** `docker-compose.yml` is provided but unverified here.
- **Node.js: not installed.** This blocks Phase 2c.
- **gh CLI: not installed.** This blocks GitHub repo creation.

## Live-trading requirements not yet approved

None of these is implemented. Each needs separate owner authorisation:

1. Trading-scoped API credentials and verified permission scopes
2. `LiveExecutionEngine` implementation (preview → submit → reconcile), reviewed
3. Removal of the code-level boundary (SECURITY §3) via a dedicated PR
4. Uncertain-outcome recovery tested against the venue's real behaviour
5. Balance and position reconciliation against `/v1/portfolio` and `/v1/account`
6. Emergency cancel-all path tested
7. Separate deployment with TLS, authentication, alerting, and on-call
8. Regulatory/KYC confirmation that API trading is permitted on the owner's account
9. Explicit written go-live confirmation by the owner
