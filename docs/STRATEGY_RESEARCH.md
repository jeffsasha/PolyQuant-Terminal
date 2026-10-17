# Strategy Research Plan

Nothing here is a claim of edge. Each strategy is a hypothesis with a
pre-registered evaluation protocol. A strategy is labelled
"ready for further evaluation" only if it passes the gates in §6.

## 1. What the contract actually pays on

Up pays $1 if `S̄(T_end) ≥ S̄(T_start)`, where `S̄(t)` is the **trailing 60s
average of BRTI** sampled at `t−1s` (RESEARCH_AUDIT §1.3). Implications:

1. **The terminal value is an average, not a point price.** In the last 60 s of
   a window, part of the close average is already fixed. Variance of the
   remaining outcome shrinks faster than √τ.
2. **Ties go to Up.** Prices are rounded to $0.01, so near-zero distance carries
   a small Up bias. This is measurable from history.
3. **The observable series is smoothed.** Naive realised vol computed from 1s
   differences of `S̄` underestimates spot vol. Over long lags the MA filter
   matters less, so we estimate vol from non-overlapping 60 s differences, or
   de-smooth explicitly, and validate against settlement outcomes.
4. **External spot (Coinbase, Binance) is a feature, not a reference.** It may
   lead `S̄` by up to ~30 s simply because `S̄` lags spot by construction. That
   lag is a legitimate, testable information source. It is the obvious first
   hypothesis for Strategy A/B, and also the one most likely already priced by
   other participants.

## 2. Strategy B — fair probability (baseline first)

Baseline model, which is interpretable:

- Let `d = S̄_now − priceToBeat` and `τ` = seconds to `window_end − 1s`.
- Model the future path of spot as driftless with vol `σ` (EWMA on 60s returns,
  regime-bucketed). Compute the distribution of the terminal 60s average given
  the current partial average. Under Brownian motion, the variance of an
  average of the remaining path has a closed form.
- `P(Up) = Φ(d / σ_eff(τ))`, plus a tie-mass adjustment.
- Fat tails: compare a Student-t variant against the Gaussian on held-out data.
  Keep it only if calibration improves.

Calibration data: needs only the index series plus `priceToBeat` and
`settlementPrice`, all public and historical. **This can be validated before
any order-book data exists.** Metrics: Brier score, log loss, and reliability
diagrams by `τ` bucket and vol regime, against a "market mid" benchmark once we
have recorded BBO.

## 3. Strategy A — momentum

Features: 60 s / 5 min log returns of `S̄` and external spot, acceleration,
realised-vol ratio, distance `d`, and `τ`. Hypothesis: momentum adds
information **beyond** what B already prices. Test it as an incremental feature
in B's model (likelihood-ratio and out-of-sample log loss), not as a
standalone rule.

## 4. Strategy C — order-book signals

Needs recorded BBO (2a) and L2 (2b). Features: top-of-book imbalance, spread
changes, depth depletion, trade intensity. Evaluate at a **delayed** decision
time (signal time + measured latency + 1 poll interval). Measure value net of
taker fees.

## 5. Strategy D — combined; Strategy E — Smart Money

- **D** must beat each component out of sample, after costs, under the
  conservative execution profile.
- **E** is **UNAVAILABLE** for Polymarket US: there is no public trader-level
  data (RESEARCH_AUDIT §4). The module will exist only as a documented stub.

## 6. Evaluation gates (pre-registered)

- Data is split by time into development, validation, and an **untouched
  out-of-sample** period, with walk-forward refits.
- Count **independent markets**, not ticks. Up to four 15m windows overlap
  each 1h window and they are correlated. Report effective sample size.
- Report net PnL after fees, spread and slippage, under the base **and**
  conservative profiles, with bootstrap CIs (block bootstrap by market).
- Minimum before any "ready" label: ≥300 independent traded markets out of
  sample, a positive conservative-profile EV whose 90% CI excludes 0, and
  calibration no worse than market mid.
- No annualised returns from short samples.

## 7. Data dependency timeline

| Strategy | Needs | Available |
|---|---|---|
| B (calibration) | index + reference + settlement | now (public history) |
| B (vs market) | + recorded BBO | after a few days of 2a recording |
| A | + external spot (optional) | now |
| C | + L2 + trades | after 2b and weeks of recording |
| D | all of the above | last |
