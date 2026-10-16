# PolyQuant Terminal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking. Current authorized execution is native in this chat for Task 00, the read-only production verification. Product implementation tasks follow this plan's review.

**Goal:** Build an English, local Polymarket US BTC 15m/1h terminal with real data, automatic paper orders, durable risk/accounting, and credible after-cost research.

**Architecture:** A single Python trading writer owns validated events, decisions, risk, paper execution, settlement, and ledger transactions in PostgreSQL. Next.js consumes the authenticated FastAPI application. Compressed recordings support causal replay using the same strategies and risk/execution code.

**Tech Stack:** Python 3.12+, FastAPI, audited official US Python SDK, PostgreSQL, Next.js, TypeScript, Tailwind, Docker Compose, pytest, Playwright. Dependency versions are pinned from audited release artifacts before installation; never copy mutable-main versions into a lock without checking release provenance.

**Spec:** [Approved design](../../../DESIGN.md), [architecture](../../ARCHITECTURE.md), [strategy settings](../../STRATEGY_RESEARCH.md), [security](../../SECURITY.md), and [acceptance IDs A01–A28](../../ACCEPTANCE.md). Design approved by owner on October 16, 2026.

## Global Constraints

- English interface, documentation, logs, and project communication; Polymarket US only.
- Real market data and paper orders only. LIVE_TRADING_ENABLED=false; setting true refuses startup. No exchange mutations or operational live gateway.
- Initial simulated equity $1,000 per account; isolated probability, momentum, and book experiments; never sum account/scenario returns.
- Maximum loss per entry 0.5% of conservative equity including fees; total committed BTC exposure 5%, each cadence 2.5%; two positions total, one per cadence; reservations count.
- Daily loss limit 2% of starting-risk-day equity; three realized losses cause 30-minute cooldown; no leverage, martingale, or recovery sizing.
- Risk day starts 17:00 America/New_York; UTC persistence; America/Chicago default display. Persist halts; no same-day daily-halt bypass; explicit resume after restart or a later risk day.
- Initial entry defaults: minimum net edge $0.03 per $1 payout, maximum spread $0.05, last-120s/300s exclusion for 15m/1h, book age 2s, required index/spot age 3s, measured clock discrepancy limit 1s.
- One idempotent entry intent per account/strategy-version/market window. Marketable limits sweep arrival-time visible depth, allow partial fills, cancel remainder. Default holding period ends at official final settlement.
- Frozen versioned experiments; no online retuning or automatic recent-winner selection.
- Raw recording budget 10,000,000,000 bytes; warning at 80%; stop capture/new entries before exceeding it; no automatic sample deletion. Ledger headroom remains separate; filesystem warnings below 5GB, entry halt below 2GB.
- Single user, local login, published ports bound to 127.0.0.1, backend-only secrets. No external notifications in this release.
- New private jeffsasha/PolyQuant-Terminal; feature branches and PRs. No existing unrelated repository modifications, main merge, production deployment, or live activation.
- No fixtures presented as live data; no missing tests marked passed. Production/preproduction isolation is mandatory.

## Review Focus

1. A successful HTTP response can still contain HTML, truncated JSON, stale data, or a different environment; tests in Tasks 00/03 reject it as usable production evidence.
2. An active listing can have a future window, missing threshold, preliminary settlement, or a later administrative expiration; Tasks 03/05/09 test those lifecycle distinctions.
3. Two intents can independently pass risk checks and overspend together; Task 06 tests transactional reservations with concurrent requests.
4. A recorder quota halt must not consume the space required to persist settlement; Tasks 04/09/13 test quota headroom and database failures separately.
5. Backfilled historical values and late corrections can leak future knowledge; Tasks 10/11 test availability timestamps, revisions, and unchanged earlier decisions after future-data perturbation.

## File map and execution record

Current review/probe artifacts live in the existing design package; no application repository exists yet. Product paths below are relative to the future local checkout `outputs/PolyQuant-Terminal/`.

