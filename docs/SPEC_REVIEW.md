# PolyQuant Terminal — Spec Review (Phase 0)

Date: 2026-10-17 (UTC). Status: **approved 2026-10-17** (monolith, read-only API key, local-first). Addenda below are marked *Update*.

Everything marked **[verified]** was checked against official docs or a live
public API call on 2026-10-17 around 05:30 UTC. **[unverified]** means the docs
are silent or contradictory, so it must be tested with credentials before we
rely on it.

---

## 1. Verified facts that change the design

| # | Finding | Evidence | Impact |
|---|---|---|---|
| F1 | Two base URLs: `https://gateway.polymarket.us` (public, no auth) and `https://api.polymarket.us` (Ed25519-signed). | SDK `client.py` (`GATEWAY_BASE_URL`), 401 on `api.` without headers **[verified]** | The public data adapter and the authenticated adapter are separate classes. |
| F2 | BTC up/down markets are discoverable by metadata: `assetPriceTerms.marketType=ASSET_PRICE_MARKET_TYPE_UP_DOWN`, `horizon` (`15m`, `1h`), `indexSymbol=BRTI`, `windowStart`, `windowEnd`, `priceToBeat`, `settlementPrice`. Slugs look like `cpc-btc-updown-15m-2026-10-17-0530z`. The docs say to identify markets by metadata, not slug. | `/v1/market/slug/{slug}`, Crypto Schema doc **[verified]** | Discovery keys on metadata. Slug patterns are only a fallback hint. |
| F3 | **The official open reference (`priceToBeat`) is published by the venue**, "absent until a few seconds after the window opens". `settlementPrice` appears at resolution. | Live market response: `priceToBeat=81487.13` **[verified]** | We never need to compute the official reference ourselves. Strategies must handle the window where it's still `null`. |
| F4 | **The official BRTI index is available publicly at 1s granularity**: `GET /v1/asset-prices/history?assets=crypto:btc&bucket=ASSET_PRICE_BUCKET_1S&from=…&to=0`. | Live call returned 1s candles **[verified]** | This removes the spec's biggest risk. "Official reference unavailable" becomes a degraded-mode case, not the default. Binance/Coinbase become secondary features only. |
| F5 | Settlement rule: open = mean of the 60 per-second BRTI prices in `[T−60s, T)`, rounded to 2 dp. Close is computed the same way. **Up if close ≥ open (a flat result settles Up).** Last trade is at `interval_end`, and the instrument expires 30 min later. | Crypto Schema doc **[verified]** | Fair-value model input is the *expected 60s average*, not spot. A tie is Up, and that asymmetry matters near zero distance. |
| F5a | *Update:* **The public 1s index series is already the trailing 60-second average** (every point has `tickCount: 60`). Its value at `T−1s` equals `priceToBeat` (T = windowStart) and `settlementPrice` (T = windowEnd) **exactly in 49/49 resolved BTC 15m/1h markets checked**, and the outcome matched `close ≥ open → Up` in all 49. | Empirical check, 2026-10-17 **[verified empirically; not documented]** | We can compute the official reference live from public data. The series is smoothed, so volatility estimates must correct for the moving-average filter. The raw BRTI tick series is not available to us. |
| F6 | **One instrument per market, not separate YES/NO books.** `marketSides`: Yes = `long:true`, No = `long:false`. Buying "Down" means going short the same instrument, priced at 1 − bid. | Live `marketSides`, `outcomePrices` **[verified]** | Up/Down mapping = long/short on one book. The "No" ask is derived from the "Yes" bid. The sweep simulator must model this. |
| F7 | **Public L2 book is NOT available for crypto markets.** `GET /v1/markets/{slug}/book` returns `not found` for the BTC market but works for a sports market. Public BBO works and includes `askDepth`/`bidDepth` (level counts), `sharesTraded`, `openInterest`. | Live calls **[verified]** | **Blocker for realistic sweep fills without credentials.** See §2.1. |
| F8 | Markets WebSocket `wss://api.polymarket.us/v1/ws/markets` **requires API-key auth**. It has 3 types: `MARKET_DATA` (full book), `MARKET_DATA_LITE`, `TRADE`. Max 100 markets per subscription. **Sequence numbers, heartbeats, and snapshot-vs-delta semantics are undocumented.** | WS doc **[verified]**; semantics **[unverified]** | Real-time L2 needs read-only credentials. Book-integrity logic must be designed defensively and confirmed empirically. |
| F9 | Tick size 0.01, min qty 0.01, `feeCoefficient: 0.0695` is exposed per market. | Live market **[verified]** | Read the fee coefficient from market metadata and cross-check it against the versioned schedule. Alert on mismatch. |
| F10 | Fees: taker `Θ·C·p·(1−p)` with Θ=0.0695. Banker's rounding to $0.01. Multi-fill orders have a cumulative cap (an adjustment can only reduce a charge). **Oct 15 2026 08:00 ET:** the 17% crypto maker bonus ends. **Oct 19 2026 13:00 ET:** maker rebates become volume-tiered, and Tier 1 (<$10M/mo) gets **zero**. Taker rebate tiers also change, and Tier 1 (<$250k) gets zero. | Fees doc **[verified]** | A small paper account is Tier 1, so we model **zero rebates** by default after Oct 19. Fee schedules are versioned by effective timestamp with time-zone-aware boundaries. |
| F11 | Rate limit: 25 req/s shared per IP. 429 means wait ≥1s, then exponential backoff. ***Update:* the public gateway returned Cloudflare HTML 429s at only ~5 req/s in testing, so the budget is set to 2 req/s. **Orders not processed within 5s are rejected** as "Global Rate Limit Exceeded" (a latency stopgap). The SDK never retries order POSTs. | Rate-limits doc, SDK README **[verified]** | The REST poller budget is a global token bucket. The paper engine models 5s latency rejections in the stress profile. |
| F12 | Order preview **requires auth** and returns the generic `Order` schema (`avgPx`, `cumQuantity`, commissions). Whether it inserts nothing is implied by the docs, not stated. | Preview doc **[verified]** | Preview is an optional cross-check of the paper fill model when credentials exist. It can't be the paper engine. |
| F13 | **No public trader-level, leaderboard, or wallet endpoint exists.** Only `GET /v1/rfqs/trades` (anonymous RFQ fills). The US venue is account-based, not on-chain wallets. | llms.txt index **[verified]** | Strategy E for US = **UNAVAILABLE**. International (Polygon) wallet research is a separately labelled offline dataset, if pursued at all. |

