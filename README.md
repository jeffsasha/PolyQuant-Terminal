# PolyQuant Terminal

English local research terminal for **Polymarket US BTC 15m and 1h**. Real public production data, independent $1,000 paper accounts, and no real order gateway.

## Run on this Mac

The project is installed here with a Python virtual environment, pinned Node packages, and workspace-owned PostgreSQL 17. The services bind to loopback only. They are currently launched manually and do not automatically start after reboot.

```sh
cd PolyQuant-Terminal/terminal
python3 scripts/local.py start
```

Open **http://127.0.0.1:3000**. Both **127.0.0.1** and **localhost** are accepted as exact local Origins. There is no username field. Read the generated local password:

```sh
cat .local/login-password.txt
```

Paste it into **Local password**, then choose **Open terminal**. The password file and backend `.env` have mode 0600 and are excluded from Git. Sessions expire after 12 hours. Sign out with the arrow at the upper right.

```sh
python3 scripts/local.py stop
```

This stops only project-owned web/API processes and this workspace's database. Database files, paper balances, halts, and recordings remain in `.local/`. Do not delete that directory to fix a startup problem. Private local service logs are `.local/backend.log`, `.local/web.log`, and `.local/postgres.log`.

## Paper trading with production data

Select **Discretionary paper** for your manual paper account. The **Verification (paper)** account contains explicitly labeled production-data test trades and has separate money and risk. The Probability, Momentum and Order Book research accounts retain their own balances and remain disabled while models and reference data are unvalidated. No account returns are combined.

1. Click **UP** or **DOWN** on the BTC 15m or 1h contract to populate the paper ticket.
2. Set contracts, limit price and execution scenario. Click **Inspect costs & risk**. This fetches a fresh production book and shows costs, estimated depth and risk reasons.
3. If eligible, click **Place paper order**. **Orders** shows its ID/status; **Fills** shows executed price, quantity, fee and source-book hash. A preview is not a fill: arrival obtains a new snapshot and can cancel safely if data or liquidity is unavailable.
4. In **Positions**, click **Prepare exit**, inspect the sale ticket, then **Place paper order**. Closed/settled history and audit details remain visible. Unfilled IOC quantity cancels. There is no assumed maker queue fill.

Risk stays enforced: 0.5% maximum possible trade loss including fees, 5% combined exposure, 2.5% per cadence, two positions, one per cadence, 2% daily loss, and a 30-minute cooldown after three consecutive losses. New entries stop in the final two minutes of 15m contracts and final five minutes of 1h contracts. Manual discretionary tickets do not claim a fitted model probability or net edge; all financial/data gates still apply.

**Emergency stop** and **Pause paper account** persist for the selected account. **Resume paper account** cannot clear a same-day daily loss lock or unresolved persistence fault. No feed fault invents a close. Preview edits or contract rollover invalidate prior approval; rejected previews are recorded without placing an order.

## Reference investigation and production feed

**Reference-dependent strategies remain disabled in code.** Follow-up evidence found that 1S BRTI history is inconsistent with coarser buckets and the documentation's reconstruction example. An already-averaged 1S series is a plausible explanation, not a confirmed replacement specification. Read [BRTI follow-up research](docs/BRTI_FOLLOWUP_RESEARCH.md).

Manual trading uses production US books and official contract definitions. Public responses can be cached, unavailable, or rate limited. Fresh order reads use distinct cache keys, keep actual source/receive/cache timestamps, and retain the two-second freshness rule. The fallback uses at most one public GET/second, observes Retry-After and exponential cooldowns, and fails visibly during cooldown. Display polling is slower than an authenticated stream; inspect/order arrival refreshes again. Never interpret a stale displayed quote as tradable.

Official paper settlement requires **MARKET_STATUS_RESOLVED**, a matching slug, and a valid binary payout from the official settlement endpoint. Missing/404/ambiguous outcomes remain pending. BTC spot or reconstructed BRTI never supplies a guessed payout. Settled markets stay on correction watch, rechecked roughly every five minutes while running and after restart; compensating postings preserve prior history.

Coinbase BTC-USD candles are separately labeled spot context. Smart Money remains unavailable without a verified US performance feed. **Recordings → Verify recording** checks event causality and integrity; it is not a profitability backtest.

The authenticated US market socket is unverified until credentials are configured. Later, add the following variables to the backend `.env` locally and restart. Never use NEXT_PUBLIC_ for secrets or paste them into chat:

```dotenv
POLYMARKET_US_KEY_ID=
POLYMARKET_US_SECRET_KEY=
```

Only market-data socket code is used. The production REST transport allows fixed **GET** routes only; the paper engine has no exchange order client. `LIVE_TRADING_ENABLED=true` refuses startup, and the web process receives no backend credentials.

## Verification and limits

See [paper-trading follow-up verification](docs/PAPER_TRADING_FOLLOWUP_VERIFICATION.md), the earlier [verification report](docs/VERIFICATION_REPORT.md), and [acceptance criteria](docs/ACCEPTANCE.md). The local manual paper path is separate from the full strategy release: fitted models, full engine replay, authenticated stream reliability, 24-hour/load observation, Docker and remote CI/PR gates remain incomplete. There is no positive strategy-profitability claim.

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
