# Acceptance and Evidence Matrix

Status: Criteria retained from the approved design. Actual implementation evidence and incomplete gates are tracked in [VERIFICATION_REPORT.md](VERIFICATION_REPORT.md). This file is not a claim that all checks passed.

## Evidence categories

- **D — Deterministic:** controlled fixtures and fault injection; proves specified behavior, not actual venue availability.
- **I — Integration:** observed official production requests/streams using locally configured credentials where needed.
- **O — Observation:** real recorded windows and operational sessions; report date range, uptime, environment, and gaps.
- **R — Research:** chronological sample separation, calibration, uncertainty, and after-cost analysis.

Every check records PASS, FAIL, BLOCKED, or NOT RUN, command/procedure, code and dependency versions, output/artifact location, and evidence type. BLOCKED and NOT RUN are never green passes. A source document is documentation evidence, not an integration result.

## Required checks

| ID | Type | Check and pass condition |
|---|---|---|
| A01 | D/I | Discovery identifies BTC/UP-DOWN/15m/1h through verified typed terms; unknown, incomplete, and unsupported instruments cannot trade. Production availability is demonstrated separately for each cadence. |
| A02 | D/O | Both cadences roll into new instruments without hardcoded individual slugs. Observe at least two consecutive boundaries per cadence; expired instrument orders are rejected. |
| A03 | D/I | Reference reconstruction matches at least three published resolved markets per cadence to the specified precision, including exact endpoint boundaries; missing or gap-filled seconds reject required calculations. |
| A04 | D/I | YES/NO and UP/DOWN mapping, tie behavior, price transformations, tick/lot limits, and payout units agree with verified market rules and captured payloads. |
| A05 | D | UTC, Chicago display, New York risk-day boundary, DST spring/fall transitions, and distinct last-trade/expiration times produce correct gates. |
| A06 | D/O | Stale book, stale reference, missing source timestamps, delayed spot, clock discrepancy, and backlog produce the documented flags and no forbidden new entries. |
| A07 | D/I | Disconnect/reconnect, snapshot resync, duplicate/out-of-order messages, and real stream semantics are handled; no unsupported continuity guarantee is claimed. |
| A08 | D | Book levels sort correctly; malformed/crossed/negative data invalidate the book; delta logic is tested only if actually supported by the protocol. |
| A09 | D | Size-aware ASK buys and BID sells match exact expected weighted prices; no last-trade or midpoint fill; no fill beyond visible eligible depth. |
| A10 | D | Delayed arrival, depth changes, partial fills, canceled remainder, limit violations, capital caps, and shadow liquidity consumption match expected outcomes. |
| A11 | D | A maker order touching a quote does not guarantee a fill; missing queue evidence results in the documented conservative behavior. |
| A12 | D | Official fee vectors, half-even ties, cumulative caps, fill-granularity uncertainty, and effective-time rebate changes are checked; historical unknown schedules block credible net reporting. |
| A13 | D/I/O | Official final outcome credits exactly one payout per holding; duplicated settlement messages do not double credit; preliminary/ambiguous settlement retains collateral; verified void/refund rules are handled. |
| A14 | D | Insufficient funds, per-trade maximum loss including fees, pending reservations, tick/lot rounding, and zero/invalid quantities reject atomically. |
| A15 | D | Repeated signal, request, retry, reconnect, and crash replay produce no duplicate orders, fills, or ledger postings. |
| A16 | D | Per-cadence and combined exposure, position slots, correlated BTC limits, and manual tickets enforce the same risk rules independently for each account. |
| A17 | D | Daily 2% loss gate, persistent manual stop, three-loss cooldown, and risk-day rollover behave as specified; restarting cannot clear a halt or bypass same-day loss lock. |
| A18 | D | Crash before/after reservation and fill commit recovers correct cash, positions, pending orders, and halts. Database restore reproduces those states. |
| A19 | D/R | Perturb future prices/outcomes and show earlier features/orders unchanged. Split/embargo rules prevent overlapping label leakage; replay respects original availability order. |
| A20 | D | All UI/backend order paths remain paper-only. Set live flags and attempt mutation routes: startup/request denied and no real order request reaches the network. |
| A21 | D/O | 80% quota warning, pre-limit write rejection, 10GB capture stop, persistent storage halt, filesystem headroom checks, no sample deletion, and continued ledger/settlement work with reserved space are verified. |
| A22 | D | Missing/incorrect login, expired session, CSRF, invalid Origin/Host, and unauthorized state-changing calls fail; ports bind locally; no secret appears in UI assets, logs, recordings, or committed files. |
| A23 | D/O | UI flow: login → inspect real/replay source → Paper Start → inspect decision/rejection → inspect fill/position → stop → restart → inspect preserved state. English labels, theme switching, keyboard basics, and unavailable views work. |
| A24 | D/O | Recorded replay at observed peak and 10× rate for ten minutes gives identical accounting or a visible safe halt; queue overflow never silently drops strategy-critical events. |
| A25 | I/O | 24-hour production data observation records uptime/gaps, cadence coverage, reconnects, index freshness, and final settlements. Sleep/connection gaps are disclosed and cannot be counted as continuous uptime. |
| A26 | D/I | Compose build/start/health/stop/restart works on an actual Docker engine; native checks alone cannot satisfy this item. Fresh-database migrations and backup restore pass. |
| A27 | D/I | CI runs required suites, dependency and secret scans; repository is private under the approved owner; PR contains evidence and known gaps. Merge/deploy remain unperformed without approval. |
| A28 | R | Independent accounts/scenarios never share balances or combine returns; all requested metrics handle zero-trade/zero-denominator cases; fills, fees, costs, latency assumptions, and data exclusions are visible. |

## Important financial examples

Fixtures will include multi-level purchases and sales, insufficient depth, movement between signal and arrival, adverse price crossing the limit, split fee rounding, partial cancellation, identical duplicate event IDs, fees exhausting the remaining risk budget, a settlement delay, and crash/retry around a committed transaction. Expected balances and ledger postings are calculated independently with exact decimals. They are labeled test fixtures and never displayed as live history.

Payout and sale cashflows reconcile to positions and ledger balances. Expected risk checks use maximum loss and conservative valuations rather than an assumed stop fill. Reports attribute spread/slippage without deducting the same costs twice. An unavailable mark is distinct from a zero-value risk bound and from a realized loss.

## Engineering release decision

All deterministic safety/accounting checks and required UI checks must pass. Integration and observation gates for real production US 15m/1h support must pass to describe the full requested real-data terminal as working. A build with blocked venue capabilities may be delivered as a clearly limited recorder/replay system, but cannot be declared the full requested release without an owner-approved scope change.

Keep a `VERIFICATION_REPORT.md` with the check matrix, exact commands, actual outputs, screenshots, captured production evidence without secrets, dataset/config hashes, and unresolved limitations. This report will be produced after implementation, not prepopulated with imagined successes.

## Strategy evaluation decision

Before labeling a strategy ready for further evaluation, apply the predeclared screening floor and uncertainty gates in [Strategy research](STRATEGY_RESEARCH.md). Show optimistic, base, conservative, and stress results, not only the best case. Insufficient observations, unstable calibration, negative conservative net performance, or dependence on unsupported reference/fee assumptions produce `INSUFFICIENT EVIDENCE` or `NO DEMONSTRATED EDGE`.

Even a positive research result does not pass any future live-trading activation gate. Software acceptance and financial evidence are separate decisions.
