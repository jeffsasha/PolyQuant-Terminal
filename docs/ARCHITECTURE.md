# Architecture

Status: Approved architecture. A limited local implementation exists; actual implemented and unverified behavior is recorded in VERIFICATION_REPORT.md.

## Runtime and boundaries

Python 3.12+ with FastAPI owns discovery, asynchronous ingestion, strategy evaluation, risk, paper execution, settlement, ledger, and API streaming. PostgreSQL stores durable state with migrations. Next.js, TypeScript, Tailwind, and an audited charting library provide the terminal. Use built-in asynchronous queues with bounded buffers; no Redis initially. Backend startup refuses multiple trading writers; a database advisory lock protects the writer role.

Separate a read-only US venue adapter from the local PaperExecutionEngine. Narrow protocols exist where the brief requires replaceability: MarketDataProvider, ReferencePriceProvider, Strategy, RiskManager, ExecutionEngine, PortfolioLedger, FeeModel, and SettlementProvider. Keep concrete implementations small; do not create generic plugin loading or extra network services.

The default external spot source is the public Coinbase BTC-USD market feed, subject to official-schema and connectivity verification. Any replacement is explicitly named and versioned. It is never the settlement authority. Data unavailable means unavailable, not a substituted reference.

## Instrument identity and market lifecycle

Discover by typed asset, market family, cadence, exact window, terms, and tradability. Slugs are routing identifiers, not parsed contract definitions. Maintain immutable versions of retrieved terms and rules. Unrecognized rules, missing official threshold, or ambiguous outcome mapping reject trading. Keep active and upcoming windows; refresh definitions and discover the next window automatically.

