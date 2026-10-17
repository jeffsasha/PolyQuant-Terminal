# PolyQuant Terminal — Source and Integration Audit

Review date: October 16, 2026 (America/Chicago).

**Later integration update:** [Public production requests](PRODUCTION_API_AVAILABILITY.md) subsequently confirmed typed BTC 15m/1h markets and open books, superseding this initial source-only audit's availability uncertainty. The [reference reconstruction investigation](REFERENCE_DATA_DISCREPANCY.md) failed reconciliation. Authenticated streaming and full trading readiness remain unverified. The bounded source audit below is retained as its original evidence class.

## Evidence boundary

This is a bounded documentation and source review for design approval. No package was installed, no repository code was executed, no API credential was accessed, and no authenticated exchange connection was tested. A local unauthenticated GitHub metadata request failed DNS resolution; browser-source reads succeeded selectively. Source-access failures are missing evidence, not proof that a capability is absent.

The inspected GitHub sources use mutable `main` references. Commit hashes could not be verified in the available responses. Manifest versions below are observed source versions, not verified package releases or reproducible pins. Before implementation reuse, resolve a commit/tag, inspect its complete dependency lock and artifact provenance, retain required license notices, and repeat relevant source checks.

## Design decisions supported by the review

1. Use the official **US** SDK behind a narrow data-only adapter. Both SDK clients also expose live order resources; possession of the SDK alone does not enforce paper-only operation. Inspect the [Python client](https://github.com/Polymarket/polymarket-us-python/blob/main/polymarket_us/client.py) and [TypeScript client](https://github.com/Polymarket/polymarket-us-typescript/blob/main/src/client.ts).
2. Treat the target production BTC cadence as an integration gate. The [Crypto Schema](https://docs.polymarket.us/trader-guide/crypto-schema) distinguishes automated families in preprod from currently hand-listed production BTC markets. Examples do not establish production availability.
3. Record the US order book directly. The [market-data guide](https://docs.polymarket.us/data-guide/market-data) documents current L2 reads and streaming; the [API index](https://docs.polymarket.us/llms.txt) separately lists display-price history. This review did not establish a retail historical L2 replay service.
4. Reject direct reuse of international copy-trading execution. The [Node bot manifest](https://github.com/polymarketwallets/polymarket-copy-trading-bot/blob/main/package.json) uses an international CLOB client and wallet libraries; this is different from the US SDK surface.
5. Reuse established calibration tools selectively. The [scikit-learn calibration implementation](https://github.com/scikit-learn/scikit-learn/blob/main/sklearn/calibration.py) supports probability calibration and explicitly requires disjoint fit/calibration data for prefit models. The project still needs chronological, market-grouped evaluation.

## Official US data and market semantics

### Market identity and production eligibility

The [Crypto Schema](https://docs.polymarket.us/trader-guide/crypto-schema) identifies BTC contracts through typed metadata and Retail `assetPriceTerms`; it warns against parsing symbol or slug formats. It names BRTI as the reference index. `price_to_beat` can initially be absent. Production discovery must therefore save the actual contract terms, rule text, index, outcome mapping, time window, market state, and environment before a strategy can act.

The same source documents 15-minute and hourly Up/Down families, but explicitly separates automated preprod listings from production rollout. The design must not manufacture a 5-minute US listing from international examples or silently change venue/cadence. Missing intended production contracts means `NO_ELIGIBLE_MARKET`, with research and data diagnostics available. [Source](https://docs.polymarket.us/trader-guide/crypto-schema)

### Live books and authentication

The [Markets WebSocket](https://docs.polymarket.us/api-reference/websocket/markets) requires key authentication during handshake and offers market data, lite prices, and trades. Its book-depth section says “top levels”; do not equate that automatically with unlimited depth. Debouncing batches updates, so latency/depth suitability must be measured with the chosen subscription.

The institutional [market-data guide](https://docs.polymarket.us/data-guide/market-data) lists `read:marketdata` and `read:l2marketdata` scopes. These institutional credentials and scopes must not be assumed to be the same as the user's retail API credentials. Prefer the retail surface unless an explicit need and actual entitlement justify institutional integration.

### Reference history versus executable history

The [Asset Prices overview](https://docs.polymarket.us/api-reference/asset-prices/overview) describes unauthenticated reference-index OHLC history, with up to 3,600 candles and request-window clamping. Its stated examples imply one hour at 1-second resolution, 60 hours at 1-minute, and 150 days at 1-hour. These are documented request spans, not verified retention or observed coverage.

The linked [endpoint reference](https://docs.polymarket.us/api-reference/asset-prices/get-a-bucketed-ohlc-price-series-for-one-or-more-assets) and [OpenAPI schema](https://docs.polymarket.us/api-reference/oapi-schemas/asset-prices-schema.json) could not be retrieved in this audit. Their detailed query constraints remain unverified. Use configurable request windows and inspect returned effective bounds.

There is a confirmed averaging-boundary discrepancy in the documentation: the current [Asset Prices overview](https://docs.polymarket.us/api-reference/asset-prices/overview) specifies `[T−60s, T)`, while the September 21 entry in the [changelog](https://docs.polymarket.us/changelog) describes `T−59s` through `T`, inclusive. The overview provides a published price-to-beat reproduction example favoring the former. Verify actual market terms and returned index seconds against published thresholds and final values before activation; do not silently choose the old changelog interpretation.

The [API index](https://docs.polymarket.us/llms.txt) describes market price history as book-derived Yes/No display prices, while reference-index candles describe the BTC settlement benchmark. Neither description supplies historical price-level quantities or an executable arrival-time book. Display-price bars cannot establish fills, partial fills, slippage, or queue position.

Historical L2 availability is **unverified**, not declared unsupported. Check official entitlement, export, and retention options. Until validated, start forward recording; mark price-only studies as probability research and prevent their P&L from being labeled execution-validated. [Official data guide](https://docs.polymarket.us/data-guide/market-data)

Public US trader-level identity/history suitable for wallet rankings was not established in the inspected official API surface. A private account portfolio endpoint is not a public all-trader dataset. Keep Smart Money unavailable/research-only unless a suitable official source is verified; international wallet history cannot represent US trading records. [US API index](https://docs.polymarket.us/llms.txt)

### Fee schedule to version in the simulator

As of this review: standard taker fee is `0.0695 × C × p × (1−p)`; maker coefficient is `−0.0125`. Fees use cent-level half-even rounding. Aggressive multi-fill charges cannot exceed half-even rounding of cumulative exact fees; adjustments only reduce charges. Maker rebates are independent per fill. The extra crypto maker program ended October 15, 8 AM ET. On October 19, **noon Chicago time** (1 PM ET), rebates change, not taker fees. Maker tiers become `0/−0.0035/−0.0070/−0.0104`; taker rebates `0/3/5/10/15/30%`. [Official fee schedule](https://docs.polymarket.us/fees)

Proposal: store fee-policy effective time and source snapshot; assume no rebate for the small paper accounts unless entitlement is explicitly modeled. Test the order-level cumulative cap with split fills, not just a single-price formula. Do not borrow international fees or count a later weekly rebate as immediate cash.

## Repository audit

### Official Python SDK — reuse narrowly

- Repository: [Polymarket/polymarket-us-python](https://github.com/Polymarket/polymarket-us-python).
- Checked source: [manifest](https://github.com/Polymarket/polymarket-us-python/blob/main/pyproject.toml), [license](https://github.com/Polymarket/polymarket-us-python/blob/main/LICENSE), [auth.py](https://github.com/Polymarket/polymarket-us-python/blob/main/polymarket_us/auth.py), [client.py](https://github.com/Polymarket/polymarket-us-python/blob/main/polymarket_us/client.py), [resources/markets.py](https://github.com/Polymarket/polymarket-us-python/blob/main/polymarket_us/resources/markets.py), [websocket/markets.py](https://github.com/Polymarket/polymarket-us-python/blob/main/polymarket_us/websocket/markets.py), and README.
- Observed manifest: version **2.4.1**, Python >=3.10, MIT; runtime dependencies `httpx`, `pynacl`, and `websockets`. [Manifest](https://github.com/Polymarket/polymarket-us-python/blob/main/pyproject.toml)
- Code confirms US gateway/API defaults, authenticated WebSocket creation, market resource reads, and Ed25519 header creation. The client also constructs an order resource and exposes POST/DELETE. [Client](https://github.com/Polymarket/polymarket-us-python/blob/main/polymarket_us/client.py), [authentication source](https://github.com/Polymarket/polymarket-us-python/blob/main/polymarket_us/auth.py)
- Decision: preferred backend data SDK candidate; keep credentials and client private to the collector. Expose immutable normalized data, never the client or order methods, to strategy/paper execution. Enforce outbound method/path allowlisting below the adapter.
- Pending: pin and inspect the async client, base WebSocket reconnect/subscription behavior, complete types, locks and distribution; validate real gateway payloads. This review does not certify SDK security or runtime correctness.

### Official TypeScript SDK — valid alternative, avoid duplicate backend clients

- Repository: [Polymarket/polymarket-us-typescript](https://github.com/Polymarket/polymarket-us-typescript).
- Checked: [package.json](https://github.com/Polymarket/polymarket-us-typescript/blob/main/package.json), [LICENSE](https://github.com/Polymarket/polymarket-us-typescript/blob/main/LICENSE), [auth.ts](https://github.com/Polymarket/polymarket-us-typescript/blob/main/src/auth.ts), [client.ts](https://github.com/Polymarket/polymarket-us-typescript/blob/main/src/client.ts), [resources/markets.ts](https://github.com/Polymarket/polymarket-us-typescript/blob/main/src/resources/markets.ts), [websocket/markets.ts](https://github.com/Polymarket/polymarket-us-typescript/blob/main/src/websocket/markets.ts), and README.
- Observed manifest: **2.1.1**, Node >=18, MIT; `@noble/ed25519` and `ws`. [Manifest](https://github.com/Polymarket/polymarket-us-typescript/blob/main/package.json)
- Source signs timestamp/method/path, separates US gateway from authenticated API, dispatches market frames, and also exposes orders. [Auth](https://github.com/Polymarket/polymarket-us-typescript/blob/main/src/auth.ts), [client](https://github.com/Polymarket/polymarket-us-typescript/blob/main/src/client.ts), [market stream](https://github.com/Polymarket/polymarket-us-typescript/blob/main/src/websocket/markets.ts)
- Decision: reference or alternative if backend implementation becomes TypeScript; do not put exchange secrets in the browser or introduce a second exchange client merely because the UI uses TypeScript.
- Pending: complete lock/distribution audit, version pinning, reconnect tests, payload fixtures, decimal conversion. No claim of feature parity from equal package names.

### PMWallets Node copy bot — reject executor; defer research ideas

- Repository: [polymarketwallets/polymarket-copy-trading-bot](https://github.com/polymarketwallets/polymarket-copy-trading-bot).
- Checked: README, [package.json](https://github.com/polymarketwallets/polymarket-copy-trading-bot/blob/main/package.json), and [LICENSE](https://github.com/polymarketwallets/polymarket-copy-trading-bot/blob/main/LICENSE). Attempts to retrieve execution/config source did not succeed; their internals were not audited.
- Manifest **0.4.1**, Node >=20, MIT; includes `@polymarket/clob-client-v2`, `viem`, PMWallets, proxy/network libraries, and YAML. [Manifest](https://github.com/polymarketwallets/polymarket-copy-trading-bot/blob/main/package.json)
- README describes wallet-fill mirroring, an external PMWallets key, a dry-run/live configuration switch, wallet private keys, funder addresses, and USDC. Those are incompatible with this release's US-only, code-enforced paper execution boundary. [README](https://github.com/polymarketwallets/polymarket-copy-trading-bot)
- Decision: do not install, fork into the runtime, or import executor/MCP trading tools. Later research may adapt idempotent processing and leader-selection ideas after a complete source review; no copyable edge or US support is established here.

### PMWallets Python copy bot — reject runtime; source evidence incomplete

- Repository: [polymarketwallets/polymarket-copy-trading-bot-python](https://github.com/polymarketwallets/polymarket-copy-trading-bot-python).
- Checked: README/repository listing. Manifest, execution/config source, and license-file reads failed. GitHub/README identifies MIT, but license text and dependency graph still require verification. [Repository](https://github.com/polymarketwallets/polymarket-copy-trading-bot-python)
- README describes the same external-wallet mirroring flow and live-mode switch, with private key, funder address, and USDC configuration. It is not evidence of a US SDK adapter. [README](https://github.com/polymarketwallets/polymarket-copy-trading-bot-python)
- Decision: do not install or adopt. Defer copy-trading research. Do not infer its dependency names, implementation safety, or execution accuracy from the Node version.

### Oraclebook — adapt concepts only; defer dependency adoption

- Repository: [jabrahamtech/oraclebook](https://github.com/jabrahamtech/oraclebook).
- Checked: README and [pyproject.toml](https://github.com/jabrahamtech/oraclebook/blob/main/pyproject.toml). Adapter implementation and license-file reads were not available.
- Manifest **0.0.1**, Python >=3.11, MIT declaration; `structlog`, optional `aiohttp`, and optional `py-clob-client-v2` for live execution. [Manifest](https://github.com/jabrahamtech/oraclebook/blob/main/pyproject.toml)
- README labels it pre-alpha, describes single-feed reproducible replay with best-effort cross-topic interleaving, and discloses default builder attribution for live orders. It does not establish a US adapter. [README](https://github.com/jabrahamtech/oraclebook)
- Decision: use its feed/strategy/gate/executor/replay separation as a comparison, not a runtime dependency. PolyQuant requires one persisted total event order, US semantics, no live executor, and no builder attribution. Full implementation/license review remains pending before any copied code.

### Synpath arbitrage example — reject strategy fit; adapt separation idea

- Repository: [Synpath-ai/prediction-market-arbitrage-trading-bot](https://github.com/Synpath-ai/prediction-market-arbitrage-trading-bot).
- Checked: README, [requirements.txt](https://github.com/Synpath-ai/prediction-market-arbitrage-trading-bot/blob/main/requirements.txt), [config.py](https://github.com/Synpath-ai/prediction-market-arbitrage-trading-bot/blob/main/config.py), [src/strategy.py](https://github.com/Synpath-ai/prediction-market-arbitrage-trading-bot/blob/main/src/strategy.py), and [LICENSE](https://github.com/Synpath-ai/prediction-market-arbitrage-trading-bot/blob/main/LICENSE).
- MIT; requirements include `synpath>=0.2.0`, `httpx`, `matplotlib`, `numpy`, and `pytest`. [Requirements](https://github.com/Synpath-ai/prediction-market-arbitrage-trading-bot/blob/main/requirements.txt), [license](https://github.com/Synpath-ai/prediction-market-arbitrage-trading-bot/blob/main/LICENSE)
- Actual strategy source uses a two-venue opportunity list and fixed entry/exit edge; configuration caps quantity at quoted best-level size. This does not implement the proposed US BTC probability strategy or depth-walking arrival simulation. [Strategy](https://github.com/Synpath-ai/prediction-market-arbitrage-trading-bot/blob/main/src/strategy.py), [config](https://github.com/Synpath-ai/prediction-market-arbitrage-trading-bot/blob/main/config.py)
- README distinguishes minute-price backtests from live-book paper signals and advertises broader Synpath US coverage. That advertisement is not a tested US path in this example. [README](https://github.com/Synpath-ai/prediction-market-arbitrage-trading-bot)
- Decision: retain the idea of one strategy shared by replay and paper mode. Reject cross-venue arbitrage scope and published simulated return as acceptance evidence. Underlying SDK, catalog matching, fee handling, fill simulator, locks and retention are unaudited.

## Additional primary repositories considered

### scikit-learn — selective research dependency candidate

Checked [calibration.py](https://github.com/scikit-learn/scikit-learn/blob/main/sklearn/calibration.py), including calibration methods and prefit-data separation. Decision: prefer a version-pinned established implementation for offline calibration if required; start with a small calibrated baseline and chronological train/calibration/test partitions. Default random/stratified CV must not be accepted blindly for overlapping contracts. Complete license, dependency, release and artifact checks remain pending; no install or runtime test occurred.

### NautilusTrader — reference, defer engine adoption

Checked the [official repository/README](https://github.com/nautechsystems/nautilus_trader): it describes a Rust/Python event-driven research/live engine, book-data backtests, and LGPL-3.0 licensing. Decision: reference deterministic clock, event ordering and backtest/live separation; defer adopting an entire multi-venue engine for the bounded local first release. A US adapter and this project's paper-only restrictions were not verified. No claim of unsuitability or insecurity follows from choosing a smaller implementation.

## Integration checks required before paper trading can be accepted

These are proposed checks, not completed results:

- Confirm the user's credentials are **Polymarket US retail** credentials; never paste them into chat, docs, logs, or GitHub.
- Query production read-only market discovery, preserve actual responses, and prove intended BTC family/cadence exists with unambiguous rules. Record preprod separately.
- Verify `assetPriceTerms`, tick/quantity increments, Yes/No book interpretation, missing fields, reference provider and exact tie/settlement rule against each actual market.
- Test unauthenticated reference history with several bounded windows. Compare requested/effective ranges, bucket alignment, gaps, zero-tick candles, age/retention and values near known settlements. Resolve the overview/changelog averaging-boundary discrepancy.
- Confirm full-market-data stream authentication and entitlement, timestamp freshness, book depth, refresh semantics, heartbeats, errors, disconnect/reconnect and subscription restoration. Do not claim sequence guarantees absent measured/documented evidence.
- Determine whether a historical US L2 archive is available under current entitlements; otherwise label the collected replay coverage explicitly.
- Pin SDK/dependencies, inspect locks and artifacts, run relevant vulnerability/license checks, and record commit/tag/hash provenance before installation.
- Demonstrate that attempted exchange mutations fail locally at the transport allowlist and cannot reach the network. The paper executor must have no credentials or exchange client.
- Compare actual observed payloads with SDK types; keep raw fixtures with secrets redacted and decimal strings preserved.
- Reconcile official settlement independently and verify corrected/delayed/void resolution handling before treating a simulation as complete.
- Freeze fee-policy effective timestamps, rounding fixtures, no-rebate default, and unknown terms behavior. Fee-policy uncertainty blocks new entries.
- Measure recorded-data growth and replay speed; cap recording before the agreed storage budget while retaining reserve for ledger and settlement reconciliation.

## Approval implication

This research supports a US-only collector, local recorder, independent strategy accounts, conservative paper executor, and offline evaluation. It does **not** establish a profitable strategy, available production short-horizon BTC listings, authenticated connectivity, complete historical depth coverage, or security clearance for any third-party bot. Those remain explicit gates in the implementation plan.