| Area | Files and responsibilities |
|---|---|
| Current verification | `tools/verify_production.py`, `tools/test_verify_production.py`, `verification/production/`, `docs/PRODUCTION_API_AVAILABILITY.md` in the design package |
| Core | `services/polyquant/types.py`, `config.py`, `clock.py`, `runtime.py`: shared records, validated settings, deterministic clocks, single-writer orchestration |
| US data | `services/polyquant/venue/us.py`, `venue/transport.py`, `market_data.py`, `reference.py`: read-only venue boundary, discovery, normalized books, index/spot data |
| Persistence | `services/polyquant/store.py`, `ledger.py`, `migrations/`: durable orders, balanced postings, immutable configuration, writer/account locks |
| Trading | `services/polyquant/risk.py`, `fees.py`, `execution.py`, `settlement.py`: independent admission gates, fees, fills, final payouts |
| Research | `services/polyquant/strategies/{probability,momentum,book}.py`, `replay.py`, `research.py`: frozen signals, causal replay, evaluation |
| Capture/API | `services/polyquant/recorder.py`, `api.py`, `auth.py`: event retention, authenticated API/SSE, local sessions |
| Web | `apps/web/app/`, `apps/web/components/`, `apps/web/lib/api.ts`: terminal, authentication, signal/account/scenario views |
| Verification | `tests/unit/`, `tests/integration/`, `tests/e2e/`, `docs/VERIFICATION_REPORT.md` |
| Delivery | `pyproject.toml`, `requirements.lock`, `requirements-dev.lock`, frontend lockfile, Dockerfiles, `docker-compose.yml`, `.env.example`, `.github/workflows/ci.yml`, README and approved docs |

Use a persistent task ledger naming this plan, commits, exact test commands/results, and rulings. Each task below follows red → green for nontrivial product behavior. Commands describe future verification and are not claims of completed runs. Commit product tasks on a feature branch after their checks pass; Task 00 produces local evidence without manufacturing a product commit.

## Task 00 — Production API availability probe (authorized now)

**Files:** Create current-package `tools/verify_production.py`, `tools/test_verify_production.py`, `docs/PRODUCTION_API_AVAILABILITY.md`; save raw response bodies and request metadata under `verification/production/<run-id>/`.

**Interfaces:** `validate_url(url: str) -> str`; `classify_market(market: dict, observed_at: datetime) -> dict`; `scan_listing(fetch_page, max_pages: int) -> dict`; CLI `python tools/verify_production.py --output verification/production` uses GET only, production gateway only, no credentials.

- [x] Write standard-library unit tests: reject non-HTTPS/nonproduction/order/portfolio paths and redirects; reject incomplete or malformed terms; classify 900s and 3600s windows through assetPriceTerms, not slug text; reject wrong asset/family/horizon duration; distinguish current/upcoming/expired; detect duplicate pages and page caps as incomplete, never absence.
- [x] Run `python -m unittest discover -s tools -p 'test_verify_production.py' -v`; observe failures before implementation.
- [x] Implement bounded, sequential public GET requests with timeouts, response-size caps, TLS verification, no redirect following, hashes, UTC receipt times, selected safe response headers, and machine-readable summaries. Scan `closed=false&categories=crypto&includeHidden=true` pages without assuming a sub-limit response is terminal; stop on an empty page, duplicate page, error, or explicit cap. Optionally inspect recent closed markets as separate history evidence.
- [x] Run the unit command again; require all checks pass. Execute the probe. For each typed candidate, request the official detail, BBO, and book paths, then check terms, window, state, reference, and quote freshness. Never construct a current contract slug from a clock or parse it for identification.
- [x] Write a dated capability matrix: reachable vs blocked, complete vs partial listing scan, discovered vs currently open vs sufficiently fresh, each cadence separately. Probe recent official index history independently. Authentication and streaming remain NOT TESTED until credentials are locally configured. If DNS/network access is blocked, attempt the approved read-only network path; do not infer a venue limitation from a local restriction.

**Observed outcome:** Task 00 diagnostic complete. Public production availability verified for both cadences; reference reconstruction failed; REST freshness is intermittent/cached; streaming not tested by owner choice. See [availability report](../../PRODUCTION_API_AVAILABILITY.md) and [execution status](../../EXECUTION_STATUS.md). These findings block trading activation, not the existence of the markets.

**Gate / coverage:** A01/A04 integration begins here. No orders, SDK installation, portfolio calls, or credential transmission. Product availability requires actual qualifying production responses, not public examples alone.

## Task 01 — Audited build and paper-only runtime boundary

