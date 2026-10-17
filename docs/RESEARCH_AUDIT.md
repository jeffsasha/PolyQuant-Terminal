# Research Audit

Audit date: 2026-10-17. Method: official docs were read, the public gateway was
probed live, and repositories were shallow-cloned into a temp directory **for
reading only**. No third-party code was installed or executed. Each claim below
cites the source file or API call it rests on.

## 1. Venue: Polymarket US (not Polymarket international)

Polymarket US is a CFTC-regulated DCM (QCX LLC). Accounts are KYC'd. There are
no on-chain wallets, so international CLOB code (`py-clob-client`, Polygon
signing, `clob.polymarket.com`, `gamma-api.polymarket.com`,
`data-api.polymarket.com`) **must not** be used for any part of this system.

### 1.1 Endpoints confirmed live (public gateway, no auth)

| Purpose | Call | Result |
|---|---|---|
| Market by slug | `GET /v1/market/slug/{slug}` | OK. Includes `assetPriceTerms`, `marketSides`, `feeCoefficient`, BBO quotes, `status`. |
| Event discovery | `GET /v1/events?categories=crypto&closed={false\|true}&endDateMin=…&endDateMax=…&limit=100` | OK. **Upcoming windows have `closed=true` and `status=MARKET_STATUS_CLOSED`**, so discovery must query both. |
| BBO | `GET /v1/markets/{slug}/bbo` | OK. `bestBid`, `bestAsk`, `bidDepth`/`askDepth` (level counts), `bidShares`/`askShares` (meaning **unverified**), `lastPriceSample.ts` (last *trade* time, not quote time), `state`. |
| L2 book | `GET /v1/markets/{slug}/book` | **`not found` for crypto markets.** Works for sports markets. |
| Settlement | `GET /v1/markets/{slug}/settlement` | `{"settlement": 1}` means Yes/Up paid, `0` means No/Down paid. Returns `not found` until resolved. |
| Index history | `GET /v1/asset-prices/history?assets=crypto:btc&bucket=ASSET_PRICE_BUCKET_1S&from=&to=` | OK. Asset id format is `crypto:btc`. `from` is required. |
| Series slug filter on events | `seriesSlug=` | **Ignored by the server.** Filter by metadata client-side instead. |

The authenticated host `api.polymarket.us` returns 401 without Ed25519 headers.

### 1.2 Market lifecycle as actually observed

| Phase | Observed fields |
|---|---|
| Listed / upcoming | `status=MARKET_STATUS_CLOSED`, `closed=true`, `priceToBeat=null`, `outcomePrices=["0","0"]`, `endDate = windowEnd + 30 min` |
| Open | `status=MARKET_STATUS_OPEN`, `closed=false`, `priceToBeat` set a few seconds after `windowStart` |
| Resolved | `status=MARKET_STATUS_RESOLVED`, `ep3Status=EXPIRED`, `settlementPrice` set, `outcomePrices=["1","0"]` or `["0","1"]`, `endDate` rewritten to `windowEnd + 10 s` |

Observed live on 2026-10-17 (06:00Z and 06:15Z windows): at window end, status went `OPEN → CLOSED` (≈2 s
after T), then `RESOLVING` (≈11 s), then `RESOLVED` with `settlementPrice` (≈17 s). The `/settlement` flag was
first returned to us ≈5 min later. The next window opened with `priceToBeat` set ≈4 s after T. **`RESOLVING` is not
in the docs.** `phase_of` maps it to `AWAITING_SETTLEMENT`.

**BBO is not available right after open.** `/v1/markets/{slug}/bbo` returned 404 for ~40 s (06:30Z window) and
~2.7 min (06:15Z window) after the venue already reported `MARKET_STATUS_OPEN`. Strategies must not assume an
executable quote at window start. The feed stays `stale` until the first BBO arrives.

`active` was `true` in every phase, so it is **not** a tradability signal. Phase
is derived from `status`, the clock, and the settlement fields together (see
`polyquant/domain/models.py`).

### 1.3 Reference price — empirical verification

The docs define open and close as the mean of 60 per-second BRTI prices in
`[T−60s, T)`, rounded to 2 dp. The public 1s series reports `tickCount: 60` on
every point, and its value at `T−1` equals the official figure exactly. Results
across all resolved BTC 15m and 1h markets between 2026-10-16 ~19:30 and
2026-10-17 05:30 UTC:

- `priceToBeat == index(windowStart − 1s)`: 49/49
- `settlementPrice == index(windowEnd − 1s)`: 49/49
- `settlement == 1 ⇔ settlementPrice ≥ priceToBeat`: 49/49

**Conclusion:** the public series is a trailing 60s average of BRTI. This is not
stated in the docs, so the system re-verifies it continuously. The recorder
compares every resolved market against the recorded index and raises a
`reference_rule_mismatch` data-quality event on any difference.

### 1.4 Rate limits

