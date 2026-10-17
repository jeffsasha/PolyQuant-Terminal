# Architecture

## 1. Shape: a modular monolith

```
                ┌───────────────────────── polyquant (one Python 3.12+ process) ─────────────────────────┐
 gateway.poly-  │  venue/gateway.py ──► marketdata/discovery ──► InstrumentRegistry                      │
 market.us ◄────┤   (token bucket,     marketdata/reference  ──► IndexBuffer (BRTI 60s-avg series)       │
 (public REST)  │    timestamps)       marketdata/bbo        ──► latest BBO per instrument               │
                │                            │                                                           │
 api.poly-      │  venue/ws_markets (2b) ────┤  (authenticated L2, SDK)                                  │
 market.us ◄────┤                            ▼                                                           │
 (signed, 2b)   │                     marketdata/quality  ──► DataHealth (staleness, latency, gaps)      │
                │                            │                                                           │
                │                            ▼                                                           │
                │                    recorder/store ──────────────────────────────► PostgreSQL           │
                │                                                                                        │
                │  (Phase 3+) strategy → risk → paper execution → ledger → settlement                     │
                │  api/ (FastAPI, read-only in 2a) ─────────────────────────────► apps/web (Next.js)      │
                └────────────────────────────────────────────────────────────────────────────────────────┘
```

Services are packages inside one process, linked by explicit interfaces
(`polyquant/interfaces.py`). Any package can later become its own process
behind the same interface. Redis is not used. Postgres is the only stateful
dependency.

## 2. Interfaces (the contract every phase builds on)

| Interface | Implementations | Phase |
|---|---|---|
| `Clock` | `SystemClock`, `FakeClock` (tests, replay) | 2a |
| `MarketDataProvider` | `GatewayMarketData` (REST); `WsMarketData` (2b); `ReplayMarketData` (4) | 2a |
| `ReferencePriceProvider` | `GatewayIndexProvider` (official 60s-avg BRTI series) | 2a |
| `SettlementProvider` | `GatewaySettlement` | 2a |
| `FeeModel` | `VersionedFeeSchedule` | 3 |
| `RiskManager` | `CentralRiskManager` | 3 |
| `ExecutionEngine` | `PaperExecutionEngine`; `LiveExecutionEngine` (**stub that raises**) | 3 |
| `PortfolioLedger` | `PostgresLedger` | 3 |
| `Strategy` | baseline strategies | 4 |

## 3. Domain model

- **Instrument** is one BTC Up/Down market. Fields: `slug`, `market_id`,
  `horizon` (15m | 1h), `window_start`/`window_end` (UTC), `index_symbol`
  (BRTI), `price_to_beat`, `settlement_price`, `fee_coefficient`, `tick_size`,
  `min_qty`, and a raw-status snapshot.
- **Outcome mapping.** There is one instrument per market. `long` = Yes = **Up**
  and `short` = No = **Down**. Buying Down is selling the long side: its price
  is `1 − bestBid(Yes)` and its liquidity is the Yes bid stack. The UI shows
  both legs, but liquidity is never double-counted.
- **Phase** is derived by `phase_of(instrument, now)`, never read from a single
  flag:
  `UPCOMING → OPEN → (no-entry window) → CLOSED_AWAITING_SETTLEMENT → SETTLED`.
  Any inconsistent combination (for example status OPEN while `now ≥ window_end`)
  resolves to `UNKNOWN`, which blocks trading.
- **Reference point.** `IndexPoint(ts, value, tick_count)` comes from the
  venue's 1s series. The official open is `index(window_start − 1s)` and the
  official close is `index(window_end − 1s)` (empirically verified, see
  RESEARCH_AUDIT §1.3). The venue's own `priceToBeat` is authoritative. Our
  derived value is a cross-check only.

All money and price values are `decimal.Decimal`. JSON numbers are parsed
from strings and never pass through `float`.

## 4. Data flow and timestamps

Every recorded row carries:

- `source_ts`: the venue's timestamp when one exists. For index points this is
  the candle timestamp. For BBO it is `lastPriceSample.ts`, which is a **trade**
  time, not a quote time.
- `sent_at` / `recv_at`: local UTC timestamps taken around the HTTP request.
- `source`: `gateway` | `ws` | `fixture` | `replay`.

**Observed latency** = `recv_at − source_ts` for index points, and HTTP
round-trip time for BBO. The BBO feed has no quote timestamp, so freshness is
bounded by poll interval plus RTT. That limit is reported as such, never
hidden.

