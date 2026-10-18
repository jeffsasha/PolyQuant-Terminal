# Test Report — Phase 4 (strategy framework, fair-probability baseline, calibration, replay)

Date: 2026-10-17. All numbers below come from actual runs. Full outputs: `reports/phase4/calibration.md|json` and
`reports/phase4/backtest.md|json`.

## Automated tests

`pytest -q`: **187 passed, 0 skipped**. `ruff`: clean. `pip-audit`: no known vulnerabilities (numpy 2.5,
scipy 1.18 added).

| Area | What is verified |
|---|---|
| Model maths | MA-change variance and MA-lag drift: exact discrete formulas, checked by Monte Carlo (variance within 6 %, drift exact). σ estimator recovers spot vol from the smoothed series (within 5 %), while naive 1 s diffs underestimate it by more than 70 %. |
| **Leakage (test class 19)** | `PointInTimeSeries` raises on any access past now − 1 s. `PITInstrument` has no settlement fields, and `priceToBeat` is hidden for the first 5 s. Future-perturbation test: decisions are identical when all data after the cutoff is replaced by noise. Chronological split is ordered, disjoint and embargoed. Walk-forward trains strictly on markets that ended before each fold (every call checked). |
| Calibration metrics | Brier, log loss, reliability and ECE against known values. Market-block bootstrap is seeded and resamples whole markets. |
| Strategy | Buys the underpriced side within budget (sizing includes expected slippage). No trade when price reflects probability, near settlement, or when already positioned. |
| Replay | Fill uses the **arrival** book (decision + latency), not the decision book. Settlement, slippage attribution, drawdown, streak and profit factor checked. |

Two test-design errors (saturated probabilities, hour-aligned cuts) and one real defect were found and fixed. The
defect was continuous-time formulas where the index uses a discrete 60-sample average (~1.7 % drift error).

## Data

- **Backfill:** 2,966 BTC up/down instruments (2,369 15m and 597 1h, from Sep 22), 2,950 settled; 2,241,951 official
  1 s index points (every second from Sep 21 18:00 UTC, **0 gaps**).
- **Reference rule at scale:** `priceToBeat = index(T−1s)` failed for most launch-week markets (Sep 22–24, up to
  $2.67 off) and for 1 market on Sep 28; it held for every other market. The venue outcome agreed with
  `settlementPrice ≥ priceToBeat` in 2,944/2,944 markets. Labels always use official values.

## Calibration (public history; protocol in STRATEGY_RESEARCH §6)

2,944 labelled markets. Chronological split: dev 1,756, val 591, test 593, embargoed 4. Twelve variants
(lookback × Gaussian/t4 × drift). Selection used dev only.

| | Result |
|---|---|
| Selected | `L7200_k120_t4_drift1` (2 h vol lookback, Student-t, MA-lag drift) |
| **Test (once)** | log loss **0.316** vs coin-flip 0.693 (improvement 0.377, 90 % CI 0.347–0.402); Brier **0.100**; ECE **0.019**; 2,965 predictions, 593 markets |
| Walk-forward (3 weekly folds) | Same variant re-selected each fold; log loss 0.329 / 0.306 / 0.332 |
| Consistent findings | Every drift variant beats every driftless one (dev and val). Calibration is weakest for early 1h checkpoints (ECE ≈ 0.11 at 50 and 30 min left; n = 119). |
| **Model vs market mid** | On the only 21 decision points with recorded books (6 markets): market log loss **0.456**, model **0.666**. |

**Reading:** the model predicts the official rule well and is well calibrated out of sample. But where we can
compare, the market's own price was the better forecaster. The sample is far too small to conclude, but the
direction is against the model having an edge.

## Execution replay (recorded WS books only)

11 resolved markets with recorded books. Strategy: min edge 0.02 after conservative costs, IOC, held to settlement.

| profile | trades | net | fees | EV/trade (90 % CI) |
|---|---|---|---|---|
| optimistic (diagnostic) | 7 | −1.59 | 0.97 | −0.23 (−3.15 … 2.70) |
| base | 7 | −1.37 | 0.96 | −0.20 (−3.15 … 2.76) |
| conservative | 6 | +2.14 | 0.88 | +0.36 (−2.81 … 3.78) |
| stress | 3 | +8.07 | 0.43 | +2.69 (−1.45 … 6.83) |

**This is noise.** Every CI spans zero widely, and the profile ordering is inverted: the harsher profiles skipped
trades that happened to lose. It is a pipeline check only. The ≥ 300-market gate is not met (11 markets).

## Verdict for this phase

- **Strategy B is NOT ready for further evaluation.** It is calibrated, but it has not been shown to beat
  executable prices after costs. The small available comparison points the other way.
- **What would change that:** weeks more recorded books (the recorder must keep running), then the same
  pre-registered comparison against market mid and replay PnL under conservative costs.

## Open items

- **More recorded books:** the replay and the market comparison are sample-limited until more books exist.
- **Strategy A** (external spot as a leading feature) and **Strategy C** (order-book signals) are not built.
  The market-vs-model gap suggests external spot is the first hypothesis to test.
- **Maker entries** are not replayed.
- **Early-1h miscalibration** should be investigated, e.g. vol-of-vol or regime-dependent tails.
