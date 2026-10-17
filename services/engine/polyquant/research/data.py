"""Loads recorded research data from PostgreSQL."""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal

import asyncpg
import numpy as np

from polyquant.domain.models import Horizon, Instrument, Outcome, Source
from polyquant.marketdata.book import BookSnapshot, Level


def _inst(r) -> Instrument:
    return Instrument(
        slug=r["slug"], market_id=r["market_id"], event_slug=r["event_slug"], asset=r["asset"],
        horizon=Horizon(r["horizon"]), index_symbol=r["index_symbol"], window_start=r["window_start"],
        window_end=r["window_end"], status=r["status"], price_to_beat=r["price_to_beat"],
        settlement_price=r["settlement_price"], fee_coefficient=r["fee_coefficient"], tick_size=r["tick_size"],
        min_qty=r["min_qty"], up_side_label=r["up_side_label"], down_side_label=r["down_side_label"],
        description=r["description"], source=Source(r["source"]),
        venue_outcome=Outcome(r["venue_outcome"]) if r["venue_outcome"] else None)


async def load_instruments(pool: asyncpg.Pool, *, asset: str = "btc",
                           until: datetime | None = None) -> list[Instrument]:
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM instruments WHERE asset=$1 AND ($2::timestamptz IS NULL OR "
                                "window_end <= $2) ORDER BY window_start", asset, until)
    return [_inst(r) for r in rows]


async def load_index(pool: asyncpg.Pool, *, asset: str = "btc", start: datetime | None = None,
                     end: datetime | None = None) -> tuple[np.ndarray, np.ndarray]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT extract(epoch from ts)::bigint AS t, value FROM index_points WHERE asset=$1"
            " AND ($2::timestamptz IS NULL OR ts >= $2) AND ($3::timestamptz IS NULL OR ts <= $3) ORDER BY ts",
            asset, start, end)
    ts = np.fromiter((r["t"] for r in rows), dtype=np.int64, count=len(rows))
    vals = np.fromiter((float(r["value"]) for r in rows), dtype=np.float64, count=len(rows))
    return ts, vals


async def load_books(pool: asyncpg.Pool, slug: str) -> list[BookSnapshot]:
    """Recorded WS book states for one instrument, in receive order (the order the live system saw them)."""
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT transact_time, recv_at, state, bids, offers, n_bids, n_offers"
                                " FROM book_snapshots WHERE slug=$1 ORDER BY recv_at, id", slug)
    out = []
    for r in rows:
        bids = tuple(Level(Decimal(p), Decimal(q)) for p, q in json.loads(r["bids"]))
        offers = tuple(Level(Decimal(p), Decimal(q)) for p, q in json.loads(r["offers"]))
        if len(bids) != r["n_bids"] or len(offers) != r["n_offers"]:
            raise ValueError(f"{slug}: recorded book was depth-capped; replay needs full depth (BOOK_RECORD_LEVELS=0)")
        out.append(BookSnapshot(slug=slug, bids=bids, offers=offers, state=r["state"],
                                transact_time=r["transact_time"], recv_at=r["recv_at"]))
    return out


async def book_coverage(pool: asyncpg.Pool) -> list[dict]:
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT slug, min(recv_at) first, max(recv_at) last, count(*) n FROM book_snapshots"
                                " GROUP BY slug ORDER BY min(recv_at)")
    return [dict(r) for r in rows]


async def load_spot(pool: asyncpg.Pool, *, source: str = "kraken", start: datetime | None = None,
                    end: datetime | None = None) -> tuple[np.ndarray, np.ndarray]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT extract(epoch from ts)::bigint AS t, last_px FROM external_spot WHERE source=$1"
            " AND ($2::timestamptz IS NULL OR ts >= $2) AND ($3::timestamptz IS NULL OR ts <= $3) ORDER BY ts",
            source, start, end)
    ts = np.fromiter((r["t"] for r in rows), dtype=np.int64, count=len(rows))
    vals = np.fromiter((float(r["last_px"]) for r in rows), dtype=np.float64, count=len(rows))
    return ts, vals
