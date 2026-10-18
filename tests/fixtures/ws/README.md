# WebSocket fixtures

Raw frames recorded from the authenticated Polymarket US markets WebSocket (`wss://api.polymarket.us/v1/ws/markets`)
on 2026-10-17 between 07:44:53 and 07:50:52 UTC with `scripts/ws_capture.py`. Each line is
`{"recv_at": <local UTC>, "frame": <frame>}`. The local clock was ~120 ms behind NTP at the time, so `recv_at` reads
earlier than true time.

- `book_1h_sequence.jsonl`: the first 40 MARKET_DATA frames of the 07:00Z 1h window (`cpc-btc-updown-1h-2026-10-17-0700z`)
- `boundary_0745z.jsonl`: the last 3 frames of the 07:30Z 15m window (OPEN→CLOSED→EXPIRED) and the first 5 of the 07:45Z window
- `trades.jsonl`: the first 8 TRADE frames

**Test fixtures only.** They must never be shown as live data. No credentials appear in frames.
