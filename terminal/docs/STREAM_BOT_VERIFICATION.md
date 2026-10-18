# Authenticated stream + autonomous bot verification

October 17, 2026. Scope: configure and verify the authenticated US market stream for the order-book paper bot, fix
the data-access problems behind the earlier zero/rare-fill observations, and verify the complete flow on real
production data. Strategy rules, sizing policy and risk limits are **unchanged** (config hash
`776c4c4b…cbf8` for `book-imbalance-aggressive-v2`). PAPER only: no exchange order path exists.

## What was wrong (verified)

- **Data access was the bottleneck.** Every signal read, valuation and arrival refresh used public REST (one GET/s
  shared, 10–300 s cooldowns after 429). Books were routinely older than the two-second freshness rule, which
  produced `STALE_BOOK`, `VENUE_RATE_LIMITED` and `SIGNAL_WARMUP`.
- **The stream path never ran.** The key was not configured. It would also have failed:
  - This python.org build has no CA bundle (`CERTIFICATE_VERIFY_FAILED`).
  - The SDK socket has no reconnect.
  - One malformed frame tore down the connection.
  - Stream books bypassed the out-of-order guard.
- **Stale docs.** The previous verification documents still said "zero aggressive fills, $1,000". In fact the bot
  had traded at 07:41 and 07:52 UTC: two BUY DOWN entries, both settled officially as losses (−$24.61 and −$198.69).
  That tripped the 20 % daily-loss entry halt. Those docs now carry a dated correction.
- **Launcher fragility.** PostgreSQL refused to start without `LC_ALL`, depending on the caller's environment.

## What changed

- `venue/stream.py`:
  - Read-only socket; the SDK is used only for request signing.
  - certifi TLS; reconnect with back-off; idle watchdog.
  - Only MARKET_DATA subscribe/unsubscribe can be sent.
  - Exactly one pending `recv()`. A concurrent recv on resubscribe dropped the connection with 1011 live; now
    fixed with a regression test.
  - Bad frames are counted, never fatal.
- `runtime.py`:
  - Frames are validated. Malformed frames, frames without a source time and out-of-order frames never replace a
    book.
  - `capture_book` prefers a stream book only if it passes the **unchanged** two-second freshness rule.
  - Arrival fills require a book whose receive **and** source times are after the modeled arrival. The runtime waits
    up to 1 s for the next frame, otherwise does a fresh REST read.
  - Stream books are recorded once per version (bounded raw volume, continuous coverage).
  - REST polling is skipped while a fresh stream book exists.
- UI:
  - Each market card shows its book source (US stream / Public REST), age and a STALE marker.
  - Data health shows stream frames, rejected frames and connections.
  - A same-day daily-loss lock states that RUN cannot clear it, and when the next risk day starts (5:00 PM ET).
- `scripts/local.py`: sets `LC_ALL` for `pg_ctl`.

## Tests

| Check | Result |
|---|---|
| Backend suite | **87 passed**, six subtests (70 pre-existing + 17 new: stream, arrival, freshness, recording, bad frames, review regressions, risk-day boundary) |
| Mutation checks | Removing the arrival-after rule, the stream freshness check or the single-recv guard each made tests fail |
| Production web build + TypeScript | PASS |
| Browser suite (against the running app) | **5 passed**. The bot test no longer assumes the real account is unlocked. When it is locked, it verifies the explanation and that RUN is refused |
| GitHub CI | Terminal backend tests on a fresh Postgres 17 runner, plus web typecheck and build: PASS |

## Independent review

A fresh read-only reviewer found **no Critical** violations of freshness, arrival-after fills, STOP during
in-flight reads, the no-order boundary or the three-observation rule. It reported three Important findings, all
fixed with regression tests:

1. Non-object or undecodable frames could drop the connection.
2. A frame without `transactTime` could replace a valid book.
3. Recorder coverage collapsed while the bot was idle.

Minor findings were fixed too: true receive time in recordings, source-time-after-arrival, liveness reset per
connection, bad-frame counting, one gap per disconnect, cache cleanup and sync-task errors.

## Real production observation (not fixtures)

- **Stream:** after restart, `CONNECTED` on one connection, 11,452 frames, **0 rejected**. Both BTC books came from
  the stream with source ages around 0.1 s. There were no REST cooldowns.
- **Risk day:** at 17:00 ET (21:00 UTC) the risk day rolled over legitimately. The aggressive baseline became
  $776.70 and the daily-loss lock expired on schedule. RUN never cleared it.
- **RUN through the website** (Playwright operator script, 21:00:45 UTC): status RUNNING.

| Step | Evidence (`evidence/stream-bot-production.json`) |
|---|---|
| Signal | Three distinct stream observations at 21:01:18.56, 21:01:23.81 and 21:01:28.83, all DOWN (imbalance −0.81 / −0.34 / −0.56; top-3 bids 1,997 vs asks 7,080), spanning 10.3 s, spread 0.01 |
| Sizing | Cadence target $271.84, total target $543.69, caps $310.68 / $621.36, cash $776.70. **Binding limit: conservative visible depth, 160.43 contracts.** Max cost $94.24 including fee |
| Order | BUY_DOWN 160.43 @ ≤0.57, created 21:01:28.99, modeled arrival 21:01:29.99 |
| Fill | 160.43 @ **0.57** (Down ask 0.56 + one adverse tick), fee $2.73, 21:01:30.20, on a book received after arrival. An independent recorder logged Up best bid 0.44 with 641 contracts at 21:01:30.12. That matches both the price and 50 % depth |
| STOP through the website | Bot STOPPED, no pending entries, **holding retained** (OPEN) for official settlement |
| Settlement | Official MARKET_STATUS_RESOLVED; settlementPrice 81,554.51 ≥ priceToBeat 81,534.22 → **UP**; outcomePrices `["1","0"]`. The DOWN position paid $0: **−$94.18** |
| Risk after | Cash/equity $682.52 (risk-day loss 12.1 %, below the 20 % halt). Three consecutive losses → **30-minute entry cooldown** until 21:52 UTC, enforced |

This is one autonomous trade. It shows the mechanics work end to end on real data. **It is not evidence of edge.**
Over the day the aggressive account went from $1,000.00 to $682.52 across three losing entries. The strategy remains
an unvalidated hypothesis.

## Remaining limits

- The stream sends books only on change and has no heartbeats. A quiet book older than two seconds is not
  tradable and falls back to REST, by design.
- The key is shared with a separate research recorder on this Mac. Both connected concurrently without being
  disconnected during observation, but the venue's per-key connection limit is undocumented.
- Local only (127.0.0.1). Not reachable from other devices.
