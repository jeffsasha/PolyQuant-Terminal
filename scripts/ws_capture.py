"""Record raw markets-WebSocket frames for the current BTC 15m/1h instruments (read-only research tool).

Usage: .venv/bin/python scripts/ws_capture.py --seconds 300 [--out captures/ws-<utc>.jsonl]

Writes one JSON line per frame: {"recv_at": <local UTC iso>, "frame": <decoded JSON>}. The auth headers are created
by the official SDK and are never printed or written. Output goes to captures/ (git-ignored).
Only market-data subscriptions are sent; nothing here can touch orders or account data.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "engine"))

from polymarket_us.websocket.markets import MarketsWebSocket  # noqa: E402

from polyquant.clock import SystemClock  # noqa: E402
from polyquant.config import Settings  # noqa: E402
from polyquant.domain.models import Horizon  # noqa: E402
from polyquant.interfaces import MemorySink  # noqa: E402
from polyquant.marketdata.discovery import DiscoveryService, InstrumentRegistry  # noqa: E402
from polyquant.marketdata.quality import FeedHealth  # noqa: E402
from polyquant.venue.gateway import GatewayClient  # noqa: E402


async def current_slugs(settings: Settings) -> list[str]:
    clock, sink = SystemClock(), MemorySink()
    reg = InstrumentRegistry(sink, clock)
    async with GatewayClient(max_rps=settings.gateway_max_rps) as gw:
        await DiscoveryService(gw, reg, sink, clock, FeedHealth("d", 180), asset=settings.asset,
                               horizons=settings.horizons, lookahead_s=3600, lookback_s=600).run_once()
    out = []
    for h in Horizon:
        for inst in (reg.current(h), reg.next(h)):
            if inst:
                out.append(inst.slug)
    return out


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=300)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--debounced", action="store_true", help="request responsesDebounced (batched updates)")
    args = ap.parse_args()

    settings = Settings()
    if not settings.has_credentials:
        print("POLYMARKET_US_KEY_ID / POLYMARKET_US_SECRET_KEY not set (.env or environment)", file=sys.stderr)
        return 2
    slugs = await current_slugs(settings)
    print("subscribing to:", slugs)
    out = args.out or ROOT / "captures" / f"ws-{datetime.now(UTC):%Y%m%dT%H%M%SZ}.jsonl"
    out.parent.mkdir(exist_ok=True)

    ws = MarketsWebSocket(key_id=settings.polymarket_us_key_id.get_secret_value(),
                          secret_key=settings.polymarket_us_secret_key.get_secret_value())
    counts: dict[str, int] = {}
    closed = asyncio.Event()

    with out.open("w") as fh:
        def on_message(msg: dict) -> None:
            kind = next((k for k in ("marketData", "marketDataLite", "trade", "heartbeat", "error") if k in msg),
                        "other")
            counts[kind] = counts.get(kind, 0) + 1
            fh.write(json.dumps({"recv_at": datetime.now(UTC).isoformat(), "frame": msg}) + "\n")

        ws.on("message", on_message)
        ws.on("close", lambda *a: closed.set())
        ws.on("error", lambda e: print("ws error:", e, file=sys.stderr))
        await ws.connect()
        for i, sub in enumerate(("SUBSCRIPTION_TYPE_MARKET_DATA", "SUBSCRIPTION_TYPE_TRADE")):
            req = {"subscribe": {"requestId": f"cap-{i}", "subscriptionType": sub, "marketSlugs": slugs}}
            if args.debounced:
                req["subscribe"]["responsesDebounced"] = True
            await ws.send(req)
        try:
            await asyncio.wait_for(closed.wait(), timeout=args.seconds)
            print("server closed the connection early", file=sys.stderr)
        except TimeoutError:
            pass
        await ws.close()
    print(f"wrote {out} frames={counts}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
