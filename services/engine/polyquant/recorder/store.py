"""Postgres recorder. Implements EventSink without blocking producers: events go to a bounded queue that a
single writer task drains in order, one transaction per batch, retrying on database errors."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

import asyncpg

from polyquant.clock import Clock, SystemClock
from polyquant.domain.models import BBOSnapshot, IndexPoint, Instrument, TradePrint

log = logging.getLogger(__name__)


def _json_default(o: Any) -> Any:
    if isinstance(o, Decimal | datetime | Enum):
        return str(o) if not isinstance(o, datetime) else o.isoformat()
    raise TypeError(f"not JSON serialisable: {type(o).__name__}")


def dumps(o: Any) -> str:
    return json.dumps(o, default=_json_default, separators=(",", ":"))


UPSERT_INSTRUMENT = """
INSERT INTO instruments (slug, market_id, event_slug, asset, horizon, index_symbol, window_start, window_end,
    status, price_to_beat, settlement_price, fee_coefficient, tick_size, min_qty, up_side_label, down_side_label,
    description, source, first_seen_at, updated_at, venue_outcome)
VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$19,$20)
ON CONFLICT (slug) DO UPDATE SET
    status = EXCLUDED.status,
    venue_outcome = COALESCE(instruments.venue_outcome, EXCLUDED.venue_outcome),
    price_to_beat = COALESCE(instruments.price_to_beat, EXCLUDED.price_to_beat),
    settlement_price = COALESCE(instruments.settlement_price, EXCLUDED.settlement_price),
    fee_coefficient = EXCLUDED.fee_coefficient,
    window_start = EXCLUDED.window_start,
    window_end = EXCLUDED.window_end,
    updated_at = EXCLUDED.updated_at
"""

INSERT_INDEX = """
WITH incoming AS (
    SELECT * FROM unnest($1::text[], $2::timestamptz[], $3::numeric[], $4::int[], $5::timestamptz[], $6::text[])
        AS t(asset, ts, value, tick_count, recv_at, source)
), ins AS (
    INSERT INTO index_points (asset, ts, value, tick_count, recv_at, source)
    SELECT asset, ts, value, tick_count, recv_at, source FROM incoming
    ON CONFLICT (asset, ts) DO NOTHING
    RETURNING 1
)
SELECT i.ts, i.value AS incoming, p.value AS existing, (SELECT count(*) FROM ins) AS inserted
FROM incoming i JOIN index_points p USING (asset, ts)
WHERE p.value <> i.value
"""

INSERT_BBO = """
INSERT INTO bbo_snapshots (slug, sent_at, recv_at, best_bid, best_ask, bid_depth, ask_depth, bid_shares, ask_shares,
    last_trade_px, current_px, shares_traded, open_interest, state, last_trade_ts, source, raw, data_as_of,
    cache_status, cache_age_s)
VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20)
"""

INSERT_BOOK = """
INSERT INTO book_snapshots (slug, transact_time, recv_at, state, best_bid, best_ask, n_bids, n_offers, bids, offers,
    source)
VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
"""

INSERT_TRADE = """
INSERT INTO trades (trade_id, slug, trade_time, recv_at, price, quantity, quantity_unit, maker_side, taker_side, source,
    raw)
VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
ON CONFLICT (trade_id) DO NOTHING
"""

INSERT_SPOT = """
INSERT INTO external_spot (source, ts, last_px, first_px, high_px, low_px, n_trades, volume, recv_at)
SELECT * FROM unnest($1::text[], $2::timestamptz[], $3::numeric[], $4::numeric[], $5::numeric[], $6::numeric[],
                     $7::int[], $8::numeric[], $9::timestamptz[])
