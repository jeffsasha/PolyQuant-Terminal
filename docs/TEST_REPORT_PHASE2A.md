# Test Report — Phase 1 + 2a

Date: 2026-10-17. Machine: macOS (Darwin 25.5), Python 3.13.5, PostgreSQL 17.11 (project-local cluster).
All results below were actually run. Nothing is extrapolated.

## Automated tests

`pytest -q` with `POLYQUANT_TEST_DATABASE_URL` set: **63 passed, 0 skipped, 0 failed** (pytest 9.1.1,
pytest-asyncio 1.4.0). `ruff check .`: clean. `pip-audit --skip-editable`: no known vulnerabilities, after
upgrading pytest 8.4.2 → 9.1.1 for PYSEC-2026-1845.

Mutation spot-checks: each change below was made deliberately, confirmed to fail tests, then reverted.

| Mutation | Caught by |
|---|---|
| Tie rule `>=` → `>` | `test_tie_settles_up` |
| Down ask = Up ask (instead of 1 − Up bid) | `test_bbo_derived_down_prices` |
| Reference offset 1 s → 0 s | 3 reference tests |
| Index poll `from == to` fix removed | `test_reference_single_second_poll_respects_from_before_to` |

Coverage against the 20 required test classes (spec §13). The ones in scope for 2a:

| # | Class | Status |
|---|---|---|
| 1 | Market discovery | ✅ metadata filter, both closed states queried, ETH/range excluded |
| 2 | 15m/1h rollover | ✅ unit (boundaries, overlap refusal) + **live** (06:15Z, 06:30Z) |
| 3 | Official settlement reference | ✅ unit on recorded data + **live** + `verify-references` |
| 4 | YES/NO mapping | ✅ long = Up, Down = 1 − opposite side; matches venue `shortQuote` |
| 5 | Time zones | ✅ ns timestamps, ET labels incl. DST end 2026-11-01 |
| 6 | Stale data | ✅ transitions emitted. **Live** stale/fresh events recorded. |
| 7 | WS disconnects | ⏳ Phase 2b (no WS yet). REST retry/back-off covered. |
| 8 | Order-book reconstruction | ⏳ Phase 2b |
| 9–16 | Slippage, fills, fees, payout, capital, duplicates, limits, kill switch | ⏳ Phase 3 |
| 17 | Database restart recovery | ✅ resume-from-last-point (unit + **live**: 2464/2464 seconds across 3 restarts), writer retry after DB error |
| 18 | Data leakage in backtests | ⏳ Phase 4 |
| 19 | Paper-vs-live isolation | ✅ GET-only client, host allowlist, constant `LIVE_TRADING_ENABLED=False` (env cannot override), live stub raises, static scan for order endpoints |
| 20 | (secrets) | ✅ log redaction, `SecretStr` masking |

## Live runs against the real public gateway

Three runs between 06:05 and 06:32 UTC: 4 min, 15 min, and 4 min. Final database state:

| Table | Rows |
|---|---|
| instruments | 27 |
| instrument_events | 115 |
| index_points | 2464 (05:50:43 → 06:31:46, **every second present**) |
| bbo_snapshots | 1096 |
| data_quality_events | 28 (16 fresh, 8 window_changed, 4 stale) |

Recorder totals: 0 dropped events and 0 write errors in every run.

- `polyquant verify-references --hours 2`: **10/10** resolved markets match the reference rule.
- Live settlement (06:00Z 15m window): `settlementPrice` 81482.11 = index(06:14:59Z) = the next window's
  `priceToBeat`. Venue flag 1 (Up) agrees with close ≥ open.
- Index freshness, observed age at receipt: p50 1.70 s, p95 2.26 s. This includes our deliberate 1 s lag so
  that only completed seconds are recorded.
- BBO request round trip: ~45–48 ms average.

## Bugs found by the live runs and fixed on this branch

1. **Index poll `from == to` → HTTP 400.** Every other 1 s poll failed, which roughly doubled reference latency.
   Fixed, with a regression test whose mock enforces the venue rule.
2. **Rate-limit starvation.** With index (HIGH) and BBO (NORMAL) saturating the 2 req/s budget, discovery
   (LOW) never ran again after start-up. Its feed went stale at 06:13Z. Fixed with priority aging (promotion
   after 3 s) and BBO pacing (`BBO_POLL_INTERVAL_S`, default 1 s). The next live run did 6 discoveries in 260 s.

## Venue behaviour observed (now in RESEARCH_AUDIT §1.2)

- An undocumented `MARKET_STATUS_RESOLVING` state appears between CLOSED and RESOLVED.
- BBO returns 404 for 40 s to 2.7 min after a window opens.
- The `/settlement` flag became available about 5 min after resolution (one observation).

## Not verified

- `docker-compose.yml` / `Dockerfile`: Docker isn't installed on this machine.
- CI workflow: not run yet (no GitHub repository exists yet).
- Behaviour over many hours: the longest continuous run was 15 min.
