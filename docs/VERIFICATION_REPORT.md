# Local verification — October 16, 2026

This is a runnable **local paper-only collection and research terminal**, with reference-dependent entries deliberately blocked. It is not a claim that the entire approved engineering/research release has passed.

## Observed evidence

- Python 3.13.5, PostgreSQL 17.11, Node 24.19.0; dependency versions/locks retained.
- `PYTHONPATH=services:tests/unit .venv/bin/python -m pytest -q --tb=short`: 28 tests and 6 subtests passed before the additional account-performance test. Full final count will be recorded after review.
- Next.js 16.4.2 production Webpack build: PASS, including TypeScript checks. Turbopack could not spawn its CSS worker on this host, including after allowing its internal port; Webpack is the documented build path.
- Actual Chromium E2E: PASS. Login, visible PAPER boundary, absent live switch, reference block, dark/light theme, emergency stop, page-reload halt persistence, and manual resume back into the reference block.
- Public production API login/state check at approximately 20:36 UTC: both 15m and 1h typed BTC markets, real Coinbase spot and US BRTI values, three isolated $1,000 accounts. Public books intermittently unavailable; some responses stale. These limitations are visible, not bypassed.
- Reference reconstruction: FAIL (five mismatches retained in the research evidence). It cannot be enabled through UI or environment configuration.
- Authenticated market stream: NOT CONFIGURED / UNVERIFIED. Owner will add backend credentials later.
- Screenshot: [local-terminal.png](images/local-terminal.png). Captured market data can already be stale by the time it is viewed.

## Acceptance status

`PARTIAL` means some deterministic evidence exists, but the complete criterion is not proved. Test fixtures never establish venue availability or profitability.

| Criterion | Status | Evidence / remaining gate |
|---|---|---|
| A01 | PASS for public discovery | Typed US BTC 15m/1h listings captured; focused bounded discovery; public books not continuously available |
| A02 | PARTIAL | Active markets rediscovered; required two observed boundaries per cadence not certified |
| A03 | FAIL / ACTIVATION BLOCKED | Reference discrepancies documented; no artificial threshold correction |
| A04 | PARTIAL | DOWN complement execution fixtures; final payout mapping not independently observed |
| A05 | PARTIAL | UTC/New York DST risk-day tests; terminal displays UTC explicitly |
| A06 | PARTIAL | Source/receive-age and reference gates tested; full clock/backlog fault drills pending |
| A07 | BLOCKED | Credentialed stream/reconnect semantics unverified |
| A08 | PASS deterministic | Normalized sorted, noncrossed, valid books |
| A09–A12 | PASS deterministic core | Depth sweeps, limits, maker no-fill, fee vectors and effective times; full venue granularity remains uncertain |
| A13 | PARTIAL / NOT ENABLED | Exactly-once/correction ledger fixtures; no authoritative production settlement poller |
| A14–A16 | PASS deterministic core | Full-loss fees, reservations, concurrent cadence slot, independent accounts and arrivals |
| A17 | PARTIAL | Persisted manual/daily halt, same-day lock and cooldown fixtures; no full operational day observed |
| A18 | PARTIAL | Reservation/fill transactions and restart reconciliation; exhaustive crash-boundary faults not run |
| A19 | PARTIAL | Causal event ordering, embargo, Brier/log loss helpers; no fitted model or full engine replay report |
| A20 | PASS deterministic boundary | Live flag refused, fixed GET transport, live stub throws, no order SDK client or UI live toggle |
| A21 | PARTIAL | Quota/headroom/checksum fixtures; full storage-failure settlement drill pending |
| A22 | PASS core local auth | Scrypt, session, rate limits, CSRF/Host/Origin tests; frontend launched without backend credentials |
| A23 | PARTIAL | Real login/theme/stop/reload/resume E2E; no fabricated trade/fill to claim blocked entry flow passes |
| A24 | NOT RUN | Ten-minute 10× replay/load drill |
| A25 | NOT RUN | 24-hour data continuity/finality observation |
| A26 | BLOCKED / PARTIAL | Docker absent; native startup verified; Compose provided but not executed |
| A27 | NOT RUN | No remote private repository, PR, or executed CI security scans |
| A28 | PARTIAL / INSUFFICIENT EVIDENCE | Isolated ledger/account metrics; no fitted strategies, qualifying sample history or performance evidence |

## Scope and release ruling

The owner's latest instruction asks for the local terminal while keeping the failed reference gate disabled. Deliver this explicitly limited local build. Do not describe the full 16-task release, strategy backtesting, authenticated feed reliability, or financial acceptance as complete. Reference-dependent automation and models remain unavailable until their separate evidence gates pass.

Automatic official settlement, full shared-engine replay, offline fitted model artifacts, a 30-day/200-window research dataset, comprehensive fault/load/24-hour observation, executed Compose, and private remote PR/CI remain outstanding. The terminal labels these limitations and retains holdings rather than inventing exits.

Independent review and final verification results will be appended below. No real order or trading credential was used in these checks.
