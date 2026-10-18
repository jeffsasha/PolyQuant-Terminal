from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from polyquant.domain.models import Outcome, Phase, phase_of
from polyquant.domain.settlement import (
    check_references,
    derived_reference,
    outcome_from_prices,
    outcome_from_settlement_flag,
)
from polyquant.domain.timeutil import format_et, parse_utc
from polyquant.venue.parsing import parse_index_points, parse_instrument
from tests.conftest import load, utc

# ---- settlement rule -----------------------------------------------------------------------------


def test_tie_settles_up():
    assert outcome_from_prices(Decimal("81000.00"), Decimal("81000.00")) is Outcome.UP


def test_lower_close_settles_down():
    assert outcome_from_prices(Decimal("81000.00"), Decimal("80999.99")) is Outcome.DOWN


def test_settlement_flag_mapping():
    assert outcome_from_settlement_flag(1) is Outcome.UP
    assert outcome_from_settlement_flag(0) is Outcome.DOWN
    with pytest.raises(ValueError):
        outcome_from_settlement_flag(2)


def test_venue_settlement_flag_agrees_with_rule():
    inst = parse_instrument(load("market_15m_resolved_up.json"))
    assert load("settlement_15m_up.json")["settlement"] == 1
    assert inst.settled_outcome() is outcome_from_settlement_flag(1)


def _series(name):
    return {p.ts: p.value for p in parse_index_points(load(name), asset="btc", recv_at=utc(2026, 10, 17, 6))}


def test_official_reference_equals_index_point_at_t_minus_1s():
    """Recorded real data: priceToBeat of the 05:00Z window == index point stamped 04:59:59Z (§1.3)."""
    up = parse_instrument(load("market_15m_resolved_up.json"))  # window 05:00 → 05:15
    assert derived_reference(_series("brti_1s_before_0500z.json"), up.window_start) == up.price_to_beat
    assert derived_reference(_series("brti_1s_before_0515z.json"), up.window_end) == up.settlement_price


def test_naive_mean_of_window_does_not_match():
    """Documents why we do NOT average the 1s series again: it is already a 60s average."""
    up = parse_instrument(load("market_15m_resolved_up.json"))
    xs = list(_series("brti_1s_before_0500z.json").values())
    naive = (sum(xs) / len(xs)).quantize(Decimal("0.01"))
    assert naive != up.price_to_beat


def test_check_references_reports_mismatch():
    up = parse_instrument(load("market_15m_resolved_up.json"))
    series = _series("brti_1s_before_0500z.json") | _series("brti_1s_before_0515z.json")
    assert all(c.matches for c in check_references(up, series))
    bad = replace(up, price_to_beat=up.price_to_beat + Decimal("0.01"))
    checks = check_references(bad, series)
    assert [c.matches for c in checks] == [False, True]


# ---- lifecycle phase -----------------------------------------------------------------------------


def test_phase_transitions():
    inst = parse_instrument(load("market_15m_upcoming.json"))  # 06:00 → 06:15, status CLOSED
    assert phase_of(inst, utc(2026, 10, 17, 5, 59, 59)) is Phase.UPCOMING
    # window started but venue still says CLOSED → UNKNOWN (not tradable), never assumed open
    assert phase_of(inst, utc(2026, 10, 17, 6, 0, 0)) is Phase.UNKNOWN
    opened = replace(inst, status="MARKET_STATUS_OPEN")
    assert phase_of(opened, utc(2026, 10, 17, 6, 0, 0)) is Phase.OPEN
    assert phase_of(opened, utc(2026, 10, 17, 6, 14, 59)) is Phase.OPEN
    # end is exclusive
    assert phase_of(opened, utc(2026, 10, 17, 6, 15, 0)) is Phase.AWAITING_SETTLEMENT
    settled = replace(opened, status="MARKET_STATUS_RESOLVED", settlement_price=Decimal("1"))
    assert phase_of(settled, utc(2026, 10, 17, 6, 15, 10)) is Phase.SETTLED


def test_resolved_without_price_is_unknown():
    inst = replace(parse_instrument(load("market_15m_open.json")), status="MARKET_STATUS_RESOLVED")
    assert phase_of(inst, utc(2026, 10, 17, 5, 50)) is Phase.UNKNOWN


def test_settlement_price_before_window_end_is_unknown():
    inst = replace(parse_instrument(load("market_15m_open.json")), settlement_price=Decimal("1"))
    assert phase_of(inst, utc(2026, 10, 17, 5, 40)) is Phase.UNKNOWN


# ---- time handling -------------------------------------------------------------------------------


def test_parse_nanosecond_timestamp_truncates():
    t = parse_utc("2026-10-17T05:41:54.667293388Z")
    assert t == utc(2026, 10, 17, 5, 41, 54).replace(microsecond=667293)


def test_parse_rejects_naive():
    with pytest.raises(ValueError):
        parse_utc("2026-10-17T05:41:54")


def test_et_label_matches_venue_description_edt():
    inst = parse_instrument(load("market_15m_resolved_down.json"))  # 05:15Z → 05:30Z
    assert format_et(inst.window_start) == "1:15AM ET"
    assert format_et(inst.window_end) == "1:30AM ET"
    assert "1:30AM ET" in inst.description and "1:15AM ET" in inst.description


def test_et_label_across_dst_end():
    # US DST ends 2026-11-01 06:00Z (02:00 EDT → 01:00 EST)
    assert format_et(utc(2026, 11, 1, 5, 30)) == "1:30AM ET"  # EDT
    assert format_et(utc(2026, 11, 1, 6, 30)) == "1:30AM ET"  # EST, same wall clock an hour later
    assert format_et(utc(2026, 11, 1, 17, 0)) == "12:00PM ET"