## 2. Weaknesses and outdated assumptions in the spec

### 2.1 Critical
1. **L2 depth needs credentials.** The spec assumes real L2 is available. Without at least read-only API keys we only have BBO and level counts. A sweep simulator built on BBO alone would be *optimistic for any size beyond top-of-book*. **Proposal:** run the paper engine in two declared fidelity tiers:
   - `L2` when the authenticated WS book is live.
   - `BBO_ONLY`, which fills only up to a conservative assumed top-of-book size (configurable, default small) and rejects the rest. Every report is labelled with its fidelity tier.
2. **The settlement target is a 60s average, not a point price.** Momentum and fair-probability models that use spot-vs-reference distance are biased in the last ~2 minutes. Inside the closing window, the already-elapsed part of the average is known, so model variance must shrink correctly. Default to no-entry in the final 90s until this is validated.
3. **"BUY DOWN" isn't a separate order book** (F6). The spec's YES/NO framing implies two books. Getting this wrong double-counts liquidity.
4. **Backtesting has no history to start with.** The venue publishes BRTI history and settled prices, but **historical L2 and BBO aren't offered** as far as the docs show. Phase 4 can only validate *execution-aware* strategies once we've recorded our own data for weeks. Fair-probability calibration (Brier score, log loss) can start right away from BRTI history plus `priceToBeat`/`settlementPrice`. **Sequence the work around this: start the recorder on day one.**

