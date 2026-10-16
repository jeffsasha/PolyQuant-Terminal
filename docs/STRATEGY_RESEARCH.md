# Strategy Research and Proposed Defaults

All settings below are proposed research configurations. They do not establish expected profitability. Parameters remain frozen per experiment; any change creates a new version and a new evaluation run.

## Probability target and baseline

Forecast the probability that the contract's rounded final reference statistic meets its rounded official starting threshold. Include the actual tie rule. Do not use a terminal spot-price crossing as the target when the contract settles on an average.

Benchmark 0 uses zero drift and estimated short-horizon volatility, with the settlement averaging explicitly represented. Baseline 1 resamples historical BRTI return paths by volatility regime and time remaining, reconstructs the settlement statistic, and estimates outcome probability. The end-window statistic, observed portion if any, rounding, index/source differences, and jumps are explicit. External spot is an optional versioned feature, not a substitute for missing BRTI. Use only data available at each decision time; insufficient matching data means no forecast eligible to trade.

Before enabling automatic baseline trading, publish the chosen volatility lookback, sampling interval, minimum valid observations, calibration fit, and uncertainty method in an immutable experiment manifest after measuring available history. Collect-only operation is acceptable until this warm-up and offline fit are complete. This is an explicit activation gate, not an assumed ready model.

Momentum and book signals get separate accounts with the same initial equity, risk rules, evaluation windows, and execution assumptions. Report calibration and net performance for each; test combinations only against the frozen individual models. No wallet-copy strategy in the first trading release.

## Entry decision

For a proposed quantity C and $1 payout, expected net value is `C × model_probability − executable_purchase_cost − estimated_fees − additional_execution_allowance`. Price and cost are quantity-aware. When purchase cost already includes spread and book sweeping, do not subtract those costs again. Use a conservative probability bound or a documented uncertainty haircut when deciding to enter.

Compute YES and NO opportunities independently from verified executable sides. Select at most one direction; if uncertainty or a risk gate fails, record `NO TRADE`. No compulsory trade count. Compare buy-and-hold to settlement with early-exit experiments separately.

## Initial operational settings for review

| Setting | Proposed initial value / rule |
|---|---|
| Capital / main and each experiment account | $1,000, isolated |
| Per-entry maximum loss | 0.5% of conservative account equity; purchase amount plus worst-case fees, no rebate credit |
| Total committed exposure | 5% across BTC; initially 2.5% sublimit for each cadence; include pending reservations |
| Position count | Two total, at most one per cadence; pending orders reserve a slot |
| Minimum estimated net edge | $0.03 per $1 contract payout after costs and uncertainty allowance |
| Spread ceiling | $0.05 per contract; malformed or unsupported side mapping rejects |
| No-entry interval | Last 120 seconds of a 15m window; last 300 seconds of a 1h window |
| Opening gate | No entry before window start or before official threshold is published and validated |
| Book receive-age ceiling | 2 seconds; also require a valid current connection and snapshot |
| Official index age ceiling | 3 seconds for reference-dependent strategies; reject gap-filled inputs |
| External spot age ceiling | 3 seconds when used by the active model |
| Clock discrepancy | Halt entries if an available reliable check shows more than 1 second; mark unmeasurable checks explicitly |
| Attempts | One idempotent entry intent per account, strategy version, and market window; no automatic chase of unfilled remainder |
| Consecutive realized losses | Three: 30-minute cooldown; persists across restart |
| Daily loss | 2% of starting-risk-day equity; fees, realized losses, and defensible unrealized losses included |
| Risk day | Proposed 17:00 America/New_York boundary; UTC storage; Chicago display by default |
| Position exit | Official settlement; manual close and early-exit studies use available bid liquidity |
| Re-arming | Explicit resume after reconciled restart; daily halt cannot clear in its triggering risk day |

Tighter gates win. These defaults may produce no trades and must not be loosened merely to improve an in-sample chart. Amendments require an offline, documented experiment version. Fixed risk limits remain owner-controlled.

For equity marks, use defensible executable liquidation values with fees and depth. If a reliable mark is unavailable, block new entries and show valuation unavailable with the last valid timestamp. Do not carry forward a stale mark while presenting it as current. For admission and loss gates, use a conservative lower bound that may value an unpriceable long position at zero; label this as a risk bound, not an executed loss. Starting-day risk equity and halt state are persisted.

## Execution scenarios

| Scenario | Arrival delay | Usable visible depth | Adverse-price allowance | Role |
|---|---|---|---|
| Optimistic | Zero modeled delay | 100% | None | Diagnostic only, still sweeps the actual book |
| Base | Greater of 500ms and measured local processing p95 | 100% | Observed arrival-book movement | Provisional until actual delay evidence exists |
| Conservative | Greater of 1s and twice base delay | 50% | One verified tick adverse | Primary comparison report |
| Stress | Greater of 3s and four times base delay | 25% | Three verified ticks adverse | Liquidity/latency impairment |

Scenario delays are artificial simulation assumptions, not measured live order acknowledgment latency. A stressed price above the limit cancels that quantity. Apply allowances once; use separate attribution for arrival movement and any extra stress penalty. Do not turn a stress assumption into a claim about exchange behavior. Compare scenarios within a strategy; do not add their equities together.

## Fees and accounting

Use versioned official schedules, Decimal arithmetic, execution-time eligibility, and verified rounding. Aggregated L2 levels do not reveal individual counterparty fills: exact per-maker fee rounding may be unknowable. Base reports disclose a documented aggregation assumption; conservative reports use an applicable order-level rounded upper bound rather than claimed exchange-identical fills. If observed fill granularity becomes available, refine the model with evidence. See [Source audit](RESEARCH_AUDIT.md).

Settlement net PnL equals payouts plus sale proceeds minus purchase cost and fees, plus only earned, modeled rebates. Gross trading PnL excludes fees. Spread, sweep slippage, and delay drag are diagnostic decompositions of execution cost already reflected in prices; they are not additional ledger deductions. Reserve collateral until official settlement is confirmed; pay it once. Unknown historical fee schedules make cost-adjusted evaluation for that interval unavailable.

## Validation protocol

Split independent market windows chronologically into development, validation, and an untouched test period; preserve BTC overlap by grouping adjacent windows into time blocks. Purge training records whose outcome horizons overlap evaluation and include an embargo at least as long as the supported maximum horizon where needed. Fit feature transforms and calibration on training data only. Use walk-forward evaluation without retraining on future labels.

Separate the model dataset's source time from the time its value became available. Historical backfills may support retrospective forecasting research, but cannot be presented as having arrived live at their original observation timestamp. Replay actual recorded receive order and modeled arrival; outcomes become available only after resolution.

Report Brier score, log loss, reliability diagrams, calibration sample counts, independent markets, net PnL, ROI, profit factor (or undefined when denominator is zero), expected value, drawdown, losing streaks, holding time, fills, costs, source gaps, and performance by cadence/regime/time. Include a no-trade account and a frozen simple probability benchmark. Use block bootstrap by market/time blocks; report dependence, multiple-experiment selection, and uncertainty.

Proposed screening floor: 30 distinct observation days and 200 distinct resolved market windows per cadence in the untouched evaluation set. Distinct market IDs do not imply statistically independent outcomes; report dependence and effective sample limitations. This is a minimum reporting floor, not proof of adequacy. Further-evaluation eligibility additionally requires positive conservative net EV with a 95% block-bootstrap interval above zero, positive net PnL, calibration no worse than the predeclared benchmark within uncertainty, and results not dominated by one period. Insufficient precision or regimes means collect more evidence. Passing is research eligibility only, never live authorization.