Documented: 25 req/s shared per IP and Cloudflare location. **Observed:** a
burst of ~5 req/s to the gateway drew Cloudflare **HTML** 429 responses, not
the documented JSON body. The client therefore:

- caps the gateway at 2 req/s by default;
- treats any 429, whether JSON or HTML, as a back-off signal (≥1 s, exponential, with jitter);
- never retries non-idempotent requests.

### 1.5 Fees (docs.polymarket.us/fees, read 2026-10-17)

See `services/engine/polyquant/fees/` (Phase 3) and SPEC_REVIEW F10. The
Oct 19 2026 13:00 ET change is to rebates only. The taker formula
`Θ·C·p·(1−p)` with Θ=0.0695 is unchanged. Banker's rounding to $0.01, with a
cumulative per-order cap.

## 2. Official SDKs

### polymarket-us (Python) v2.4.1 — **USE (selectively)**
- MIT. Last commit 2026-10-08. Deps: `httpx`, `pynacl`, `websockets`. Python ≥3.10.
- `client.py`: `GATEWAY_BASE_URL = "https://gateway.polymarket.us"` for public calls. `api.polymarket.us` for signed calls.
- `resources/markets.py`: `book()` → `/v1/markets/{slug}/book`, `bbo()`, `settlement()`.
- `websocket/markets.py`: path `/v1/ws/markets` on the authenticated host.
- README: retries only GET/DELETE, and never retries order placement.
- **Decision:**
  - Public REST: use our own thin `httpx` client. We need exact send and receive timestamps, HTML-429 handling, and a global token bucket shared by all pollers. The SDK's internal retries would hide latency and rate-limit events.
  - Authenticated markets WebSocket (Phase 2b): use the SDK, pinned to `==2.4.1`.
  - Order endpoints: never imported in this release (see SECURITY.md).

### polymarket-us-typescript — **REFERENCE ONLY**
- MIT. Last commit 2026-10-08. The browser never talks to the venue; it only talks to our backend.

## 3. Third-party repositories

| Repo | What the source actually does | Reuse | Adapt | Reject |
|---|---|---|---|---|
| **jabrahamtech/oraclebook** (MIT, last commit 2026-07-06, dep: `structlog`) | `core/protocols.py`: `Clock`, `Feed`, `Strategy`, `Executor`, `Gate`, `Venue` protocols. `core/paper_executor.py`: **fills every order immediately at its limit price for full size**, float math. Adapters target international `clob.polymarket.com` and `gamma-api`. `replay/recorder.py`: bus-topic recorder. `risk/circuit_breaker.py`. | Pattern: injected `Clock` protocol so replay and live share code. | Bus-topic recorder idea becomes Postgres-backed. Gate protocol becomes a central RiskManager. | Paper fill model (optimistic). International adapters. Float money. |
| **Synpath-ai/prediction-market-arbitrage-trading-bot** (MIT, last commit 2026-10-15, deps: `synpath` commercial SDK, `api.synpath.dev`) | Kalshi ↔ international Polymarket arbitrage. `trading/bot.py` paper trades "at the quoted prices… capped by the size quoted there". Float math. | — | The idea of capping fills at displayed size, as a sanity bound only. | Commercial data dependency, wrong venue, top-of-book-only fills. |
| **polymarketwallets/polymarket-copy-trading-bot** (Node) and **-python** (MIT, 2026-10-14) | `run.py`: `pmwallets.AsyncClient(api_key=…)` streams fills from the paid `api.pmwallets.com` service. `polymarket.py`: `py-clob-client-v2` with `chain_id=137` and a Polygon private key. `secrets.py` has a reasonable redaction registry. No exfiltration found at grep-level review. | Idea: a secret-redaction registry for logs (we implement our own). | — | Everything else: international venue, paid signal source, private-key signing. |

Further GitHub discovery for strategy and backtesting repos is deferred to
Phase 4. No candidate is adopted without the same source-level review.

## 4. Unsupported or uncertain features

| Feature | Status | Plan |
|---|---|---|
| Public L2 book for crypto markets | **Not available** | Authenticated WS (Phase 2b, needs read-only key) |
| WS sequence numbers / heartbeats / snapshot-vs-delta | **Undocumented** | Empirically characterise in 2b. Defensive integrity checks. |
| Historical L2 / BBO | **Not offered** | Record our own from day one (this phase) |
| Raw (unsmoothed) BRTI ticks | **Not available publicly** | Model on the 60s-average series. Correct vol for smoothing. |
| `bidShares` / `askShares` semantics | **Unverified** | Record raw values, compare with WS L2 in 2b |
| Public trader-level data (Smart Money) | **Not available on US** | Strategy E = UNAVAILABLE |
| API key permission scopes (read-only) | **Unverified** | Check at polymarket.us/developer when you create the key |
| Order preview side-effects | Implied none, not stated | Phase 3 cross-check only, never in a hot path |