Distinguish window start, last trading instant, instrument expiration, and final resolution. Scheduled maintenance or missing listings may cause legitimate gaps. The trading gate uses the verified last trading instant, never a later administrative expiration. Official typed fields and per-market rules must agree. [US crypto schema](https://docs.polymarket.us/trader-guide/crypto-schema)

Production and preproduction have distinct environment identifiers, credential configuration, database namespaces, and UI labels. Only verified production inputs qualify for the requested real-market acceptance. Do not silently connect to preproduction when production is empty.

## Data pipeline

Every event stores source, environment, market, source timestamp when supplied, local receive UTC timestamp, monotonic receive order, schema version, connection epoch, and payload hash. Missing source timestamps remain null; do not manufacture latency measurements. Report receive freshness and observable source-to-receive delay separately from unmeasurable exchange execution latency.

Prefer authenticated Markets WebSocket; REST supports discovery and snapshot reconciliation. Establish whether messages are snapshots or deltas from source and observed traffic before applying them. Validate sequences only if the protocol supplies them. When it does not, never claim gap-free continuity; reconcile snapshots and flag uncertainty. [Markets stream](https://docs.polymarket.us/api-reference/websocket/markets), [REST book](https://docs.polymarket.us/api-reference/markets/get-market-book)

Reconnect with bounded exponential backoff and jitter within published rate limits. A disconnect, backlog, schema error, crossed book, invalid quantity, or clock anomaly invalidates the affected state. REST fallback is labeled degraded and cannot meet a stricter freshness requirement merely because a request succeeded.

Persist incoming decision-relevant events before making them eligible for strategies. A recorder failure or full queue halts new entries rather than dropping data invisibly. Retain raw JSON in compressed, rotated segments and an indexed database manifest with hashes, schema versions, and gap intervals. Raw recordings are local and excluded from GitHub.

## Settlement and reference

Store external spot, current official index, official price-to-beat, and official final settlement as different fields. The API's index history includes gap-filled candles; reject missing real observations for computations requiring exact data. The documented averaging interval must be reproduced against real published markets before activation. [Asset price overview](https://docs.polymarket.us/api-reference/asset-prices/overview)

Index reconstruction is a validation tool. Actual paper payouts follow confirmed official market outcomes and verified finality, not an independent forecast. Resolve any ambiguity in the settlement endpoint's units before use; a field called settlement is not automatically an underlying USD price or binary payout. If finality is unavailable or contradictory, keep the position `AWAITING_SETTLEMENT`, retain collateral, and raise an alert. Refunds/voids require verified exchange rules and explicit ledger events. [Settlement endpoint](https://docs.polymarket.us/api-reference/markets/get-market-settlement)

## Orders, money, and risk

Store prices, money, quantities, and fees as Decimal / PostgreSQL NUMERIC; serialize them to the UI as decimal strings. Statistical calculations may use floating point, but monetary estimates cross an explicit Decimal validation boundary. Reject NaN, infinity, invalid ranges, and unsupported ticks or lot sizes.

An account transaction locks its capital and positions, checks risk, creates an idempotent order intent, reserves maximum spend plus fee allowance, and appends an audit event. At simulated arrival, recheck the market, halt state, freshness, risk, limit price, and costs before filling. Fills, fees, reservations, position changes, and balanced ledger postings commit atomically. Failed transactions have no partial financial effect.

Order lifecycle: `INTENT → RESERVED → PENDING_ARRIVAL → FILLED / PARTIALLY_FILLED_AND_CANCELED / CANCELED / REJECTED`. Unknown or interrupted outcomes remain reserved until local journal reconciliation proves what committed. Never create a replacement order through blind retries. Explicit event IDs and database constraints prevent duplicate fills, settlements, and signal orders.

Buy orders consume offers; position-closing sells consume bids. Native YES/NO mapping and any complement transformation require verified US semantics. No uncovered short positions. The default strategy buys one direction per account/market, with one entry attempt per window; a later opposite signal cannot silently hedge or double exposure.

## Realistic paper execution

At modeled arrival time, sweep only visible eligible price levels, up to the limit and reserved capital. Never fill beyond displayed depth. Track shadow consumption within an account and book version so repeated simulated orders cannot reuse identical liquidity. Other experimental accounts are separate counterfactuals, not simultaneous participants in one purported combined portfolio.

Each fill records the triggering book version, price, quantity, latency assumption, liquidity adjustment, and fee uncertainty. Conservative maker simulation defaults to no fill when queue/trade evidence is insufficient. Maker functionality can exist for research without being enabled in the main strategy. Settlement does not need an artificial closing trade.

## Persistence and storage

Core tables: instrument/rule versions; dataset manifests; experiments and frozen configurations; decisions; orders; fills; positions; balanced ledger entries; fee schedules; daily risk snapshots; halt reasons; audit events. Partition historical event indexes as measurements justify it. Database state is authoritative; caches are disposable.

Raw-data budget is 10,000,000,000 bytes across compressed segments, staging files, and their indexes. Warn at 80%; rotate in bounded chunks and reject a write before it exceeds the quota. At the limit pause capture and new entries. No automatic sample deletion. Keep ledger capacity outside that quota; also warn below 5GB filesystem free and halt new entries below 2GB. Those headroom thresholds are proposed operational defaults, not an assurance against disk failure.

At storage halt, continue low-volume official settlement polling, accounting, and health reporting where space permits. If database persistence itself fails, fail closed, report unhealthy, and recover/reconcile later; do not claim settlement committed. A local backup on the same disk protects against some mistakes, not disk loss. Document encrypted off-device backup as a later migration requirement.

## Startup, halt, and recovery

On restart, start paused, acquire the single-writer lock, run migrations, verify account balances from ledger, reconcile orders/reservations, reload halts, and resynchronize inputs. Reevaluate pending paper orders conservatively; an interval lacking recorded books cannot receive invented historical fills. Mark unresolvable attempts canceled with a gap reason once reconciliation establishes that no fill committed.

A manual stop or daily-loss halt cancels pending quantities and preserves holdings. Daily-loss halts cannot be cleared during the same risk day. Proposal: account risk days follow the US schema's 17:00 America/New_York trade-day boundary, stored in UTC with timezone-aware DST handling. This is distinct from the user's Chicago display timezone. Resume after the next risk day still requires an explicit action. Fresh data alone never clears a persistent halt.

## UI and observability

Authenticated same-origin HTTP serves commands; Server-Sent Events deliver state updates, with a current-state refresh after reconnect. UI controls include Paper Start, Pause, Emergency Stop, replay selection, and paper order entry; no live toggle. Show separate account/scenario selectors to prevent combined-return confusion. Include latency, gaps, quota usage, data provenance, and reference reliability beside signals.

Health checks distinguish process alive, database writable, market discovery, feed freshness, recorder health, reference status, and trading readiness. Keep reason-coded logs, metrics, and append-only audit records. Polling/stream limits and circuit breakers are documented per source.
