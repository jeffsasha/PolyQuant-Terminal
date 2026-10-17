# Security

This is a financial system. The first release is **paper only**.

## 1. Secrets

- Credentials are read **only** from the environment (`POLYMARKET_US_KEY_ID`,
  `POLYMARKET_US_SECRET_KEY`) on the backend. They are never accepted from the
  frontend, config files in git, CLI arguments, or chat.
- `.env` is git-ignored. `.env.example` holds placeholders only.
- `polyquant.config.Settings` stores the secret as `pydantic.SecretStr`. Its
  `repr`/`str` is masked.
- The logging filter redacts any registered secret value, plus anything shaped
  like a base64 Ed25519 key, before a record is emitted.
- CI runs `gitleaks` on every push and PR. A finding fails the build.
- Request a **read-only / market-data** key if the developer portal offers
  scopes. Whether it does is **unverified**. Check when you create the key.

## 2. Network allowlist

`venue/gateway.py` only talks to hosts in `ALLOWED_HOSTS`:
`gateway.polymarket.us`, plus `api.polymarket.us` for the WS in 2b. It sends
**GET only**. Any other method raises `ForbiddenRequest` before a socket is
opened. A test enforces this.

### 2.1 Markets WebSocket (Phase 2b)

`venue/ws_markets.py` connects only to `wss://api.polymarket.us/v1/ws/markets` and signs the handshake with the
SDK's `create_auth_headers` (`GET /v1/ws/markets`). `_send` refuses anything except `subscribe` and
`unsubscribe` for `SUBSCRIPTION_TYPE_MARKET_DATA` / `SUBSCRIPTION_TYPE_TRADE`. Private channels (orders, positions,
balances) are never opened. Tests assert both rules. TLS uses certifi's CA bundle explicitly.

### 2.2 Credential handling lessons (2026-10-17)

- The key file must be plain text named exactly `.env`. A rich-text file (`KEY API.env`, RTF) was not loadable and
  was not covered by `.gitignore`. It was never committed. `.gitignore` now also covers `*.env` and `*.rtf`.
- While checking that file's format, a diagnostic `awk` printed a fragment of the secret into the development
  session transcript. The owner said they would revoke that key, and a new one is now in `.env` (revocation not
  verified by us). **Rule since then:** credentials are verified
  only by loading them through `Settings` and printing booleans and lengths, never raw file lines.
- Recommended way to create `.env`: a `read -s` prompt (README), so the secret never appears on screen or in
  shell history.

## 3. Live-trading boundary (defence in depth)

1. **Code.** No module imports the SDK's `orders` resource or calls an order
   endpoint. `LiveExecutionEngine` methods raise `LiveTradingDisabled`
   unconditionally. There is no code path that places an order.
2. **Config.** `LIVE_TRADING_ENABLED` is a constant `False` in
   `polyquant/config.py`. It is *not* read from the environment, so setting an
   env var or flipping a UI toggle changes nothing.
3. **Tests.** A static test greps the package for order-endpoint paths
   (`/v1/orders`) and SDK `orders.` usage, and fails if found outside the stub.
4. **Process.** Enabling live trading requires a future reviewed PR that
   changes (1)–(3), separate deployment approval, and explicit owner
   confirmation. See IMPLEMENTATION_PLAN §"Live-trading requirements not yet
   approved".

## 4. Uncertain outcomes (applies to the future live adapter and to the paper engine)

A timed-out submission is never blindly retried. Capital is reserved while an
outcome is unknown, and the order is reconciled against the venue before any
further action. The paper engine models this state too.

## 5. API surface (dashboard backend)

- Phase 2a's API is **read-only** and binds to `127.0.0.1` by default.
- Before any deployment beyond localhost: TLS, authenticated sessions, CSRF
  protection on state-changing routes, rate limiting, and an RBAC
  owner/viewer split.

## 6. Data integrity

- `index_points` never overwrites. Conflicts become quality events.
- Event tables are append-only. No `UPDATE`/`DELETE` statements touch them in
  application code.
- Migrations run inside transactions.
- Backups: `scripts/backup-db.sh` (pg_dump) is documented in the README. Owner
  runs it on a schedule of their choosing.

## 7. Supply chain

- Python dependencies are pinned in `pyproject.toml` with lower and upper
  bounds, and audited with `pip-audit` in CI.
- Third-party repos are reviewed at source level before any reuse. Nothing
  from them is vendored in 2a (RESEARCH_AUDIT §3).
- Downloaded or cloned code is never executed.
