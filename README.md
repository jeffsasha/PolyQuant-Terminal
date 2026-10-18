# PolyQuant Terminal

Research and **paper-trading** infrastructure for Polymarket US BTC 15-minute and 1-hour Up/Down markets.

The goal is to find out whether a real, repeatable, executable edge exists. The goal is not to look
profitable.

> **Mode: PAPER ONLY.** Live order submission is disabled at the code boundary (`docs/SECURITY.md` §3).
> No environment variable, config file or UI toggle can enable it.

## Status

| Phase | State |
|---|---|
| 0–1 Spec review, research, architecture | done: see `docs/` |
| 2a Public-data layer and recorder | **done** (this branch, see `docs/TEST_REPORT_PHASE2A.md`) |
| 2b Authenticated L2 WebSocket | **done** (see `docs/TEST_REPORT_PHASE2B.md`). Runs automatically when `.env` has a key. |
| 2c Next.js terminal UI | blocked on Node.js ≥20 being installed |
| 3 Fees, paper execution, risk, ledger, settlement | **done** (see `docs/TEST_REPORT_PHASE3.md`) |
| 4 Strategy framework, fair-probability baseline, calibration, replay | **done** (see `docs/TEST_REPORT_PHASE4.md`; no edge shown) |
| 5–6 Smart Money doc, QA | not started |

Key verified facts that shape the design (details in `docs/RESEARCH_AUDIT.md`):

- The official reference index is public. The venue's 1s BTC series is already the trailing 60s BRTI
  average. Its value at T−1s equals `priceToBeat` / `settlementPrice` exactly (49/49 resolved markets checked).
  `polyquant verify-references` re-checks this, and so does the running recorder.
- Up/Down is **one instrument**: long = Up, short = Down. Down ask = 1 − Up bid.
- The public L2 book is **not** available for crypto markets. The authenticated WebSocket sends **full books** on
  every change (no deltas, no sequence numbers) and is live ~1.3 s after a window opens.
- **REST `/bbo` is Cloudflare-cached for up to 30 s.** It is used only to cross-check the WS book, never as an
  executable quote.
- The public gateway rate-limits (HTML 429) well below the documented 25 req/s. The budget is set to 2 req/s.

## Run it (macOS, verified)

Prerequisites: Python ≥3.12 and PostgreSQL 16/17 binaries (`brew install postgresql@17`).

```bash
python3 -m venv .venv
```

```bash
.venv/bin/pip install -e ".[dev]"
```

```bash
scripts/dev-db.sh start
```

```bash
cp .env.example .env
```

Optional, for the L2 WebSocket: add your read-only Polymarket US key without it appearing on screen or in shell
history:

```bash
read -r "KID?Key ID: " && read -rs "SEC?Secret key: " && echo && (umask 077 && printf 'POLYMARKET_US_KEY_ID=%s\nPOLYMARKET_US_SECRET_KEY=%s\n' "$KID" "$SEC" >> .env) && unset KID SEC && echo saved
```

```bash
.venv/bin/polyquant db-migrate
```

```bash
.venv/bin/polyquant run
```

The last command starts discovery, the official index poller, the BBO poller, the refresher and the recorder. It
also serves a read-only API on `http://127.0.0.1:8787`:

| Endpoint | What |
|---|---|
| `/health` | Feed freshness, latency p50/p95, gateway stats, `mode: PAPER` |
| `/v1/markets` | Current and next 15m/1h windows: phase, countdown, official `priceToBeat`, distance from the reference, WS book summary (Up/Down bid/ask, sizes, microprice, imbalance), `quote_source` |
| `/v1/markets/{slug}/book?levels=20` | Full L2 ladder from the WebSocket, as Up and as Down |
| `/v1/reference?seconds=300` | Recent official index points |
| `/v1/alerts` | Recent data-quality events (stale feeds, gaps, revisions, rule mismatches) |

Other commands:

```bash
.venv/bin/polyquant status
```

```bash
.venv/bin/polyquant verify-references --hours 3
```