**Files:** Create product `pyproject.toml`, dependency locks, `services/polyquant/{__init__,config}.py`, `services/polyquant/venue/transport.py`, `.env.example`, CI base, `tests/unit/test_paper_boundary.py`; copy approved docs. Create private GitHub repository only after plan review and access/name-collision checks.

**Interfaces:** `Settings.from_env(environ: Mapping[str,str]) -> Settings`; `ReadOnlyUSTransport.request(method: str, path: str, params: Mapping | None = None) -> dict`. No live executor implementation.

- [ ] Test `LIVE_TRADING_ENABLED=true` refuses startup; mutation methods, order/portfolio paths, redirect hosts, malformed path encodings, and public frontend secret variables fail before dispatch. Tests assert intercepted network request count remains zero for denied calls.
- [ ] Run `python -m pytest tests/unit/test_paper_boundary.py -q` and observe the missing-boundary failure.
- [ ] Verify release/tag/hash/license and locked transitive dependencies; install only audited pinned artifacts. Implement environment parsing and explicit read-route allowlists. Scope `.env.example` to placeholders and preserve secrets solely in backend configuration.
- [ ] Rerun the test file; require pass. Run secret scanning on repository and build artifacts using a seeded synthetic test token in an isolated test directory, then remove that token fixture from delivery output.
- [ ] Commit `feat: establish audited paper-only runtime boundary`; record commit and test output.

**Coverage:** A20/A22/A27. If GitHub creation is unavailable, keep a local repository with the same feature-branch workflow and record the limitation.

## Task 02 — Shared types, clocks, and immutable experiment settings

**Files:** Create `services/polyquant/{types,clock}.py`, extend `config.py`; tests `tests/unit/test_types_clock.py`.

**Interfaces:** Define frozen `MarketTerms`, `MarketEvent`, `BookSnapshot`, `ReferenceSnapshot`, `ExperimentConfig`, `OrderIntent`, `RiskDecision`, `Fill`, `ExecutionResult`, `AccountState`, and `SettlementResult` records. All monetary/quantity fields use Decimal; all timestamps are aware UTC. `Clock.now() -> datetime`; `Clock.monotonic_ns() -> int`; `risk_day_id(at: datetime) -> str`; `config_hash(config: ExperimentConfig) -> str`. Event identity includes environment, source/receive/availability times, connection epoch, receive sequence, and payload hash. Store complete model and scenario parameters in ExperimentConfig.

- [ ] Tests assert Decimal serialization round-trips, NaN/infinity rejection, deterministic config hashes, UTC enforcement, explicit nullable source times, and correct New York 17:00 boundaries across both DST transitions.
- [ ] Run `python -m pytest tests/unit/test_types_clock.py -q`; observe failure.
- [ ] Implement records and real/replay clocks; enforce the approved settings exactly, including one-entry identity and independent account/scenario names. Freeze configuration after experiment creation.
- [ ] Rerun the test file and verify expected boundary IDs and serialization values.
- [ ] Commit `feat: define validated records and deterministic clocks`.

**Coverage:** A04/A05/A19/A28; prerequisite for every later monetary/data task.

## Task 03 — Production discovery, reference adapters, and reconciled books

**Files:** Create `services/polyquant/{market_data,reference}.py`, `venue/us.py`; tests `tests/unit/test_discovery.py`, `test_market_data.py`, and `tests/integration/test_us_readonly.py`.

**Interfaces:** `USDataAdapter.discover() -> list[MarketTerms]`; `USDataAdapter.stream() -> AsyncIterator[MarketEvent]`; `USDataAdapter.book(market_id: str) -> BookSnapshot`; `ReferenceProvider.latest() -> ReferenceSnapshot`; `MarketState.apply(event: MarketEvent) -> None`; `MarketState.snapshot(market_id: str, at: datetime) -> BookSnapshot`.

