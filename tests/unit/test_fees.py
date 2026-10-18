from __future__ import annotations

from datetime import datetime
from decimal import Decimal as D
from zoneinfo import ZoneInfo

import pytest

from polyquant.fees.schedule import FeeSchedule, FeeScheduleUnknown, bankers_cents

ET = ZoneInfo("America/New_York")


def et(*a):
    return datetime(*a, tzinfo=ET)


F = FeeSchedule()
NOW = et(2026, 10, 17, 2, 0)


def test_documented_taker_examples():
    # Θ·C·p·(1−p) = 0.0695 × 100 × 0.5 × 0.5 = 1.7375 → $1.74
    assert F.taker_fee(D(100), D("0.50"), NOW) == D("1.74")
    # 1000 contracts at 0.30: 0.0695 × 1000 × 0.3 × 0.7 = 14.595, an exact half-cent tie → half-even → 14.60
    assert F.taker_fee(D(1000), D("0.30"), NOW) == D("14.60")


def test_bankers_rounding_half_even():
    assert bankers_cents(D("0.025")) == D("0.02")
    assert bankers_cents(D("0.035")) == D("0.04")
    assert bankers_cents(D("0.0251")) == D("0.03")


def test_fee_is_symmetric_for_up_and_down_prices():
    # an Up fill at p and a Down fill at 1-p are the same trade: same fee
    assert F.taker_fee(D(37), D("0.23"), NOW) == F.taker_fee(D(37), D("0.77"), NOW)


def test_cumulative_cap_only_reduces():
    # three fills with exact fee 0.006 each: naive per-fill rounding = 0.03, cap = round(0.018) = 0.02
    fills = [(D(1), D("0.5"))] * 3
    out = F.order_fills(fills, NOW, liquidity="taker", theta_override=D("0.024"))
    assert [f.charged for f in out] == [D("0.01"), D("0"), D("0.01")]
    assert sum(f.charged for f in out) == bankers_cents(sum(f.exact for f in out))
    # never above the per-fill rounded charge
    assert all(f.charged <= bankers_cents(f.exact) for f in out)


def test_version_boundaries_in_eastern_time():
    assert F.version_at(et(2026, 10, 19, 12, 59, 59)).name == "2026-10-15-crypto-bonus-ended"
    assert F.version_at(et(2026, 10, 19, 13, 0, 0)).name == "2026-10-19-volume-tiers"
    assert F.version_at(et(2026, 10, 15, 7, 59)).name == "2026-10-07-standard"
    assert F.version_at(et(2026, 10, 15, 8, 0)).name == "2026-10-15-crypto-bonus-ended"
    # same instant given in UTC
    from datetime import UTC

    assert F.version_at(datetime(2026, 10, 19, 17, 0, tzinfo=UTC)).name == "2026-10-19-volume-tiers"


def test_maker_rebate_tier1_goes_to_zero_on_oct_19():
    before = F.maker_rebate(D(1000), D("0.5"), et(2026, 10, 19, 12, 0))
    after = F.maker_rebate(D(1000), D("0.5"), et(2026, 10, 19, 14, 0))
    assert before == D("-3.12")  # -0.0125 × 1000 × 0.25 = -3.125 → banker's → -3.12
    assert after == D("0.00")
    tier3 = FeeSchedule(maker_tier=3).maker_rebate(D(1000), D("0.5"), et(2026, 10, 20, 9))
    assert tier3 == D("-1.75")


def test_taker_formula_unchanged_across_versions():
    a = F.taker_fee(D(10), D("0.4"), et(2026, 10, 8, 12))
    b = F.taker_fee(D(10), D("0.4"), et(2026, 10, 20, 12))
    assert a == b


def test_no_schedule_before_documented_start():
    with pytest.raises(FeeScheduleUnknown):
        F.version_at(et(2026, 10, 7, 9, 59))


@pytest.mark.parametrize("px", [D(0), D(1), D("1.2"), D("-0.1")])
def test_rejects_invalid_prices(px):
    with pytest.raises(ValueError):
        F.taker_fee(D(1), px, NOW)


def test_rejects_naive_datetime():
    with pytest.raises(ValueError):
        F.version_at(datetime(2026, 10, 17, 12))