ON CONFLICT (source, ts) DO NOTHING
"""

INSERT_QUALITY = "INSERT INTO data_quality_events (at, feed, kind, detail) VALUES ($1, $2, $3, $4)"


class RecorderSink:
    def __init__(self, pool: asyncpg.Pool, *, clock: Clock | None = None, max_queue: int = 50_000,
                 batch_size: int = 500, book_levels: int = 0) -> None:
        self._pool = pool
        self._clock = clock or SystemClock()
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue)
        self._batch_size = batch_size
        self._book_levels = book_levels or None  # None = record full depth
        self.dropped = 0
        self.written = 0
        self.write_errors = 0
        self._task: asyncio.Task | None = None
        self._stopping = False

    # ---- EventSink (non-blocking) ----------------------------------------------------------------

    def _put(self, item: tuple) -> None:
        try:
            self._queue.put_nowait(item)
        except asyncio.QueueFull:
            self.dropped += 1

    def instrument_changed(self, inst: Instrument, changes: dict, observed_at: datetime) -> None:
        self._put(("instrument", inst, changes, observed_at))

    def index_points(self, points: list[IndexPoint]) -> None:
        if points:
            self._put(("index", list(points)))

    def bbo(self, snap: BBOSnapshot) -> None:
        self._put(("bbo", snap))

    def book(self, snap) -> None:
        self._put(("book", snap))

    def trade(self, trade: TradePrint) -> None:
        self._put(("trade", trade))

    def spot_bars(self, bars: list) -> None:
        if bars:
            self._put(("spot", list(bars)))

    def quality_event(self, feed: str, kind: str, detail: dict, at: datetime) -> None:
        self._put(("quality", at, feed, kind, detail))

    # ---- writer ----------------------------------------------------------------------------------

    def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="recorder-writer")

    async def stop(self, timeout_s: float = 10.0) -> None:
        self._stopping = True
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout_s)
            except TimeoutError:
                self._task.cancel()
                log.error("recorder stop timed out with %d queued events unwritten", self._queue.qsize())

    @property
    def queued(self) -> int:
        return self._queue.qsize()

    async def flush(self) -> None:
        """Write everything currently queued (used by tests and shutdown)."""
        while not self._queue.empty():
            await self._write(self._drain())

    def _drain(self) -> list[tuple]:
        batch = []
        while len(batch) < self._batch_size:
            try:
                batch.append(self._queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        return batch

    async def _run(self) -> None:
        backoff = 0.5
        pending: list[tuple] = []
        reported_drops = 0
        while True:
            if not pending:
                if self._stopping and self._queue.empty():
                    return
                try:
                    first = await asyncio.wait_for(self._queue.get(), timeout=0.5)
                except TimeoutError:
                    continue
                pending = [first, *self._drain()]
            if self.dropped > reported_drops:
                pending.append(("quality", self._clock.now(), "recorder", "backpressure_drop",
                                {"dropped_total": self.dropped}))
                reported_drops = self.dropped
            try:
                await self._write(pending)
                pending = []
                backoff = 0.5
            except (asyncpg.PostgresError, OSError, asyncpg.InterfaceError) as exc:
                self.write_errors += 1
                log.error("recorder write failed (%s); retrying %d events in %.1fs", exc, len(pending), backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)

    async def _write(self, batch: list[tuple]) -> None:
        if not batch:
            return
        async with self._pool.acquire() as conn, conn.transaction():
            for item in batch:
                kind = item[0]
                if kind == "instrument":
                    await self._write_instrument(conn, *item[1:])
                elif kind == "index":
                    await self._write_index(conn, item[1])
                elif kind == "bbo":
                    await self._write_bbo(conn, item[1])
                elif kind == "book":
                    await self._write_book(conn, item[1])
                elif kind == "trade":
                    await self._write_trade(conn, item[1])
                elif kind == "spot":
                    b = item[1]
                    await conn.execute(INSERT_SPOT, [x.source for x in b], [x.ts for x in b], [x.last_px for x in b],
                                       [x.first_px for x in b], [x.high_px for x in b], [x.low_px for x in b],
                                       [x.n_trades for x in b], [x.volume for x in b], [x.recv_at for x in b])
                elif kind == "quality":
                    _, at, feed, k, detail = item
                    await conn.execute(INSERT_QUALITY, at, feed, k, dumps(detail))
        self.written += len(batch)

    async def _write_instrument(self, conn, inst: Instrument, changes: dict, at: datetime) -> None:
        await conn.execute(UPSERT_INSTRUMENT, inst.slug, inst.market_id, inst.event_slug, inst.asset,
                           inst.horizon.value, inst.index_symbol, inst.window_start, inst.window_end, inst.status,
                           inst.price_to_beat, inst.settlement_price, inst.fee_coefficient, inst.tick_size,
                           inst.min_qty, inst.up_side_label, inst.down_side_label, inst.description,
                           inst.source.value, at, inst.venue_outcome.value if inst.venue_outcome else None)
        if "settlement_flag" in changes:
            await conn.execute("UPDATE instruments SET settlement_flag = $2 WHERE slug = $1 AND settlement_flag "
                               "IS NULL", inst.slug, int(changes["settlement_flag"][1]))
        await conn.execute("INSERT INTO instrument_events (slug, observed_at, changes) VALUES ($1, $2, $3)",
                           inst.slug, at, dumps({k: list(v) if isinstance(v, tuple) else v
                                                 for k, v in changes.items()}))

    async def _write_index(self, conn, points: list[IndexPoint]) -> None:
        rows = await conn.fetch(INSERT_INDEX, [p.asset for p in points], [p.ts for p in points],
                                [p.value for p in points], [p.tick_count for p in points],
                                [p.recv_at for p in points], [p.source.value for p in points])
        for r in rows:
            await conn.execute(INSERT_QUALITY, self._clock.now(), "index", "index_revision_db",
                               dumps({"ts": r["ts"], "existing": r["existing"], "incoming": r["incoming"]}))

    async def _write_bbo(self, conn, s: BBOSnapshot) -> None:
        await conn.execute(INSERT_BBO, s.slug, s.sent_at, s.recv_at, s.best_bid, s.best_ask, s.bid_depth,
                           s.ask_depth, s.bid_shares, s.ask_shares, s.last_trade_px, s.current_px,
                           s.shares_traded, s.open_interest, s.state, s.last_trade_ts, s.source.value,
                           dumps(s.raw), s.data_as_of, s.cache_status, s.cache_age_s)

    async def _write_book(self, conn, b) -> None:
        await conn.execute(INSERT_BOOK, b.slug, b.transact_time, b.recv_at, b.state, b.best_bid, b.best_ask,
                           len(b.bids), len(b.offers),
                           dumps([[str(lv.px), str(lv.qty)] for lv in b.bids[: self._book_levels]]),
                           dumps([[str(lv.px), str(lv.qty)] for lv in b.offers[: self._book_levels]]), b.source.value)

    async def _write_trade(self, conn, t: TradePrint) -> None:
        await conn.execute(INSERT_TRADE, t.trade_id, t.slug, t.trade_time, t.recv_at, t.price, t.quantity,
                           t.quantity_unit, t.maker_side, t.taker_side, t.source.value, dumps(t.raw))


async def latest_index_ts(pool: asyncpg.Pool, asset: str) -> datetime | None:
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT max(ts) FROM index_points WHERE asset = $1", asset)


async def counts(pool: asyncpg.Pool) -> dict[str, int]:
    out = {}
    async with pool.acquire() as conn:
        for t in ("instruments", "instrument_events", "index_points", "bbo_snapshots", "book_snapshots", "trades",
                  "external_spot", "data_quality_events"):
            out[t] = await conn.fetchval(f"SELECT count(*) FROM {t}")  # noqa: S608 - fixed table names
    return out
