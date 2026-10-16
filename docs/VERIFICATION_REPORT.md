# Local verification — October 16, 2026

This is a runnable **local paper-only collection and research terminal**, with reference-dependent entries deliberately blocked. It is not a claim that the entire approved engineering/research release has passed.

## Observed evidence

- Python 3.13.5, PostgreSQL 17.11, Node 24.19.0; dependency versions/locks retained.
- `PYTHONPATH=services:tests/unit .venv/bin/python -m pytest -q --tb=short`: 36 tests and 6 subtests passed after independent-review fixes.
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

## Independent review — snapshot eb7e825

A fresh reviewer inspected the complete range `84b5ba4..eb7e825` without session history, credentials, database state, or modifications. It independently ran 17 unit tests and 6 subtests and reproduced a recording race in temporary files. No critical live-order, reference-activation, or authentication escape was found.

Five Important findings were returned. Each was reproduced with a failing regression check, fixed, and rerun by the implementer:

1. Recorder append/seal race: use a shared reentrant lock, atomic fsynced manifests, and recoverable disk-to-database publication.
2. Orphaned crash recordings: scan durable segments/manifests on startup and register valid unsealed/unregistered captures. Preserve incomplete originals in quarantine and visibly halt collection for recovery; never delete or fabricate missing events.
3. Persistence I/O failures: latch collection/recorder unhealthy, persist `PERSISTENCE_FAILED` when the database permits, stop event publication, and report degraded health. Manual sealing follows the same failure boundary.
4. Native ownership/shutdown: validate PID process identity and cwd even after Next changes its title; wait for API/web termination before stopping PostgreSQL. Startup checks actual local readiness and reuses owned processes.
5. Daily halt rollover: persist `daily_halt_day` independently of the current account risk day. Same-day resume is denied; next-day explicit resume succeeds and never auto-resumes the account.

Minor findings were also addressed: known HTTP cache age now participates in freshness rejection; backup documentation correctly says owner-only permissions rather than encryption; stale design status text now points to this evidence report.

The reviewer judged the original snapshot financially safe for supervised blocked localhost inspection, but unsuitable for reliable collection until those fixes. The subsequent fixes were verified by the implementer, not independently reviewed a second time. Full release readiness remains **NO**.

Review exclusions and rulings: authoritative final settlement, authenticated streaming, full shared-engine replay/models/profitability, Docker/remote CI/24-hour/load/exhaustive crash recovery remain incomplete and must not be advertised as passed. Backup fidelity was source-only in the independent review; native restoration was separately executed by the implementer. User secret files were intentionally outside review scope.

## Final checks after review fixes

- Full backend suite: **36 passed, 6 subtests passed**, with one upstream Starlette TestClient deprecation warning. Includes deterministic concurrent sealing, restart recovery/quarantine, I/O failure halts, process-title ownership, next-day daily-halt resume, and known-cache-age freshness regressions.
- Real browser suite: **2 passed**. Adds actual SSE state arrival, persisted manual rejected order provenance, no page errors, and mobile overflow checks.
- Actual native shutdown/start/repeated-start: passed. A persisted momentum-account halt survived backend and PostgreSQL restart. Explicit resume returned reference-blocked with `reference_validated=false`; `/health` reported PAPER and `trading_ready=false`.
- Backup to owner-only local file and restore into a new disposable database: passed; the restored database was removed after verification. All application-table canonical row hashes, counts and selected account state matched. No production database was overwritten.
- Dark/light desktop and 390px mobile screenshots inspected. Scoped table CSS prevents chart clipping; theme changes now update the chart palette without discarding loaded candles. Final production Webpack build and browser rerun recorded at handoff.
- Generated local login/database secret scan of tracked/candidate files: passed before the review snapshot. This is a specific generated-secret check, not a comprehensive secret-scanning or dependency-vulnerability certification.

The application remains bound to `127.0.0.1:3000` (web), `127.0.0.1:8000` (API), and `127.0.0.1:55432` (database). No real order was sent, and no user exchange credentials were loaded.

Final handoff rerun: production Webpack build/TypeScript passed; 36 Python tests + 6 subtests passed; both actual Chromium tests passed on the rebuilt running terminal. Complete table-hash backup/restore comparison passed. Services left running locally at the owner’s request.