- [ ] Tests cover typed BTC 15m/1h discovery, incomplete price-to-beat, mismatched rules, unknown status, future start, last trade vs expiration, duplicate/out-of-order updates, snapshot/delta semantics, reconnect epochs, stale/null timestamps, and a crossed book. Wrong or unavailable environments cannot populate production state.
- [ ] Run `python -m pytest tests/unit/test_discovery.py tests/unit/test_market_data.py -q`; observe failures.
- [ ] Wrap the audited official US SDK behind the read-only transport. Implement bounded retries/rate limits, current/upcoming discovery, explicit validated side mapping, snapshot reconciliation, separately labeled external Coinbase BTC-USD and official BRTI. Do not invent protocol sequence guarantees or exchange latency.
- [ ] Rerun unit checks; configure key locally and run `python -m pytest tests/integration/test_us_readonly.py -m production_readonly -q` only against allowlisted data routes. Preserve redacted real payloads. Reproduce published thresholds for three resolved markets per cadence when available; inaccessible evidence remains blocked.
- [ ] Commit `feat: ingest verified US instruments and market data`.

**Coverage:** A01–A08. No reference-dependent strategy activation until its required inputs pass validation.

## Task 04 — Durable raw capture and quota controls

**Files:** Create `services/polyquant/recorder.py`, dataset-manifest migration in `migrations/`, `tests/unit/test_recorder.py`, `tests/integration/test_capture_recovery.py`.

**Interfaces:** `Recorder.append(event: MarketEvent) -> PersistedEvent`; `Recorder.seal() -> DatasetManifest`; `Recorder.status() -> CaptureStatus`. These records include durable event ID, segment checksum, event order/range, gaps, byte usage, and quota state. Strategies consume only successfully persisted events.

- [ ] Tests assert write-before-publish, crash-safe segment sealing, corrupt hash detection, explicit gap intervals, 80% warning, pre-write 10GB cap using a tiny injected quota, separate ledger headroom, no automatic deletion, and bounded queue overflow producing a halt.
- [ ] Run `python -m pytest tests/unit/test_recorder.py tests/integration/test_capture_recovery.py -q`; observe failures.
- [ ] Implement bounded compressed JSON segments and transaction-safe manifests, accounting for staging/index bytes. Keep records out of Git and reserve database headroom.
- [ ] Rerun checks; capture/close/reopen a short real stream and verify its manifest/checksums and receipt ordering.
- [ ] Commit `feat: record causal market events with safe quotas`.

**Coverage:** A06/A18/A19/A21/A24. Depends on Tasks 02/03 and the minimum manifest persistence from Task 05; implement the manifest schema with Task 05 before running the integration portion.

## Task 05 — Transactional ledger, reservations, and restart state

**Files:** Create `services/polyquant/{store,ledger}.py`, `migrations/001_core.sql`; `tests/integration/test_ledger.py`, `test_writer_recovery.py`.

**Interfaces:** `Store.transaction(account_id: str)` locks the account. `Ledger.reserve(intent: OrderIntent, maximum_cost: Decimal) -> str`; `Ledger.commit_execution(order_id: str, result: ExecutionResult) -> None`; `Ledger.state(account_id: str) -> AccountState`; `Ledger.reconcile() -> ReconciliationReport`. Tables support immutable experiments, manifests, rule versions, decisions, fills, orders, positions, halts, and balanced postings.

- [ ] Tests assert two $1,000 accounts remain isolated; balanced postings/rollback; reservations reduce free capital but do not duplicate holdings; repeated fill IDs do nothing; crashes immediately before/after commit reconstruct identical balances; a second trading writer cannot acquire ownership.
- [ ] Run `python -m pytest tests/integration/test_ledger.py tests/integration/test_writer_recovery.py -q`; observe failures against a disposable database.
- [ ] Implement PostgreSQL migrations, NUMERIC constraints, advisory writer lock, per-account row locks, unique event/order identities, append-only audit roles, and journal-based reconciliation. Never write funds into memory as the sole authority.
- [ ] Rerun checks; restore a backup into a new disposable database and compare cash, reservations, positions, configs, and halts.
- [ ] Commit `feat: persist balanced paper accounts and recovery state`.

**Coverage:** A14/A15/A18/A22/A26/A28. **Execution order ruling:** run Task 05 before Task 04's database-dependent steps; task numbers identify features, not a contradictory dependency order. The execution order below is authoritative.

## Task 06 — Independent central risk engine

**Files:** Create `services/polyquant/risk.py`, `tests/unit/test_risk.py`, `tests/integration/test_risk_concurrency.py`.