### 2.2 Important
5. **Scope is ~6 services plus Postgres, Redis, Docker, Next.js, and Playwright** for a single-user paper system. Proposal: a **modular monolith**. That's one Python process with an internal async event bus, explicit interfaces (the spec's 8), plus Postgres and the Next.js app. Split it into services later only if needed. Drop Redis. Same safety, a fraction of the failure surface.
6. **"Fees documented in October 2026" are themselves changing in 2 days** (F10). The fee engine needs a dated schedule table, and backtests must look up the fee by fill timestamp in ET.
7. **No explicit clock-discipline requirement.** Add NTP-offset monitoring. Compare local receive time against venue `transactTime` and BRTI candle timestamps, and halt if skew exceeds a threshold.
8. **WS semantics are undocumented** (F8). Without sequence numbers, the "snapshot reconciliation" requirement becomes: periodic REST BBO cross-check against the WS top-of-book, a crossed-book detector, and a forced resubscribe on divergence.
9. **The risk limits aren't consistent with each other.** 0.5% of $1,000 is $5 per trade, but a binary contract at $0.49 loses the full premium. Define "risk" for binaries as **max loss = premium + fees**, not a stop distance. Stop-losses on 15m binaries rarely make sense, so make exits explicit strategy decisions run through the same sweep model.
10. **Smart Money for US is impossible as specified** (F13). Keep it as a documented UNAVAILABLE module. The two `polymarketwallets/*` repos are 0-star, days-old "ready-to-run copy trading bots" for the *international* on-chain venue. *Update after a read-only source review:* no exfiltration code was found. However, both bots get their trade signals from a commercial API (`api.pmwallets.com`, which needs a paid key) and sign orders with a Polygon private key against the international CLOB. **Reject for this project: wrong venue, third-party signal dependency.** They were cloned for reading only and never executed. If wallet research is wanted later, use only official international public data APIs in an isolated offline notebook.

### 2.3 Missing safety requirements to add
- A **live-trading code boundary**: no `LiveExecutionEngine.submit()` implementation ships at all. Only the interface plus a `NotImplementedError` stub exists. A CI test asserts that the authenticated order endpoints are unreachable from the paper process, with the network allowlist enforced in the HTTP client.
- **Read-only credential scoping:** if the API supports permission scopes, request market-data/read-only keys only. **[unverified whether scopes exist]**
- **Market-state guard** on every simulated order: `active && !closed && now < windowEnd − noEntry && priceToBeat != null` for strategies that need it.
- **Data-provenance tag** on every stored row (`source=gateway|ws|fixture|replay`). The UI refuses to render `fixture` rows outside test builds.

## 3. Reference repo triage (preliminary, metadata only)

| Repo | License / activity | Verdict |
|---|---|---|
| Polymarket/polymarket-us-python v2.4.1 | MIT, last commit 2026-10-08. Deps: httpx, pynacl, websockets | **Use** as the venue SDK behind our adapter. |
| Polymarket/polymarket-us-typescript | MIT, 2026-10-09 | Reference only. The frontend talks to our backend, never to the venue. |
| jabrahamtech/oraclebook | MIT, 0★, created recently | Audit for adapter and backtest patterns. Don't depend on it. |
| Synpath-ai/prediction-market-arbitrage-trading-bot | MIT, 43★ | Kalshi plus international Polymarket. Audit paper-fill logic for ideas only. |
| polymarketwallets/* (×2) | MIT, 0★, international copy-trading, commercial signal API | **Reject** (see 2.2 #10). |

A full source-level audit goes into `docs/RESEARCH_AUDIT.md` in Phase 1.

## 4. Proposed revised plan

1. **Phase 1 (research and architecture, ~short).** Write RESEARCH_AUDIT, ARCHITECTURE, STRATEGY_RESEARCH, SECURITY, and IMPLEMENTATION_PLAN. Set up the repo skeleton and CI with secret scanning.
2. **Phase 2a (data, unauthenticated).** Build the discovery/rollover service, BRTI 1s poller, BBO poller (within the 25 rps budget), and a Postgres recorder that stores source and receive timestamps. Build the terminal UI on real gateway data.
3. **Phase 2b (needs read-only API key from you).** Add the authenticated markets WS with full L2, book reconstruction, and integrity checks.
4. **Phase 3 (paper engine).** Implement the versioned fee engine with Decimal math, banker's rounding, and the cumulative cap. Add the long/short sweep, conservative maker queue model, four execution profiles, the risk engine, the ledger, settlement from the official `settlementPrice`, and restart recovery.
5. **Phase 4 (strategies).** Fair-probability baseline first: BRTI log-return vol, a model of the remaining 60s-average, and a fat-tail adjustment. Calibrate on BRTI history. Momentum and order-book signals are only evaluated on recorded data, and the combined strategy is compared to its components.
6. **Phase 5.** Document Smart Money as UNAVAILABLE for US.
7. **Phase 6 (QA).** Run the 20 required test classes, Playwright, a restart-recovery test, and a security review. Open a PR with real results.

Live trading stays out of scope. No order-submitting code ships.
