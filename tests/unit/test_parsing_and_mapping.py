from __future__ import annotations

from decimal import Decimal

import pytest

from polyquant.domain.models import Horizon, Outcome, Source
from polyquant.venue.parsing import (
    ParseError,
    is_target_market,
    iter_event_markets,
    parse_bbo,
    parse_index_points,
    parse_instrument,
)
from tests.conftest import load, utc


def test_open_15m_market_fields():
    inst = parse_instrument(load("market_15m_open.json"))
    assert inst.slug == "cpc-btc-updown-15m-2026-10-17-0530z"
    assert inst.horizon is Horizon.M15
    assert inst.index_symbol == "BRTI"
    assert inst.window_start == utc(2026, 10, 17, 5, 30)
    assert inst.window_end == utc(2026, 10, 17, 5, 45)
    assert inst.price_to_beat == Decimal("81487.13")
    assert inst.settlement_price is None
    assert inst.fee_coefficient == Decimal("0.0695")
    assert inst.tick_size == Decimal("0.01")
    assert inst.status == "MARKET_STATUS_OPEN"


def test_up_down_mapping_long_is_up():
    inst = parse_instrument(load("market_15m_open.json"))
    # venue: long side described "Yes" = Up; short side "No" = Down
    assert inst.up_side_label == "Yes"
    assert inst.down_side_label == "No"


def test_1h_market_window_length():
    inst = parse_instrument(load("market_1h_open.json"))
    assert inst.horizon is Horizon.H1
    assert (inst.window_end - inst.window_start).total_seconds() == 3600


def test_upcoming_market_has_no_reference():
    inst = parse_instrument(load("market_15m_upcoming.json"))
    assert inst.status == "MARKET_STATUS_CLOSED"
    assert inst.price_to_beat is None


@pytest.mark.parametrize("name,outcome", [("market_15m_resolved_up.json", Outcome.UP),
                                          ("market_15m_resolved_down.json", Outcome.DOWN)])
def test_resolved_outcomes(name, outcome):
    inst = parse_instrument(load(name))
    assert inst.settled_outcome() is outcome


def test_rejects_float_money():
    raw = load("market_15m_open.json")
    raw["market"]["assetPriceTerms"]["priceToBeat"] = {"value": 81487.13, "currency": "USD"}
    with pytest.raises(ParseError, match="float"):
        parse_instrument(raw)


def test_rejects_window_that_does_not_match_horizon():
    raw = load("market_15m_open.json")
    raw["market"]["assetPriceTerms"]["horizon"] = "1h"
    with pytest.raises(ParseError, match="does not match horizon"):
        parse_instrument(raw)


def test_rejects_ambiguous_sides():
    raw = load("market_15m_open.json")
    for s in raw["market"]["marketSides"]:
        s["long"] = True
    with pytest.raises(ParseError, match="exactly one long"):
        parse_instrument(raw)


def test_rejects_non_usd():
    raw = load("market_15m_open.json")
    raw["market"]["assetPriceTerms"]["priceToBeat"]["currency"] = "EUR"
    with pytest.raises(ParseError, match="currency"):
        parse_instrument(raw)


def test_target_filter_is_metadata_based():
    markets = [m for _, m in iter_event_markets(load("events_crypto_closed_upcoming.json"))]
    hits = [m for m in markets if is_target_market(m, "btc", ("15m", "1h"))]
    assert hits, "expected BTC up/down markets in fixture"
    assert all("btc-updown" in m["slug"] for m in hits)
    # ETH up/down and BTC range markets are present in the fixture but must be filtered out
    assert any("eth-updown" in m["slug"] for m in markets)
    assert any("range" in m["slug"] for m in markets)
    assert not any("eth" in m["slug"] or "range" in m["slug"] for m in hits)


def test_bbo_derived_down_prices():
    raw = load("bbo_15m_open.json")
    snap = parse_bbo(raw, sent_at=utc(2026, 10, 17, 5, 41, 55), recv_at=utc(2026, 10, 17, 5, 41, 56))
    assert snap.up_bid == Decimal("0.1400") and snap.up_ask == Decimal("0.1500")
    # buying Down = selling into the Up bid → Down ask = 1 - Up bid
    assert snap.down_ask == Decimal("0.8600")
    assert snap.down_bid == Decimal("0.8500")
    # venue's own quote for the short side agrees with our derivation
    assert Decimal(raw["marketData"]["shortQuote"]["value"]) == snap.down_ask
    assert snap.spread == Decimal("0.0100")
    assert not snap.crossed
    assert snap.last_trade_ts is not None and snap.last_trade_ts.microsecond == 667293
    assert snap.source is Source.GATEWAY


def test_index_points_parse_sorted_decimal():
    pts = parse_index_points(load("brti_1s_before_0500z.json"), asset="btc", recv_at=utc(2026, 10, 17, 5, 42))
    assert len(pts) == 60
    assert all(isinstance(p.value, Decimal) for p in pts)
    assert [p.ts for p in pts] == sorted(p.ts for p in pts)
    assert {p.tick_count for p in pts} == {60}


def test_venue_outcome_from_outcome_prices():
    assert parse_instrument(load("market_15m_resolved_up.json")).venue_outcome is Outcome.UP
    assert parse_instrument(load("market_15m_resolved_down.json")).venue_outcome is Outcome.DOWN
    assert parse_instrument(load("market_15m_open.json")).venue_outcome is None  # not resolved → never inferred
    raw = load("market_15m_resolved_up.json")
    raw["market"]["outcomePrices"] = '["0.5","0.5"]'  # not definitive
    assert parse_instrument(raw).venue_outcome is None
