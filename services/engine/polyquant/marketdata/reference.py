"""Poller and in-memory buffer for the venue's official 1s reference series (60s-average BRTI)."""

from __future__ import annotations

import logging
from collections import OrderedDict
from datetime import datetime, timedelta
from decimal import Decimal

from polyquant.clock import Clock
from polyquant.domain.models import IndexPoint
from polyquant.domain.timeutil import to_unix
from polyquant.interfaces import EventSink
from polyquant.marketdata.quality import FeedHealth
from polyquant.venue.gateway import GatewayClient, GatewayError
from polyquant.venue.parsing import ParseError, parse_index_points

log = logging.getLogger(__name__)

MAX_CANDLES_PER_CALL = 3600  # documented response cap
EXPECTED_TICK_COUNT = 60
ONE_S = timedelta(seconds=1)


class IndexBuffer:
    """Ordered ts -> IndexPoint. First value wins; any later different value is reported, never applied."""

    def __init__(self, capacity: int = 6 * 3600) -> None:
        self._points: OrderedDict[datetime, IndexPoint] = OrderedDict()
        self._capacity = capacity

    def add(self, p: IndexPoint) -> tuple[bool, IndexPoint | None]:
        """Returns (inserted, conflicting_existing_point)."""
        existing = self._points.get(p.ts)
        if existing is not None:
            return False, (existing if existing.value != p.value else None)
        if self._points and p.ts < next(reversed(self._points)):
            # out-of-order (backfill): insert and re-sort
            self._points[p.ts] = p
            self._points = OrderedDict(sorted(self._points.items()))
        else:
            self._points[p.ts] = p
        while len(self._points) > self._capacity:
            self._points.popitem(last=False)
        return True, None

    def latest(self) -> IndexPoint | None:
        return self._points[next(reversed(self._points))] if self._points else None

    def value_at(self, ts: datetime) -> Decimal | None:
        p = self._points.get(ts)
        return None if p is None else p.value

    def window(self, start: datetime, end: datetime) -> list[IndexPoint]:
        return [p for ts, p in self._points.items() if start <= ts <= end]

    def __len__(self) -> int:
        return len(self._points)


class ReferenceService:
    """Implements ReferencePriceProvider over the public /v1/asset-prices/history endpoint."""

    def __init__(self, gateway: GatewayClient, sink: EventSink, clock: Clock, health: FeedHealth, *,
                 asset: str = "btc", warmup_s: int = 900, settle_lag_s: int = 1) -> None:
        self._gw = gateway
        self._sink = sink
        self._clock = clock
        self._health = health
        self.asset = asset
        self.buffer = IndexBuffer()
        self._warmup = warmup_s
        # Only request fully elapsed seconds, so an in-progress bucket is never recorded as final.
        self._settle_lag = settle_lag_s
        self._resume_from: datetime | None = None
        self.max_backfill_s = 6 * 3600

    def resume_from(self, ts: datetime | None) -> None:
        """After a restart, continue from the last recorded point so downtime is backfilled."""
        self._resume_from = ts

    def latest(self) -> IndexPoint | None:
        return self.buffer.latest()

    def value_at(self, ts: datetime) -> Decimal | None:
        return self.buffer.value_at(ts)

    def is_stale(self, now: datetime) -> bool:
        return self._health.evaluate(now)

    async def poll_once(self) -> list[IndexPoint]:
        now = self._clock.now()
        end = to_unix(now) - self._settle_lag
        last = self.buffer.latest()
        if last:
            start = to_unix(last.ts) + 1
        elif self._resume_from is not None:
            start = max(to_unix(self._resume_from) - self._warmup, end - self.max_backfill_s)
        else:
            start = end - self._warmup
        if start > end:
            return []
        new: list[IndexPoint] = []
        while start <= end:
            chunk_end = min(end, start + MAX_CANDLES_PER_CALL - 1)
            # The venue requires from < to (both inclusive). For a single new second, re-request the previous
            # one too; the buffer de-duplicates it and the overlap doubles as a revision check.
            req_start = min(start, chunk_end - 1)
            try:
                resp = await self._gw.index_history(self.asset, req_start, chunk_end)
                if not resp.ok:
                    raise GatewayError(f"index HTTP {resp.status}: {resp.data}", resp.status)
                points = parse_index_points(resp.data, asset=self.asset, recv_at=resp.recv_at)
            except (GatewayError, ParseError) as exc:
                self._health.error(str(exc))
                log.warning("index poll failed: %s", exc)
                break
            new.extend(self._ingest(points, start, chunk_end, resp.recv_at))
            start = chunk_end + 1
        if new:
            self._sink.index_points(new)
            newest = new[-1]
            # Observed age of the newest point at receipt (venue publish delay + network).
            self._health.mark(newest.recv_at, newest.ts,
                              (newest.recv_at - newest.ts).total_seconds() * 1000)
        return new

    def _ingest(self, points: list[IndexPoint], start: int, end: int, recv_at: datetime) -> list[IndexPoint]:
        inserted: list[IndexPoint] = []
        for p in points:
            ok, conflict = self.buffer.add(p)
            if conflict is not None:
                self._sink.quality_event("index", "index_revision",
                                         {"ts": p.ts.isoformat(), "kept": str(conflict.value),
                                          "incoming": str(p.value)}, recv_at)
            if ok:
                inserted.append(p)
                if p.tick_count != EXPECTED_TICK_COUNT:
                    self._sink.quality_event("index", "unexpected_tick_count",
                                             {"ts": p.ts.isoformat(), "tick_count": p.tick_count}, recv_at)
        got = {to_unix(p.ts) for p in points}
        missing = [t for t in range(start, end + 1) if t not in got]
        # The newest second or two may not be published yet; only report holes followed by later data.
        if points:
            newest = max(got)
            holes = [t for t in missing if t < newest]
            if holes:
                self._sink.quality_event("index", "index_gap",
                                         {"from": holes[0], "to": holes[-1], "count": len(holes)}, recv_at)
        return inserted