```bash
scripts/backup-db.sh
```

Docker: `docker-compose.yml` and `Dockerfile` are provided but **have not been tested** (Docker isn't installed on
the development machine).

## Continuous recorder (macOS)

Order books only exist for the time the recorder runs, so it should run continuously. A launchd user agent (no
admin rights) keeps it up: it starts the project-local Postgres if needed, restarts on crash, and prevents idle sleep
while running (`PQ_PREVENT_SLEEP=0` to disable). Closing a laptop lid still stops recording.

```bash
scripts/recorder-agent.sh install
```

```bash
scripts/recorder-agent.sh status
```

Also `logs`, `stop`, `start` and `uninstall`. Logs go to `~/Library/Logs/polyquant/recorder.log`. Expect roughly
1.5–2 GB/day of database growth with full-depth books (`BOOK_RECORD_LEVELS` caps it). It records the official index,
venue books and trades, REST BBO cross-checks, and Kraken BTC/USD 1 s spot bars (Strategy A's feature).

After a gap (machine asleep), backfill what the venue keeps:

```bash
.venv/bin/polyquant backfill --since 2026-10-17 && .venv/bin/polyquant backfill-spot --since 2026-10-17
```

Order books cannot be backfilled.

## Paper trading

The engine runs a paper account (default $1,000, conservative execution profile) against the live WS book. Order
endpoints need `API_TOKEN` in `.env`:

| Endpoint | What |
|---|---|
| `GET /v1/paper/account` | Cash, reserved, equity (positions at best bid), daily PnL, halts, positions, working orders |
| `GET /v1/paper/preview?slug=&outcome=UP&side=BUY&qty=&limit_px=` | Fill and fee estimate under all four profiles |
| `POST /v1/paper/orders` (token) | `{client_order_id, slug, outcome, side, qty, limit_px, tif: IOC\|GTC, post_only, model_prob}` |
| `DELETE /v1/paper/orders/{id}` (token) | Cancel a working order |
| `POST /v1/paper/kill-switch` (token) | `{active, reason}`: persistent emergency stop; cancels working entries |
| `GET /v1/paper/orders`, `/fills`, `/pnl`, `/risk-decisions?rejected_only=true`, `/profiles` | Audit views |

Every order goes through the central risk engine. Every decision, including rejections with all their reasons,
is stored in `risk_decisions`.

## Research

```bash
.venv/bin/polyquant backfill --since 2026-09-22
```

```bash
.venv/bin/polyquant calibrate
```

```bash
.venv/bin/polyquant backtest
```

```bash
.venv/bin/polyquant strategy-a
```

These write `reports/phase4/calibration.md` (chronological split, untouched test set, walk-forward, model vs
market) and `reports/phase4/backtest.md` (execution replay over recorded books, all four profiles).

## Tests

```bash
POLYQUANT_TEST_DATABASE_URL=postgresql://polyquant@127.0.0.1:54329/polyquant_test .venv/bin/pytest -q
```

Unit tests use **recorded real gateway responses** in `tests/fixtures/gateway/`. They are labelled as fixtures and
are never shown as live data. Integration tests need the test database. Without `POLYQUANT_TEST_DATABASE_URL` they
are skipped, never silently passed. CI (`.github/workflows/ci.yml`) runs gitleaks, ruff, pytest against
Postgres 17, and pip-audit.

## Layout

```
services/engine/polyquant/   engine (one process; see docs/ARCHITECTURE.md)
tests/                       unit + integration tests, recorded fixtures
docs/                        SPEC_REVIEW, RESEARCH_AUDIT, ARCHITECTURE, STRATEGY_RESEARCH, SECURITY, IMPLEMENTATION_PLAN
apps/web/                    Next.js terminal (Phase 2c)
packages/                    shared contracts (later)
scripts/                     dev database, backups
```

## Live-trading requirements not yet approved

See `docs/IMPLEMENTATION_PLAN.md`. Nothing on that list is implemented.
