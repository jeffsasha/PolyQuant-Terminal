# Test Report — Phase 2b (authenticated markets WebSocket, local L2 book)

Date: 2026-10-17. Same machine as Phase 2a. All results below were actually run.

## Automated tests

`pytest -q` with the test database: **93 passed, 0 skipped** (63 from 2a + 30 new). `ruff`: clean.
`pip-audit`: no known vulnerabilities.

New coverage:

| Area | Tests |
|---|---|
| Book parsing on **recorded real frames** | full-book parse, Decimal levels, Down ladder = mirror of Up book, microprice/imbalance bounds |
| Frame validation | unsorted, duplicate level, qty ≤ 0, crossed, price outside (0, 1), binary float, missing `transactTime` → rejected; previous book kept |
| Ordering | out-of-order `transactTime` rejected; equal timestamps accepted (seen live) |
| Window boundary (real frames) | old window OPEN → CLOSED → EXPIRED with empty book; new window book within 1.3 s of open |
| Trades (real frames) | id, unit (`USD`), sides; de-duplicated on `id` in Postgres |
| Stream | Ed25519 handshake signature verified with a test key; MARKET_DATA + TRADE only; resubscribe on slug change; reconnect and resubscribe after a drop; idle watchdog; back-off after auth failure; private/order channels and non-subscription messages refused |
| Reconciliation | strict match, corroborated, uncorroborated, alignment on the CDN body time, insufficient-history guard (regression) |
| Clock | skew lower bound and alert crossing |
| CDN metadata | `cf-cache-status`, `Age`, `Last-Modified` parsed; data age used for freshness |
| Recorder | book snapshots (full counts kept with `BOOK_RECORD_LEVELS` cap), trades with dedupe |

## Live runs (real venue, read-only key)

Captures: 20 s and 6 min raw (`scripts/ws_capture.py`). Then 4 engine runs between 07:55 and 08:31 UTC (12, 6, 5 and
7 min), crossing the 08:00 (15m and 1h), 08:15 and 08:30 boundaries.

| Metric | Result |
|---|---|
| WS book frames processed | 8,001 / 4,685 / 8,389 in the three runs where it was read from `/health` |
| **Rejected frames** | **0** in every run (and 0/5,487 in the raw capture) |
| Unplanned disconnects / idle reconnects | 0 |
| Rollover | subscriptions moved to the new windows each time; the new book was live ~1.3 s after open, while REST `/bbo` returned 404 for 40 s to 2.7 min |
| Recorder | 0 dropped events, 0 write errors. Database totals: 26,144 book snapshots, 8,758 trades |
| Official index completeness | 9,593 / 9,593 seconds (05:50:43 → 08:30:35) across 7 restarts |
| REST BBO corroborated by WS history (final code) | **95.8 %** (69/72). Strict time-aligned match 70.8 %. |
| Local clock lag (lower bound from venue timestamps) | 75–115 ms. NTP showed the Mac ~120 ms slow. |

## Bugs and wrong assumptions found by the live runs (fixed on this branch)

1. **WS TLS failure.** The python.org build has no CA store and the SDK's socket uses it. The engine now uses
   certifi explicitly.
2. **REST BBO is CDN-cached for up to 30 s.** Phase 2a's BBO freshness (request round trip) was misleading. It now
   uses data age from `Last-Modified`/`Age`, and the REST BBO stale threshold was raised to 40 s. The planned
   "≥99.9 % REST match" exit criterion was the wrong yardstick and was replaced by the corroboration metric.
3. **False "uncorroborated" alerts right after start-up**, when WS history didn't reach back before the REST body's
   time. A minimum-history guard was added, with a regression test.
4. Server `unsubscribed` acknowledgements were reported as unknown frames. They're now treated as control frames.

## Open items (not hidden)

- **3 of 72 REST samples (one cached body) were never seen in the WS book.** This happened in the final 50 s of a
  15m window: REST 0.49/0.62 vs WS 0.61/0.62. A 100 ms WS conflation hypothesis was tested and **not supported**
  (35–40 % of frame gaps are under 95 ms). Still unexplained. Candidates: a non-atomic REST snapshot, or a
  sub-frame transient. Tracked via the `bbo_uncorroborated` alert.
- **Trade `quantity` unit:** the venue labels it `USD`. Whether it means contracts or notional is unverified.
  It must be resolved before trades feed a fill or queue model.
- **No 24 h soak yet.** The longest WS run was 12 min.
- **Storage:** full-depth recording measured at ~1.4 GB/day of level data. Retention isn't implemented yet.
- **The local clock is ~120 ms slow.** Latency numbers from this machine carry that bias. Phase 3's risk engine
  should block trading when `clock.alerting` is true.