**Interfaces:** `RiskManager.evaluate(intent: OrderIntent, account: AccountState, market: MarketTerms, book: BookSnapshot, reference: ReferenceSnapshot, config: ExperimentConfig, at: datetime) -> RiskDecision`; `RiskManager.halt(account_id: str, reason: str, at: datetime) -> None`. Ledger reserves within the same account transaction after evaluation.

- [ ] Tests assert a $1,000 account admits at most $5 maximum entry loss including fee allowance, rejects $5.01, includes pending reservations and slots, enforces 2.5%/5% cadence/combined exposure, and rejects all stale/closed/near-expiry/invalid inputs. Daily $20 loss locks persist; three losses start a 30-minute cooldown.
- [ ] Run `python -m pytest tests/unit/test_risk.py tests/integration/test_risk_concurrency.py -q`; observe failures.
- [ ] Implement exact-money gates, conservative equity bounds, idempotency, persistent halts, start-of-risk-day snapshots, and shared manual/automatic order admission. Concurrent requests must serialize with reservation; no check-then-write race.
- [ ] Rerun checks; include unavailable valuations, next-day boundary, restart, manual resume, and two simultaneous intents competing for the last available capital/slot.
- [ ] Commit `feat: enforce persistent independent paper risk limits`.

**Coverage:** A05/A06/A14–A18/A21/A28.

## Task 07 — Versioned fee calculations

**Files:** Create `services/polyquant/fees.py`, fee-policy migration/data, `tests/unit/test_fees.py`.

**Interfaces:** `FeeModel.quote(fills: list[Fill], executed_at: datetime, policy_id: str, granularity: str) -> FeeQuote`. FeeQuote records exact/rounded charges, eligible rebates, policy source/effective time, aggregation assumption, and conservative bound.

- [ ] Tests assert standard taker C=100,p=0.50 yields $1.74; half-even 0.025→0.02 and 0.035→0.04; cumulative multi-fill cap never exceeded; canceled quantity has no fee; unknown policy refuses cost-valid execution; October 19, 2026 17:00 UTC switches rebates without changing standard taker coefficient.
- [ ] Run `python -m pytest tests/unit/test_fees.py -q`; observe failure.
- [ ] Implement Decimal arithmetic, exact effective timestamps and official rounding/eligibility. Treat L2 counterparty granularity as uncertain; record base aggregation and conservative cap without claiming exchange-identical maker fills. Historical unknown rules remain unavailable.
- [ ] Rerun tests against independent official vectors and split-fill constructions with no guaranteed rebate assumption.
- [ ] Commit `feat: model effective US fees and rounding uncertainty`.

**Coverage:** A12/A14/A28. Depends on Task 02; implement before Task 06 fee-budget integration.

## Task 08 — Arrival-time paper execution

**Files:** Create `services/polyquant/execution.py`, `tests/unit/test_execution.py`, `tests/integration/test_order_lifecycle.py`.

**Interfaces:** `PaperExecutionEngine.submit(intent: OrderIntent) -> str`; `PaperExecutionEngine.process_due(at: datetime) -> list[ExecutionResult]`; `PaperExecutionEngine.cancel_remaining(order_id: str) -> None`. Only normalized persisted books, risk, fees, clock, and ledger are injected; no venue credentials/client.

- [ ] Tests assert buying four contracts against asks 2@0.50 and 3@0.55 fills four at VWAP 0.525; selling uses bids; limit 0.52 fills two only; future arrival uses the future available book rather than the signal book; insufficient visible depth cannot fill. Test adverse tick/limit cancellation, pending halt, duplicate processing, shadow depth reuse, and fee-adjusted capital bounds.
- [ ] Run `python -m pytest tests/unit/test_execution.py tests/integration/test_order_lifecycle.py -q`; observe failures.
- [ ] Implement order state machine, delay/depth/penalty scenarios from approved spec, arrival-time revalidation, atomic fills/reservations/ledger commits, and canceled remainder. Passive maker research defaults to no fill without required evidence; no uncovered shorts.
- [ ] Rerun checks; inject crash around every transactional state boundary and reconcile without blind retry or imagined gap-period fills.
- [ ] Commit `feat: simulate conservative arrival-time paper fills`.

**Coverage:** A09–A12/A14–A18/A20/A28.

## Task 09 — Official final settlement and halt lifecycle

