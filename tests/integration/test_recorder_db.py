"""Recorder against a real PostgreSQL (POLYQUANT_TEST_DATABASE_URL). Includes restart recovery."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from polyquant.domain.models import IndexPoint
from polyquant.marketdata.discovery import InstrumentRegistry
from polyquant.recorder.db import migrate
from polyquant.recorder.store import RecorderSink, counts, latest_index_ts
from polyquant.venue.parsing import parse_bbo, parse_index_points, parse_instrument
from tests.conftest import load, utc

pytestmark = pytest.mark.db


async def test_migrations_are_idempotent(pool):
    async with pool.acquire() as conn:
        assert await migrate(conn) == []


async def test_full_write_path(pool, clock):
    rec = RecorderSink(pool, clock=clock)
    reg = InstrumentRegistry(rec, clock)
    inst = parse_instrument(load("market_15m_open.json"))
    reg.upsert(inst)
    rec.index_points(parse_index_points(load("brti_1s_before_0500z.json"), asset="btc", recv_at=clock.now()))
    rec.bbo(parse_bbo(load("bbo_15m_open.json"), sent_at=clock.now(), recv_at=clock.now()))
    rec.quality_event("index", "stale", {"age_s": Decimal("6.1")}, clock.now())
    await rec.flush()
    c = await counts(pool)
    assert c == {"instruments": 1, "instrument_events": 1, "index_points": 60, "bbo_snapshots": 1,
                 "book_snapshots": 0, "trades": 0, "external_spot": 0, "data_quality_events": 1}
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT price_to_beat, fee_coefficient, horizon FROM instruments")
        assert row["price_to_beat"] == Decimal("81487.13") and row["horizon"] == "15m"
        bbo = await conn.fetchrow("SELECT best_bid, best_ask, last_trade_ts, source FROM bbo_snapshots")
        assert bbo["best_bid"] == Decimal("0.14") and bbo["source"] == "gateway"


async def test_index_conflicts_never_overwrite_and_are_logged(pool, clock):
    rec = RecorderSink(pool, clock=clock)
    pts = parse_index_points(load("brti_1s_before_0500z.json"), asset="btc", recv_at=clock.now())
    rec.index_points(pts)
    await rec.flush()
    tampered = [replace(pts[-1], value=pts[-1].value + 1)]
    rec.index_points(pts[:5] + tampered)  # 5 identical re-sends + 1 conflicting value
    await rec.flush()
    async with pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM index_points") == 60
        stored = await conn.fetchval("SELECT value FROM index_points WHERE ts = $1", pts[-1].ts)
        assert stored == pts[-1].value
        kinds = [r["kind"] for r in await conn.fetch("SELECT kind FROM data_quality_events")]
    assert kinds == ["index_revision_db"]


async def test_settlement_lifecycle_is_append_only(pool, clock):
    rec = RecorderSink(pool, clock=clock)
    reg = InstrumentRegistry(rec, clock)
    pending = load("market_15m_resolved_up.json")
    pending["market"]["assetPriceTerms"]["settlementPrice"] = None
    pending["market"]["status"] = "MARKET_STATUS_OPEN"
    reg.upsert(parse_instrument(pending))
    reg.upsert(parse_instrument(load("market_15m_resolved_up.json")))
    rec.instrument_changed(reg.get(pending["market"]["slug"]), {"settlement_flag": (None, 1)}, clock.now())
    await rec.flush()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT status, settlement_price, settlement_flag FROM instruments")
        n_events = await conn.fetchval("SELECT count(*) FROM instrument_events")
    assert row["status"] == "MARKET_STATUS_RESOLVED"
    assert row["settlement_price"] == Decimal("81507.89") and row["settlement_flag"] == 1
    assert n_events == 3  # new, resolved, flag — history kept


async def test_restart_recovery_resumes_from_last_point(pool, clock):
    rec = RecorderSink(pool, clock=clock)
    rec.index_points(parse_index_points(load("brti_1s_before_0515z.json"), asset="btc", recv_at=clock.now()))
    await rec.flush()
    # "restart": a brand-new sink and service read state back from the database only
    from polyquant.marketdata.quality import DataHealth
    from polyquant.marketdata.reference import ReferenceService
    from polyquant.venue.gateway import GatewayClient

    last = await latest_index_ts(pool, "btc")
    assert last == utc(2026, 10, 17, 5, 14, 59)
    svc = ReferenceService(GatewayClient(), RecorderSink(pool, clock=clock), clock,
                           DataHealth(rec).register("index", 5), warmup_s=60)
    svc.resume_from(last)
    assert svc._resume_from == last


async def test_writer_retries_after_db_outage(pool, clock, monkeypatch):
    rec = RecorderSink(pool, clock=clock)
    calls = {"n": 0}
    real = rec._write

    async def flaky(batch):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("connection reset")
        await real(batch)

    monkeypatch.setattr(rec, "_write", flaky)
    rec.start()
    rec.index_points([IndexPoint("btc", utc(2026, 10, 17, 6), Decimal("1"), 60, clock.now())])
    await rec.stop(timeout_s=10)
    assert rec.write_errors == 1
    assert (await counts(pool))["index_points"] == 1


async def test_backpressure_drops_are_counted(pool, clock):
    rec = RecorderSink(pool, clock=clock, max_queue=2)
    for _ in range(5):
        rec.quality_event("x", "y", {}, clock.now())
    assert rec.dropped == 3


def _ws_rows(name):
    import json
    from pathlib import Path

    from polyquant.domain.timeutil import parse_utc

    p = Path(__file__).resolve().parents[1] / "fixtures" / "ws" / name
    return [(json.loads(x, parse_float=Decimal)["frame"], parse_utc(json.loads(x)["recv_at"]))
            for x in p.read_text().splitlines()]


def _instrument_for(slug, template="market_1h_open.json"):
    raw = load(template)
    raw["market"]["slug"] = slug
    return parse_instrument(raw)


async def test_book_snapshots_and_trades_recorded_with_dedupe_and_level_cap(pool, clock):
    from polyquant.marketdata.books import BookService
    from polyquant.marketdata.quality import DataHealth

    rec = RecorderSink(pool, clock=clock, book_levels=5)
    reg = InstrumentRegistry(rec, clock)
    slug_1h = "cpc-btc-updown-1h-2026-10-17-0700z"
    reg.upsert(_instrument_for(slug_1h))
    trades = _ws_rows("trades.jsonl")
    for f, _ in trades:
        s = f["trade"]["marketSlug"]
        if reg.get(s) is None:
            reg.upsert(_instrument_for(s, "market_15m_open.json"))
    svc = BookService(rec, clock, DataHealth(rec))
    svc.track([slug_1h])
    for f, r in _ws_rows("book_1h_sequence.jsonl"):
        svc.on_frame(f, r)
    for f, r in trades + trades[:3]:  # re-sent trades must not duplicate
        svc.on_frame(f, r)
    await rec.flush()
    async with pool.acquire() as conn:
        n_books = await conn.fetchval("SELECT count(*) FROM book_snapshots")
        row = await conn.fetchrow("SELECT n_bids, n_offers, jsonb_array_length(bids) nb, jsonb_array_length(offers) no,"
                                  " best_bid, source FROM book_snapshots ORDER BY id LIMIT 1")
        n_trades = await conn.fetchval("SELECT count(*) FROM trades")
        unit = await conn.fetchval("SELECT DISTINCT quantity_unit FROM trades")
    assert 0 < n_books <= 40
    assert row["n_bids"] == 40 and row["nb"] == 5 and row["no"] == 5  # full counts kept, levels capped
    assert row["best_bid"] == Decimal("0.89") and row["source"] == "ws"
    assert n_trades == 8 and unit == "USD"
