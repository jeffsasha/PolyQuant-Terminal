from __future__ import annotations

import copy
from dataclasses import replace
from decimal import Decimal

import respx

from polyquant.clock import FakeClock
from polyquant.domain.models import Horizon, Phase, phase_of
from polyquant.marketdata.discovery import DiscoveryService, InstrumentRefresher, InstrumentRegistry
from polyquant.marketdata.quality import FeedHealth
from polyquant.venue.gateway import GatewayClient
from polyquant.venue.parsing import parse_instrument
from tests.conftest import FIXTURES, load, utc

BASE = "https://gateway.polymarket.us"


async def _no_sleep(_s):
    return None


def gw() -> GatewayClient:
    return GatewayClient(max_rps=1000, sleep=_no_sleep)


def _events_router(router):
    def handler(request):
        closed = request.url.params["closed"]
        name = "events_crypto_open.json" if closed == "false" else "events_crypto_closed_upcoming.json"
        return respx.MockResponse(200, content=(FIXTURES / name).read_bytes())

    router.get(f"{BASE}/v1/events").mock(side_effect=handler)


async def test_discovery_finds_only_btc_15m_and_1h(sink, clock):
    reg = InstrumentRegistry(sink, clock)
    with respx.mock() as router:
        _events_router(router)
        async with gw() as g:
            svc = DiscoveryService(g, reg, sink, clock, FeedHealth("discovery", 180), asset="btc",
                                   horizons=("15m", "1h"), lookahead_s=3 * 3600, lookback_s=7200)
            n = await svc.run_once()
    slugs = [i.slug for i in reg.all()]
    assert n > 0 and slugs
    assert all(s.startswith(("cpc-btc-updown-15m", "cpc-btc-updown-1h")) for s in slugs)
    assert {i.horizon for i in reg.all()} == {Horizon.M15, Horizon.H1}
    # every new instrument produced an append-only instrument event
    assert len([e for e in sink.instrument_events if e[1].get("_new")]) == len(slugs)


async def test_discovery_query_covers_both_closed_states(sink, clock):
    reg = InstrumentRegistry(sink, clock)
    with respx.mock() as router:
        _events_router(router)
        async with gw() as g:
            await DiscoveryService(g, reg, sink, clock, FeedHealth("d", 180), asset="btc", horizons=("15m",),
                                   lookahead_s=3600, lookback_s=3600).run_once()
        seen = {c.request.url.params["closed"] for c in router.calls}
    assert seen == {"true", "false"}


def _reg_with(sink, clock, *names):
    reg = InstrumentRegistry(sink, clock)
    for n in names:
        reg.upsert(parse_instrument(load(n)))
    return reg


def test_rollover_current_and_next(sink):
    clock = FakeClock(utc(2026, 10, 17, 5, 44, 59))
    reg = _reg_with(sink, clock, "market_15m_open.json", "market_15m_upcoming.json", "market_1h_open.json")
    assert reg.current(Horizon.M15).slug.endswith("0530z")
    assert reg.next(Horizon.M15).slug.endswith("0600z")
    assert reg.current(Horizon.H1).slug.endswith("1h-2026-10-17-0500z")
    clock.set(utc(2026, 10, 17, 5, 45, 0))  # boundary: 05:30 window has ended; 05:45 window not in registry
    assert reg.current(Horizon.M15) is None
    clock.set(utc(2026, 10, 17, 6, 0, 0))
    assert reg.current(Horizon.M15).slug.endswith("0600z")


def test_overlapping_windows_are_refused(sink, clock):
    reg = _reg_with(sink, clock, "market_15m_open.json")
    dup = replace(parse_instrument(load("market_15m_open.json")), slug="cpc-btc-updown-15m-duplicate")
    reg.upsert(dup)
    assert reg.current(Horizon.M15) is None
    assert any(k == "overlapping_windows" for _, k, _, _ in sink.quality)


def test_upsert_never_erases_official_values(sink, clock):
    reg = _reg_with(sink, clock, "market_15m_open.json")
    stale = replace(parse_instrument(load("market_15m_open.json")), price_to_beat=None)
    reg.upsert(stale)
    assert reg.get(stale.slug).price_to_beat == Decimal("81487.13")


def test_changed_price_to_beat_is_flagged(sink, clock):
    reg = _reg_with(sink, clock, "market_15m_open.json")
    reg.upsert(replace(parse_instrument(load("market_15m_open.json")), price_to_beat=Decimal("1")))
    assert any(k == "price_to_beat_changed" for _, k, _, _ in sink.quality)


async def test_refresher_picks_up_price_to_beat_and_settlement(sink):
    clock = FakeClock(utc(2026, 10, 17, 5, 30, 1))
    open_raw = load("market_15m_open.json")
    pending = copy.deepcopy(open_raw)
    pending["market"]["assetPriceTerms"]["priceToBeat"] = None
    reg = InstrumentRegistry(sink, clock)
    reg.upsert(parse_instrument(pending))
    lookups = {utc(2026, 10, 17, 5, 29, 59): Decimal("81487.13")}
    ref = InstrumentRefresher(gw(), reg, sink, clock, lookups.get)
    assert [i.slug for i in ref.due(clock.now())] == [open_raw["market"]["slug"]]
    with respx.mock() as router:
        router.get(f"{BASE}/v1/market/slug/{open_raw['market']['slug']}").respond(
            200, content=(FIXTURES / "market_15m_open.json").read_bytes())
        fresh = await ref.refresh(reg.get(open_raw["market"]["slug"]))
    assert fresh.price_to_beat == Decimal("81487.13")
    assert ref.due(clock.now()) == []
    assert not any(k == "reference_rule_mismatch" for _, k, _, _ in sink.quality)


async def test_refresher_flags_reference_and_outcome_mismatch(sink):
    clock = FakeClock(utc(2026, 10, 17, 5, 16))
    up_raw = load("market_15m_resolved_up.json")
    slug = up_raw["market"]["slug"]
    reg = InstrumentRegistry(sink, clock)
    reg.upsert(parse_instrument(up_raw))
    wrong = {utc(2026, 10, 17, 4, 59, 59): Decimal("81421.81")}  # off by one cent
    ref = InstrumentRefresher(gw(), reg, sink, clock, wrong.get)
    with respx.mock() as router:
        router.get(f"{BASE}/v1/market/slug/{slug}").respond(
            200, content=(FIXTURES / "market_15m_resolved_up.json").read_bytes())
        router.get(f"{BASE}/v1/markets/{slug}/settlement").respond(200, json={"slug": slug, "settlement": 0})
        await ref.refresh(reg.get(slug))
    kinds = [k for _, k, _, _ in sink.quality]
    assert "reference_rule_mismatch" in kinds
    assert "outcome_rule_mismatch" in kinds  # venue flag 0 contradicts close >= open
    assert reg.settlement_flags[slug] == 0
    assert phase_of(reg.get(slug), clock.now()) is Phase.SETTLED