**Files:** Create `services/polyquant/settlement.py`, extend runtime/store migrations; `tests/unit/test_settlement.py`, `tests/integration/test_halt_settlement.py`.

**Interfaces:** `SettlementProvider.fetch(market_id: str) -> SettlementResult`; `SettlementService.apply(result: SettlementResult) -> None`; `Runtime.resume(account_id: str) -> RiskDecision`. SettlementResult carries official outcome, final/preliminary status, provenance, observation time, payout/refund rules, and revision ID.

- [ ] Tests assert exactly-once official payouts, delayed/preliminary outcomes retaining collateral, tie mapping, corrected/void outcomes using compensating entries, cancellation racing a fill, and recorder halted while final settlement still persists.
- [ ] Run `python -m pytest tests/unit/test_settlement.py tests/integration/test_halt_settlement.py -q`; observe failures.
- [ ] Implement authoritative finality checks using verified field meanings; never infer payout from BTC spot or a vaguely named settlement number. Persist manual/daily/storage stops and require explicit resume after reconciliation; same-risk-day daily halt remains locked.
- [ ] Rerun checks; observe at least one actual resolved market per supported cadence when available and trace its reference/outcome/paper holding independently. Simulate total database failure and show unhealthy state, not invented committed settlement.
- [ ] Commit `feat: settle paper holdings from official final outcomes`.

**Coverage:** A03–A05/A13/A17/A18/A21/A25.

## Task 10 — Frozen probability baseline

**Files:** Create `services/polyquant/strategies/probability.py`, offline fit command in `research.py`, `tests/unit/test_probability.py`.

**Interfaces:** `Strategy.evaluate(events: Sequence[MarketEvent], market: MarketTerms, account: AccountState, config: ExperimentConfig, at: datetime) -> SignalDecision`; SignalDecision contains probability/bounds, net-edge estimate, direction or NO_TRADE, feature provenance, config ID, and reasons. `fit_probability(dataset: DatasetManifest, config: ExperimentConfig) -> ModelArtifact`.

- [ ] Tests distinguish average-based settlement from a last-tick crossing, account for rounding/ties, reject missing threshold/gap-filled seconds, prevent future events and future-fitted calibration, and give reproducible probability bounds for a fixed seed. Minimum net edge is 0.03 after actual execution costs; spread/slippage cannot be deducted twice.
- [ ] Run `python -m pytest tests/unit/test_probability.py -q`; observe failures.
- [ ] Implement zero-drift benchmark and historical path-resampling baseline. Select and publish exact lookback/sampling/minimum-data/calibration/uncertainty settings offline from observed coverage, then freeze them before activation. No eligible warm-up/model means collect-only, not a fabricated signal.
- [ ] Rerun tests; save immutable model artifact/config/dataset hashes. Future data perturbation must leave earlier signals identical.
- [ ] Commit `feat: estimate contract settlement probability with causal inputs`.

**Coverage:** A03/A06/A19/A28; activation requires all data, risk, fee, and execution prerequisites.

## Task 11 — Causal replay and research reporting

**Files:** Create `services/polyquant/replay.py`, extend `research.py`, `tests/unit/test_replay.py`, `test_research_splits.py`, report export templates.

**Interfaces:** `Replay.run(dataset: DatasetManifest, config: ExperimentConfig) -> RunReport`; `evaluate_run(run: RunReport, splits: SplitManifest) -> ResearchReport`. Reports include ID/hashes, causal timing, independent market IDs, accounts/scenarios, quality exclusions, calibration, gross/fees/net PnL, cost attribution, and uncertainty.

- [ ] Tests assert identical replays yield identical decisions/ledger results; late historical backfills do not appear early; overlapping 1h/15m labels are purged/embargoed; transformations fit only on train; settlement labels arrive only when observed; zero-trade and undefined metric cases remain explicit.
- [ ] Run `python -m pytest tests/unit/test_replay.py tests/unit/test_research_splits.py -q`; observe failures.
- [ ] Implement chronological development/validation/test and walk-forward manifests, at least maximum-horizon embargo when needed, block bootstrap, Brier/log-loss/reliability, all approved performance/regime metrics, and separate execution scenarios. Market IDs are distinct samples, not proof of statistical independence.
- [ ] Rerun tests; replay one actual recorded window and show source hashes and fill/rejection provenance. A positive research label additionally requires the approved 30-day/200-window floor and conservative uncertainty gates; otherwise label insufficient evidence/no edge.
- [ ] Commit `feat: replay recorded markets and report honest strategy evidence`.

