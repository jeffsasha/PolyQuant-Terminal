from __future__ import annotations

import logging
import re
from decimal import Decimal
from pathlib import Path

import pytest
import respx

from polyquant.clock import FakeClock
from polyquant.domain.timeutil import to_unix
from polyquant.marketdata.bbo import BBOService
from polyquant.marketdata.discovery import InstrumentRegistry
from polyquant.marketdata.quality import DataHealth
from polyquant.marketdata.reference import ReferenceService
from polyquant.venue.gateway import GatewayClient
from polyquant.venue.parsing import parse_instrument
from tests.conftest import load, utc

BASE = "https://gateway.polymarket.us"


async def _no_sleep(_s):
    return None


def gw() -> GatewayClient:
    return GatewayClient(max_rps=1000, sleep=_no_sleep)


def candles(start: int, values: list[str | None], tick=60) -> dict:
    return {"series": [{"asset": {"assetClass": "ASSET_CLASS_CRYPTO", "symbol": "btc"}, "currency": "USD",
                        "candles": [{"timestamp": start + i, "open": v, "high": v, "low": v, "close": v,
                                     "tickCount": tick} for i, v in enumerate(values) if v is not None]}]}


# ---- reference poller ----------------------------------------------------------------------------


async def test_reference_poll_gap_and_revision(sink):
    clock = FakeClock(utc(2026, 10, 17, 6, 0, 10))
    health = DataHealth(sink)
    svc = ReferenceService(gw(), sink, clock, health.register("index", 5), warmup_s=5)
    end = to_unix(clock.now()) - 1
    start = end - 5
    with respx.mock() as router:
        route = router.get(f"{BASE}/v1/asset-prices/history")
        route.respond(200, json=candles(start, ["1.00", None, "1.02", "1.03", "1.04", "1.05"]))
        pts = await svc.poll_once()
        assert [str(p.value) for p in pts] == ["1.00", "1.02", "1.03", "1.04", "1.05"]
        assert route.calls[0].request.url.params["from"] == str(start)
        kinds = [k for _, k, _, _ in sink.quality]
        assert "index_gap" in kinds
        # next poll continues after the newest point; a re-sent different value is reported, not applied
        clock.advance(2)
        route.respond(200, json=candles(end - 1, ["9.99", "1.05", "1.06", "1.07"]))
        await svc.poll_once()
    assert svc.value_at(utc(2026, 10, 17, 6, 0, 8)) == Decimal("1.04")
    assert svc.latest().value == Decimal("1.07")
    health.evaluate(clock.now())
    assert not health.is_stale("index")


async def test_reference_unexpected_tick_count(sink):
    clock = FakeClock(utc(2026, 10, 17, 6, 0, 10))
    svc = ReferenceService(gw(), sink, clock, DataHealth(sink).register("index", 5), warmup_s=2)
    with respx.mock() as router:
        router.get(f"{BASE}/v1/asset-prices/history").respond(
            200, json=candles(to_unix(clock.now()) - 3, ["1.00", "1.01"], tick=59))
        await svc.poll_once()
    assert any(k == "unexpected_tick_count" for _, k, _, _ in sink.quality)


async def test_reference_resume_backfills_from_last_recorded(sink):
    clock = FakeClock(utc(2026, 10, 17, 6, 0, 0))
    svc = ReferenceService(gw(), sink, clock, DataHealth(sink).register("index", 5), warmup_s=10)
    svc.resume_from(utc(2026, 10, 17, 5, 50, 0))
    with respx.mock() as router:
        route = router.get(f"{BASE}/v1/asset-prices/history").respond(200, json=candles(0, []))
        await svc.poll_once()
    assert route.calls[0].request.url.params["from"] == str(to_unix(utc(2026, 10, 17, 5, 49, 50)))


# ---- staleness -----------------------------------------------------------------------------------


def test_stale_transitions_emit_events(sink):
    clock = FakeClock(utc(2026, 10, 17, 6))
    h = DataHealth(sink)
    f = h.register("index", 5)
    h.evaluate(clock.now())
    assert h.is_stale("index")  # never updated → stale
    f.mark(clock.now())
    h.evaluate(clock.now())
    assert not h.is_stale("index")
    clock.advance(5.5)
    h.evaluate(clock.now())
    assert h.is_stale("index")
    assert [k for _, k, _, _ in sink.quality] == ["fresh", "stale"]
    assert h.is_stale("unknown-feed")


# ---- BBO poller ----------------------------------------------------------------------------------