## 5. Polling budget (Phase 2a)

One global async token bucket guards the gateway at 2 req/s by default. That
is well under the observed Cloudflare threshold. Allocation:

| Loop | Interval | Calls |
|---|---|---|
| Index poller | 1 s target | 1 per tick, fetching `from = last_ts+1` |
| BBO poller | round-robin across OPEN instruments | remaining budget (≈1 req/s; each 15m and 1h book is refreshed every ~2 s) |
| Discovery | 60 s, plus on any window boundary | 2 |
| Instrument refresh (priceToBeat / settlement) | OPEN instruments missing `priceToBeat`, and ended instruments missing settlement | bounded, 5 s |

If the bucket starves, the index poller has priority because the reference
matters most. Phase 2b moves BBO and L2 to the authenticated WS, which frees
the REST budget.

## 5a. Authenticated markets WebSocket (Phase 2b)

```
api.polymarket.us/v1/ws/markets ──► venue/ws_markets.MarketsStream ──► marketdata/books.BookService ──► sink
   (Ed25519 handshake via SDK        reconnect + resubscribe,           validate → replace L2Book,      (recorder:
    create_auth_headers)             idle watchdog, msg allowlist        trades, skew, reconcile          book_snapshots,
                                                                                                          trades)
```

- **Subscriptions:** current and next window per horizon (≤4 slugs), MARKET_DATA + TRADE. Re-synced every second
  by the rollover loop, so the next window's book is live from its first frame (T+1.3 s observed).
- **Book model:** each frame is a full book (RESEARCH_AUDIT §1.6). It is validated (sorted, unique, qty > 0, price
  in (0, 1), not crossed, `transactTime` not older than the current book) and then replaces the book. Invalid
  frames are rejected and logged; the previous book is kept.
- **Quote source:** `/v1/markets` exposes `quote_source = ws | rest | none`. The WS book is preferred whenever its
  feed is fresh.
- **Reconciliation:** REST BBO is polled every 5 s (`BBO_RECONCILE_INTERVAL_S`) and compared with the WS top at the
  REST body's production time (`Last-Modified`). It reports strict match and corroborated rates; uncorroborated
  values raise `bbo_uncorroborated`.
- **Clock:** `ClockSkewMonitor` derives a lower bound on local clock lag from `transactTime` and alerts above 250 ms.

## 6. Data quality and staleness

`DataHealth` tracks, for each feed: last `source_ts`, last `recv_at`, a rolling
latency p50/p95, error counts, and a `stale` flag. Default thresholds:

- index: stale if no new point for 5 s;
- BBO: stale if not refreshed for 10 s;
- discovery: stale if it hasn't succeeded for 180 s.

Every stale/fresh transition is written to `data_quality_events`. From Phase 3,
the risk engine refuses entries when any feed it depends on is stale. 2a only
records and surfaces the state.

Gaps in the index series (missing seconds) are detected and backfilled from
the history endpoint, which is idempotent. Unfilled gaps are logged.

## 7. Persistence

PostgreSQL 16 or 17. Plain-SQL migrations live in
`polyquant/recorder/migrations/NNNN_*.sql` and are applied in order inside a
transaction, tracked in `schema_migrations`. Tables (2a):

- `instruments`: current state, upserted.
- `instrument_events`: **append-only** state-change log (phase, priceToBeat, settlement).
- `index_points`: PK `(asset, ts)`, `ON CONFLICT DO NOTHING`. A conflicting value is logged as a quality event, never overwritten.
- `bbo_snapshots`: append-only.
- `data_quality_events`: append-only.

Retention is configurable (`RETENTION_DAYS_BBO`, default 0 = keep forever). We
keep everything while there is no historical source to replace it.

## 8. Repository layout

```
apps/web/            Next.js terminal (Phase 2 UI; placeholder in 2a)
packages/            shared contracts (TS types generated from the API schema, later)
services/engine/polyquant/
  config.py clock.py interfaces.py
  domain/            models, settlement rule, time utilities
  venue/             gateway client, response parsing
  marketdata/        discovery, reference, bbo, quality
  recorder/          db, store, migrations
  api/               FastAPI (read-only)
  cli.py
tests/               unit + integration (fixtures in tests/fixtures, never shown as live)
docs/
```

## 9. Live-trading boundary

See SECURITY.md §3. In short, no module in this release imports an order
endpoint. `LiveExecutionEngine` is an interface-conformant stub whose methods
raise. A test asserts the HTTP client refuses any non-GET request.