**Coverage:** A19/A24/A28 and all research acceptance.

## Task 12 — Independent momentum and order-book comparisons

**Files:** Create `services/polyquant/strategies/{momentum,book}.py`, tests `tests/unit/test_strategy_accounts.py`, `test_signal_models.py`.

**Interfaces:** Both implement Task 10's Strategy.evaluate and produce the same SignalDecision; reuse Task 11's evaluator. Each gets a separately fitted/frozen model and isolated $1,000 account under identical risk/scenario rules.

- [ ] Tests assert same evaluation windows/configured cost rules across strategies, account isolation, no added returns, and no copying a leader or automatically selecting the latest winning strategy. Feature availability and insufficient independent training data produce NO_TRADE.
- [ ] Run `python -m pytest tests/unit/test_strategy_accounts.py tests/unit/test_signal_models.py -q`; observe failures.
- [ ] Implement log-return/volatility momentum features and validated imbalance/microprice/trade-intensity features where available; fit interpretable offline probability models. Missing volume/trade data disables dependent features rather than inventing zero observations. Combined strategy stays research-only until individual evidence permits a new version.
- [ ] Rerun checks and compare frozen models on the same untouched time blocks and scenarios; no positive-performance assertion without adequate evidence.
- [ ] Commit `feat: compare isolated momentum and book strategies`.

**Coverage:** A06/A19/A28.

## Task 13 — Local authenticated API, SSE, and process orchestration

**Files:** Create `services/polyquant/{api,auth,runtime}.py`, `tests/integration/test_api_auth.py`, `test_runtime.py`.

**Interfaces:** HTTP `GET /state`, `GET /events`, `GET /decisions/{id}`, `POST /paper/start`, `/paper/pause`, `/paper/stop`, `/paper/orders`, `/paper/resume`; no live mode or venue order routes. Commands call the same risk/ledger/execution functions. SSE emits versioned state events with a reconnect cursor; snapshots restore current truth.

- [ ] Tests assert login/session expiry, CSRF/Origin/Host checks, localhost binding, password hashing, login rate limits, malformed monetary values and mode injection, same risk checks for manual tickets, source labels, and SSE reconnect snapshot consistency.
- [ ] Run `python -m pytest tests/integration/test_api_auth.py tests/integration/test_runtime.py -q`; observe failures.
- [ ] Implement single-writer startup/reconciliation, paused default, health/readiness separation, authenticated commands and SSE, quota/circuit-breaker handling, and scrubbed structured audit logs. Secret-bearing settings are not dashboard editable.
- [ ] Rerun checks; exercise startup with missing feeds, database write failure, corrupt recording, and persistent halt. No healthy/ready flag is inferred solely from process liveness.
- [ ] Commit `feat: expose authenticated local paper controls and state`.

**Coverage:** A06/A15/A17/A18/A20–A23.

## Task 14 — English trading terminal

**Files:** Create `apps/web/app/{layout,page,login/page,smart-money/page}.tsx`, `apps/web/components/{Header,PriceChart,MarketPanels,OrderBook,PaperTicket,Positions,Performance,DecisionDetails,DataHealth}.tsx`, `apps/web/lib/api.ts`, frontend lock/config; `tests/e2e/terminal.spec.ts`.

**Interfaces:** Typed API clients consume decimal strings, source/environment/status labels, accounts/scenarios, SignalDecision, RunReport, and SSE versions from Task 13. UI keeps those labels visible and never computes authoritative balances.

- [ ] Playwright tests cover login → real/replay state → start → inspect signal or rejection → order/fill/position → emergency stop → restart preserved halt. Assert English text, PAPER banner, absent live toggle, theme switching, keyboard access, account/scenario isolation, unavailable references, and no fixtures labeled live.
- [ ] Run `pnpm exec playwright test tests/e2e/terminal.spec.ts`; observe failure before implementation.
- [ ] Build the approved chart/market/book/order/performance layout with 1m/5m/15m/1h candles, supported volume/VWAP, reference lines, countdowns, markers and decision details. Smart Money explains verified availability and remains disabled when unsupported; never fabricate leader rankings.
- [ ] Rerun E2E with the actual backend and a separate explicitly labeled fixture environment; run `pnpm build`, TypeScript checks, and accessibility checks on critical controls.
- [ ] Commit `feat: deliver the English paper trading terminal`.