async def test_bbo_polls_only_open_instruments_and_detects_crossed(sink):
    clock = FakeClock(utc(2026, 10, 17, 5, 41))
    reg = InstrumentRegistry(sink, clock)
    open_inst = parse_instrument(load("market_15m_open.json"))
    reg.upsert(open_inst)
    reg.upsert(parse_instrument(load("market_15m_upcoming.json")))
    health = DataHealth(sink)
    svc = BBOService(gw(), reg, sink, clock, health, stale_after_s=10)
    assert svc.targets(clock.now()) == [open_inst.slug]
    raw = load("bbo_15m_open.json")
    raw["marketData"]["bestBid"] = {"value": "0.20", "currency": "USD"}
    with respx.mock() as router:
        router.get(f"{BASE}/v1/markets/{open_inst.slug}/bbo").respond(200, json={
            "marketData": {k: (str(v) if isinstance(v, Decimal) else v) for k, v in raw["marketData"].items()}})
        snap = await svc.poll_next()
    assert snap.crossed
    assert any(k == "crossed_book" for _, k, _, _ in sink.quality)
    assert svc.latest(open_inst.slug) is snap
    # after the window ends the instrument is no longer a target and its feed is dropped
    clock.set(open_inst.window_end)
    assert svc.targets(clock.now()) == []
    await svc.poll_next()
    assert f"bbo:{open_inst.slug}" not in health.feeds


# ---- paper/live isolation and secrets ------------------------------------------------------------

PKG = Path(__file__).resolve().parents[2] / "services" / "engine" / "polyquant"


def test_live_trading_constant_is_false_and_not_env_controlled(monkeypatch):
    monkeypatch.setenv("LIVE_TRADING_ENABLED", "true")
    import importlib

    import polyquant.config as cfg

    importlib.reload(cfg)
    assert cfg.LIVE_TRADING_ENABLED is False
    assert "live_trading_enabled" not in cfg.Settings.model_fields


async def test_live_execution_engine_refuses_everything():
    from polyquant.execution.live import LiveExecutionEngine, LiveTradingDisabled

    eng = LiveExecutionEngine()
    with pytest.raises(LiveTradingDisabled):
        await eng.submit({"marketSlug": "x"})
    with pytest.raises(LiveTradingDisabled):
        await eng.cancel("id")


def test_no_order_endpoints_in_package():
    offenders = []
    pattern = re.compile(r"/v1/orders|\.orders\.|orders\.create|create_order|close_position")
    for py in PKG.rglob("*.py"):
        if py.name == "live.py":
            continue
        for n, line in enumerate(py.read_text().splitlines(), 1):
            if pattern.search(line):
                offenders.append(f"{py.relative_to(PKG)}:{n}: {line.strip()}")
    assert not offenders, offenders


def test_secrets_are_redacted_in_logs(caplog):
    import base64

    from polyquant.logsetup import RedactingFilter

    secret = base64.b64encode(bytes(range(32))).decode()  # 44-char base64, the shape of an Ed25519 key
    key_id = "1b4e28ba-2fa1-11d2-883f-0016d3cca427"
    f = RedactingFilter([key_id])
    rec = logging.LogRecord("t", logging.INFO, __file__, 1, "key=%s secret=%s", (key_id, secret), None)
    f.filter(rec)
    msg = rec.getMessage()
    assert key_id not in msg and secret not in msg and msg.count("<redacted>") == 2


def test_settings_mask_secret(monkeypatch):
    monkeypatch.setenv("POLYMARKET_US_SECRET_KEY", "super-secret-value-123")
    from polyquant.config import Settings

    s = Settings(_env_file=None)
    assert "super-secret-value-123" not in repr(s)
    assert s.polymarket_us_secret_key.get_secret_value() == "super-secret-value-123"



async def test_reference_single_second_poll_respects_from_before_to(sink):
    """Regression (found in live smoke run): the venue returns HTTP 400 'from must be before to' when from == to."""
    clock = FakeClock(utc(2026, 10, 17, 6, 0, 10))
    svc = ReferenceService(gw(), sink, clock, DataHealth(sink).register("index", 5), warmup_s=3)

    def venue(request):
        f, t = int(request.url.params["from"]), int(request.url.params["to"])
        if f >= t:
            return respx.MockResponse(400, json={"code": 3, "message": "from must be before to"})
        # value is a pure function of the timestamp, like the real (immutable) series
        return respx.MockResponse(200, json=candles(f, [f"{ts % 1000}.00" for ts in range(f, t + 1)]))

    with respx.mock() as router:
        router.get(f"{BASE}/v1/asset-prices/history").mock(side_effect=venue)
        await svc.poll_once()
        for _ in range(5):  # one new second per poll: from would equal to without the fix
            clock.advance(1)
            assert await svc.poll_once(), "poll returned no new point"
    assert svc._health.errors == 0
    assert not any(k == "index_revision" for _, k, _, _ in sink.quality)
