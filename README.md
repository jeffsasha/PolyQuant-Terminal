# PolyQuant Terminal

English local research terminal for **Polymarket US BTC 15m and 1h**. Real public production data, three independent $1,000 paper accounts, and no real order gateway.

## Run on this Mac

The project is installed here with a Python virtual environment, pinned Node packages, and workspace-owned PostgreSQL 17. The services bind to loopback only. They are currently launched manually and do not automatically start after reboot.

```sh
cd PolyQuant-Terminal/terminal
python3 scripts/local.py start
```

Open **http://127.0.0.1:3000**. Use **127.0.0.1**, because the mutation Origin check is configured for that exact address. There is no username field. Read the generated local password:

```sh
cat .local/login-password.txt
```

Paste it into **Local password**, then choose **Open terminal**. The password file and backend `.env` have mode 0600 and are excluded from Git. Sessions expire after 12 hours. Sign out with the arrow at the upper right.

```sh
python3 scripts/local.py stop
```

This stops only project-owned web/API processes and this workspace's database. Database files, paper balances, halts, and recordings remain in `.local/`. Do not delete that directory to fix a startup problem. Private local service logs are `.local/backend.log`, `.local/web.log`, and `.local/postgres.log`.

## Current operating state

**Reference-dependent strategies remain disabled in code.** Five public BRTI history reconstructions failed to reproduce the official contract thresholds. `REFERENCE_VALIDATED=true` cannot bypass this gate, and `LIVE_TRADING_ENABLED=true` refuses startup. Resume clears eligible manual paper halts; it cannot activate a reference-dependent strategy.

The terminal collects real US contract definitions, available public order books, official US BRTI history, and separately labeled Coinbase BTC-USD spot candles. Public REST responses can be cached or unavailable. A displayed quote is not proof that it is fresh enough to trade. Source age, cache age, transport errors, and missing books are visible. No missing prices or fills are synthesized.

The authenticated US market socket is **not verified** until you configure your credentials. Later, add only the following variables to the backend `.env` locally, then restart the services. Never use `NEXT_PUBLIC_` for secrets or paste credentials into chat.

```dotenv
POLYMARKET_US_KEY_ID=
POLYMARKET_US_SECRET_KEY=
```

The backend imports only the official market-data socket; its REST transport allows fixed production **GET** routes. The execution engine has no exchange credentials or order client. The web process is started without backend credentials.

## What to inspect

- Select Probability, Momentum, or Order Book to inspect isolated account state. Returns are never added across accounts.
- Inspect **Data health** for the failed reference gate and production feed limitations.
- Select a contract and use **Inspect costs & risk** for a paper risk preview. **Record paper attempt** persists the rejection reason. New reference-dependent entries are blocked.
- **Emergency stop** persists a halt for the selected paper account and cancels its pending orders. Positions remain held. **Resume paper account** cannot clear a same-day daily loss lock or unresolved storage fault.
- **Recordings** lists checksummed raw captures. Replay is currently an integrity/causality diagnostic, not a profitability backtester.

## Verification and limitations

See [Verification report](docs/VERIFICATION_REPORT.md), [Acceptance criteria](docs/ACCEPTANCE.md), and [Reference discrepancy](docs/REFERENCE_DATA_DISCREPANCY.md).

The local interface is runnable, but the complete engineering/research acceptance matrix is not passed. Models are unfitted; reference-dependent automation is blocked; authoritative automatic settlement is not enabled; authenticated streaming, a 24-hour run, load testing, and Docker deployment remain unverified. No positive strategy-return claim is made. Smart Money research is deferred without a verified US account-performance feed.

## Rebuild and test

Next.js Turbopack could not spawn its CSS worker on this host. Use the supported Webpack build:

```sh
PYTHONPATH=services:tests/unit .venv/bin/python -m pytest -q --tb=short
# Integration tests refuse to use any database except polyquant_test.
POLYQUANT_NODE="$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
"$POLYQUANT_NODE" apps/web/node_modules/next/dist/bin/next build apps/web --webpack
PLAYWRIGHT_BROWSERS_PATH="$PWD/.local/browsers" "$POLYQUANT_NODE" apps/web/node_modules/@playwright/test/cli.js test --config apps/web/playwright.config.ts
```

The native launcher uses the installed Homebrew PostgreSQL 17 binaries and this Mac's bundled Node runtime. It is not a portable installer. Compose files preserve a migration path but have not been executed because Docker is unavailable on this host. Keep the services local; this build is not an internet-hosted application.

## Backup and restore drill

Stop services before a comparison drill so the source does not change. Start only the workspace database, then:

```sh
python3 scripts/local.py stop
python3 scripts/local.py db
.venv/bin/python scripts/backup.py backup .local/backups/paper.dump
.venv/bin/python scripts/backup.py verify .local/backups/paper.dump
python3 scripts/local.py start
```

Restore verification creates and removes a new random disposable database; it never overwrites `polyquant`. Backups contain sensitive local sessions and must stay private. Also preserve `.local/raw`, its manifest files, and the private `.env` separately; a database dump alone cannot restore raw recordings. The comparison checks every listed application table's canonical row hashes plus counts and account state; it does not test every possible restore failure or PostgreSQL catalog property.