**Coverage:** A20/A22/A23/A28. Chart dependency/license and displayed data semantics are audited before adoption.

## Task 15 — Compose, CI, failure drills, and reviewable release

**Files:** Create backend/web Dockerfiles, `docker-compose.yml`, health/start/backup/restore commands, `.github/workflows/ci.yml`, README, `tests/integration/test_backup_restore.py`, `docs/VERIFICATION_REPORT.md` and `docs/LIVE_READINESS.md`.

**Interfaces:** Compose services backend/db/web; only localhost published ports; PostgreSQL volume persists. Backup/restore commands operate on specified databases and never overwrite the only live copy. CI uses isolated databases and fixture-only tests; credentialed production checks are opt-in, read-only, and not run for untrusted PRs.

- [ ] Tests assert migration-from-empty, restart recovery, clean backup restore, paper-only environment enforcement, local port bindings, and mandatory CI secret/dependency scans. Use failure fixtures for storage headroom/database outage/reconnect loops.
- [ ] Run `python -m pytest tests/integration/test_backup_restore.py -q` and targeted container checks; observe failures before completing scripts/configuration.
- [ ] Implement Compose and English instructions, native development alternative, CI suites and explicit production-check controls, local backup commands, and separate future live-readiness requirements.
- [ ] Run unit/integration/E2E/build checks, `docker compose build`, `docker compose up -d --wait`, restart/restore drills, a 10-minute 10× observed-peak replay load, and a disclosed 24-hour real observation when feasible. Store actual commands/outputs and A01–A28 statuses. Docker not available, missing products, or insufficient research history stay BLOCKED/INSUFFICIENT, never passed.
- [ ] Commit verified work; obtain a fresh whole-branch correctness/security review, fix important findings with failing regression tests, rerun affected checks, open and attach a private reviewable PR. No automatic merge, deploy, or live activation.

**Coverage:** A01–A28 final evidence, particularly A18/A20–A27. Product engineering completion requires all mandatory gates; research profitability remains a separate finding.

## Dependency order and stage gates

Execute: **00 → plan review → 01 → 02 → 03 → 05 → 04 → 07 → 06 → 08 → 09 → 10 → 11 → 12 → 13 → 14 → 15**. The order puts shared persistence before recorder manifests and fees before risk-budget integration. No stage depends on unimplemented types or a recorder-owned ledger.

After Task 00, report the actual production capability matrix and any access restriction. A supported public listing does not prove authenticated streaming, and a closed historical contract does not prove a currently open market. Continue only within the corresponding verified capabilities; a product scope change needs the owner's decision.

## Plan self-review

- Spec coverage: approved scope maps to Tasks 00–15; A01–A28 ownership is listed at each task. Live trading and wallet-copy execution are explicitly excluded, not forgotten implementations.
- Step scan: each product task specifies file paths, interfaces, red/green commands, exact assertions or observable evidence, and a commit boundary. Current public probe uses stdlib tests and no package installation.
- Type consistency: shared records belong to Task 02; PersistedEvent/DatasetManifest/CaptureStatus to Task 04; reconciliation records to Task 05; FeeQuote to Task 07; SignalDecision/ModelArtifact to Task 10; report/split records to Task 11. Store schemas support records before consumers use them.
- Dependency check: Task 05 precedes Task 04, Task 07 precedes Task 06, and all financial modules precede automation/UI. These ordering rulings are explicit above.
- Review focus: each of the five failure classes has a named test task, including truncated responses, lifecycle timing, concurrent reservation, disk exhaustion, and late data.
- Proportion: implementer writes bodies; examples pin financial outcomes rather than transcribe the implementation. Product dependencies remain auditable candidates until pinned in Task 01.

## Current authorization and handoff

The owner requested this detailed plan and explicitly authorized starting production API availability verification. Execute Task 00 now. Product implementation Tasks 01–15 have not started. Recommend native execution with a final fresh review for the later product work; the shared ledger and staged checks preserve progress. Request plan review with the Task 00 evidence so any venue limitation is visible before application implementation.
