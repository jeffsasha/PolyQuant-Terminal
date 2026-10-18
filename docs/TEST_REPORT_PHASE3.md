# Test Report — Phase 3 (fees, paper execution, risk, ledger, settlement, restart recovery)

Date: 2026-10-17. All results below were actually run.

## Automated tests

`pytest -q` with the test database: **156 passed, 0 skipped**. `ruff`: clean. `pip-audit`: no known
vulnerabilities.

### Coverage of the spec's 20 required test classes

| # | Class | Where | Status |
|---|---|---|---|
| 1 | Market discovery | test_discovery_rollover | ✅ (2a) |
| 2 | 15m/1h rollover | test_discovery_rollover, test_l2_book (real boundary frames) | ✅ |
| 3 | Official settlement reference | test_settlement_phase_time + live verification | ✅ |
| 4 | YES/NO mapping | test_parsing_and_mapping, test_execution_model (Down sweeps the Up book) | ✅ |
| 5 | Time zones | ET labels, DST, fee boundaries in ET (test_fees) | ✅ |
| 6 | Stale market data | feed staleness; paper entry gates; stale WS at order arrival → reject | ✅ |
| 7 | WS disconnect/reconnect | test_ws_stream | ✅ |
| 8 | Order-book reconstruction | test_l2_book (full-book frames, validation, ordering) | ✅ |
| 9 | Slippage calculation | VWAP sweeps, adverse ticks, slippage/spread attribution per fill | ✅ |
| 10 | Partial fills | IOC partial + remainder cancel; partially-filled GTC with proportional reserve release | ✅ |
| 11 | Unfilled maker orders | touch ≠ fill (conservative); queue depletion; expiry at window end | ✅ |
| 12 | Fees and fee-date transitions | Θ formula, banker's rounding, cumulative cap, Oct 15 / Oct 19 versions, tier 1 maker = 0, unknown pre-Oct-7 schedule | ✅ |
| 13 | Settlement and payout | winner pays $1, loser $0, tie → Up, venue-outcome settlement, conflicts block | ✅ + live |
| 14 | Insufficient capital | risk gate | ✅ |
| 15 | Duplicate order prevention | client_order_id idempotency (DB unique) + duplicate open order | ✅ |
| 16 | Position and exposure limits | max positions, combined 5 %, per-horizon 3 %, per-trade 0.5 % | ✅ |
| 17 | Daily kill switch | loss > 2 % of start-of-day equity → halt; entries blocked, exits allowed; cancels working entries | ✅ |
| 18 | Database restart recovery | rebuild cash/reserved/positions; in-flight orders cancelled; resting orders re-queued; halts persist | ✅ |
| 19 | Data leakage in backtesting | — | ⏳ Phase 4 (no backtester yet) |
| 20 | Paper-vs-live isolation | no venue order path (tightened static test), live stub raises, optimistic profile refused, token-gated API | ✅ |

### Mutation checks

Each safeguard below was disabled deliberately, confirmed to make tests fail, then restored:

- in-flight cancel on restart
- proportional reserve release (initially survived, which exposed a missing partial-GTC test, now added)
- settlement-conflict block
- stale-book check at arrival
- kill switch cancelling working orders
- earlier: tie rule, Down-ask mirror, reference offset, `from == to` fix

## Live paper run (real venue data, PAPER only)

Market: BTC 15m 09:45–10:00 ET (13:45–14:00 UTC), conservative profile, $1,000 simulated capital.

| Step | Result |
|---|---|
| IOC BUY Up 7 @ limit 0.57 (book 0.54/0.55) | Filled 7 @ **0.56** (best ask + 1 conservative tick), arriving ~1.3 s after submit. Taker fee **$0.12** (exact 0.1199). Spread cost $0.035, slippage $0.07. Ledger: reserve 4.12 → buy 3.92 + fee 0.12 → release 4.12 |
| Passive BUY Down while holding Up | **Rejected:** `opposite_side_held` (by design: long/short netting is unverified) |
| BUY Up 500 | **Rejected** with all reasons: `trade_risk_exceeds_0.5%`, `exposure_exceeds_5%`, `15m_exposure_exceeds_3%` |
| Resolution | 14:00:02 CLOSED → 14:00:12 RESOLVING → 14:00:18 RESOLVED, settlement 81386.50 vs open 81372.73 → Up |
| Settlement | The `/settlement` flag was still unavailable at 14:04 (CDN-cached). After adding settlement from `outcomePrices`, a restart settled the position: payout **$7.00**, gross +$3.08, fees $0.12, **net +$2.96**. Sources: outcome_prices + price_rule |
| Recorder | 26,396 events, 0 dropped, 0 write errors |

**This is one trade. It demonstrates the pipeline, not an edge.**

## Bugs and wrong assumptions found in this phase (fixed)

1. **Settlement blocked on the cached flag.** The engine now settles from the uncached instrument's
   `outcomePrices` when it agrees with the price rule, and cross-checks the flag when present.
2. **Misleading PnL label.** `realized_net_after_fees` counted an open position's cost as realized. The endpoint
   now reports closed-position gross/fees/net and equity PnL separately.
3. **Duplicated fee-cap logic** in the engine and the schedule. Now a single shared helper.
4. **Static safety test too broad** (matched the paper engine's own `orders` dict). It was tightened to venue
   endpoints, SDK order calls and SDK imports other than `polymarket_us.auth`.

## Open items

- **Execution profiles are assumptions.** Latencies (250/750/2000 ms), haircuts and maker rules are not calibrated:
  there are no real order outcomes to calibrate against without live orders. Calibration options are listed in
  STRATEGY_RESEARCH.
- **Venue semantics not documented:** Down price convention, long/short netting, short collateral. The paper
  engine uses conservative assumptions and blocks the ambiguous cases.
- **Trade `quantity` unit (USD label) is unresolved,** so trades aren't used by the maker model. It uses book
  changes only.
- **Taker rebates** (weekly, volume-tiered) are not credited. Correct for Tier 1; would understate PnL at higher
  tiers.
- **Test class 19** (backtest leakage) belongs to Phase 4.
