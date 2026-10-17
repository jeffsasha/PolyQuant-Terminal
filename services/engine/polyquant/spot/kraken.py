"""Kraken BTC/USD public trades → 1-second bars (Strategy A's external spot feature).

Same source for history (REST /0/public/Trades) and live (WebSocket v2 `trade` channel), so the feature behaves the
same in calibration and in live use. Read-only, allow-listed hosts, GET only for REST, subscribe-only for WS.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import httpx
import websockets

from polyquant.domain.timeutil import parse_utc
from polyquant.venue.ratelimit import RateLimiter
from polyquant.venue.ws_markets import tls_context

log = logging.getLogger(__name__)

SOURCE = "kraken"
REST_HOST = "api.kraken.com"
WS_URL = "wss://ws.kraken.com/v2"
PAIR_REST = "XBTUSD"
SYMBOL_WS = "BTC/USD"


class ForbiddenSpotRequest(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Trade:
    ts: datetime
    price: Decimal
    qty: Decimal
    trade_id: int | None


@dataclass(frozen=True, slots=True)
class SpotBar:
    source: str
    ts: datetime  # second start
    last_px: Decimal
    first_px: Decimal
    high_px: Decimal
    low_px: Decimal
    n_trades: int
    volume: Decimal
    recv_at: datetime


def aggregate(trades: list[Trade], recv_at: datetime, source: str = SOURCE) -> list[SpotBar]:
    """Group trades by whole second (trade time). Input order is preserved within a second (last = latest)."""
    bars: dict[int, list[Trade]] = {}
    for t in trades:
        bars.setdefault(int(t.ts.timestamp()), []).append(t)
    out = []
    for sec in sorted(bars):
        ts = bars[sec]
        prices = [t.price for t in ts]
        out.append(SpotBar(source, datetime.fromtimestamp(sec, UTC), prices[-1], prices[0], max(prices), min(prices),
                           len(ts), sum((t.qty for t in ts), Decimal(0)), recv_at))
    return out


class KrakenRest:
    def __init__(self, *, rps: float = 0.9, transport: httpx.AsyncBaseTransport | None = None,
                 sleep=asyncio.sleep) -> None:
        self._http = httpx.AsyncClient(base_url=f"https://{REST_HOST}", timeout=20, transport=transport,
                                       headers={"User-Agent": "polyquant/0.1 (research)"})
        self._limiter = RateLimiter(rps)
        self._sleep = sleep

    async def aclose(self) -> None:
        await self._http.aclose()

    async def get(self, path: str, params: dict) -> dict:
        req = self._http.build_request("GET", path, params=params)
        if req.method != "GET" or req.url.host != REST_HOST:
            raise ForbiddenSpotRequest(f"{req.method} {req.url}")
        backoff = 2.0
        for _ in range(6):
            await self._limiter.acquire()
            try:
                r = await self._http.send(req)
                data = r.json()
            except (httpx.HTTPError, ValueError) as exc:
                log.warning("kraken %s failed: %s", path, exc)
                await self._sleep(backoff)
                backoff = min(backoff * 2, 60)
                continue
            errs = data.get("error") or []
            if r.status_code == 429 or any("Too many requests" in e or "EAPI:Rate limit" in e for e in errs):
                self._limiter.penalize(backoff)
                await self._sleep(backoff)
                backoff = min(backoff * 2, 60)
                continue
            if errs:
                raise RuntimeError(f"kraken error {errs}")
            return data["result"]
        raise RuntimeError(f"kraken {path}: giving up after retries")

    async def trades_since(self, since_ns: int) -> tuple[list[Trade], int]:
        res = await self.get("/0/public/Trades", {"pair": PAIR_REST, "since": str(since_ns), "count": 1000})
        last = int(res.pop("last"))
        rows = next(iter(res.values()), [])
        trades = [Trade(datetime.fromtimestamp(float(r[2]), UTC), Decimal(r[0]), Decimal(r[1]),
                        int(r[6]) if len(r) > 6 else None) for r in rows]
        return trades, last


async def backfill(rest: KrakenRest, sink_bars: Callable[[list[SpotBar]], None], *, since: datetime,
                   until: datetime, flush: Callable[[], object] | None = None) -> int:
    """Page through trade history; emit only complete seconds (the boundary second is re-fetched next page)."""
    cursor = int(since.timestamp() * 1e9)
    end_ns = int(until.timestamp() * 1e9)
    total = 0
    pending: list[Trade] = []
    while cursor < end_ns:
        trades, last = await rest.trades_since(cursor)
        if not trades or last <= cursor:
            break
        pending.extend(t for t in trades if t.ts.timestamp() * 1e9 < end_ns)
        if pending:
            boundary = int(pending[-1].ts.timestamp())
            done = [t for t in pending if int(t.ts.timestamp()) < boundary]
            pending = [t for t in pending if int(t.ts.timestamp()) >= boundary]
            bars = aggregate(done, datetime.now(UTC))
            if bars:
                sink_bars(bars)
                total += len(bars)
        cursor = last
        if flush is not None and total and total % 20000 < 1000:
            await flush()
            log.info("kraken backfill through %s (%d bars)", datetime.fromtimestamp(cursor / 1e9, UTC), total)
    if pending:
        sink_bars(aggregate(pending, datetime.now(UTC)))
    return total


class KrakenTradeStream:
    """Live trades → 1 s bars. A second is emitted once a later second's trade arrives or 2 s have passed."""

    def __init__(self, on_bars: Callable[[list[SpotBar]], None], on_event: Callable[[str, dict], None], clock,
                 connect=websockets.connect, idle_timeout_s: float = 60.0) -> None:
        self._on_bars = on_bars
        self._on_event = on_event
        self._clock = clock
        self._connect = connect
        self._idle = idle_timeout_s
        self._open: dict[int, list[Trade]] = {}
        self.connected = False
        self.last_trade_at: datetime | None = None
        self.trades = 0

    def _flush(self, before_sec: int) -> None:
        ready = sorted(s for s in self._open if s < before_sec)
        if not ready:
            return
        trades = [t for s in ready for t in self._open.pop(s)]
        self._on_bars(aggregate(trades, self._clock.now()))

    def handle(self, msg: dict) -> None:
        if msg.get("channel") != "trade" or msg.get("type") not in ("update", "snapshot"):
            return
        for d in msg.get("data") or []:
            try:
                t = Trade(parse_utc(d["timestamp"]), Decimal(str(d["price"])), Decimal(str(d["qty"])),
                          d.get("trade_id"))
            except (KeyError, ValueError, ArithmeticError):
                self._on_event("bad_trade", {"sample": str(d)[:120]})
                continue
            if msg.get("type") == "snapshot":
                continue  # historical snapshot on subscribe: backfill covers history, avoid mixing
            self._open.setdefault(int(t.ts.timestamp()), []).append(t)
            self.trades += 1
            self.last_trade_at = t.ts
            self._flush(int(t.ts.timestamp()))

    def tick(self) -> None:
        self._flush(int(self._clock.now().timestamp()) - 2)

    async def run(self, stop: asyncio.Event) -> None:
        backoff = 1.0
        while not stop.is_set():
            try:
                async with self._connect(WS_URL, ssl=tls_context(), ping_interval=20, ping_timeout=20,
                                         open_timeout=15) as ws:
                    self.connected = True
                    self._on_event("connected", {})
                    await ws.send(json.dumps({"method": "subscribe",
                                              "params": {"channel": "trade", "symbol": [SYMBOL_WS]}}))
                    backoff = 1.0
                    while not stop.is_set():
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=self._idle)
                        except TimeoutError:
                            self._on_event("idle_reconnect", {})
                            break
                        self.handle(json.loads(raw))
                        self.tick()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._on_event("error", {"error": f"{type(exc).__name__}: {exc}"})
            finally:
                if self.connected:
                    self._on_event("disconnected", {})
                self.connected = False
            if stop.is_set():
                break
            try:
                await asyncio.wait_for(stop.wait(), timeout=backoff + random.uniform(0, backoff / 2))  # noqa: S311
            except TimeoutError:
                pass
            backoff = min(backoff * 2, 60)
