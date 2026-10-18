from __future__ import annotations

from decimal import Decimal as D

from polyquant.domain.models import Outcome
from polyquant.marketdata.book import BookSnapshot, Level
from polyquant.paper.execution import PROFILES, ExecutionProfile, maker_step, quantize_qty, sweep
from polyquant.paper.models import Side
from tests.conftest import utc

T = utc(2026, 10, 17, 7, 50)


def book(bids, asks) -> BookSnapshot:
    return BookSnapshot(slug="m", bids=tuple(Level(D(p), D(q)) for p, q in bids),
                        offers=tuple(Level(D(p), D(q)) for p, q in asks), state="MARKET_STATE_OPEN",
                        transact_time=T, recv_at=T)


B = book([("0.48", "100"), ("0.47", "200")], [("0.50", "50"), ("0.51", "100"), ("0.53", "1000")])
OPT = PROFILES["optimistic"]


def test_buy_up_walks_asks_with_vwap_never_mid():
    r = sweep(B, Outcome.UP, Side.BUY, D(120), D("0.52"), OPT)
    assert [(f.qty, f.px) for f in r.fills] == [(D(50), D("0.50")), (D(70), D("0.51"))]
    assert r.vwap == (D(50) * D("0.50") + D(70) * D("0.51")) / D(120)
    assert r.vwap > r.mid and r.best_px == D("0.50")


def test_limit_stops_the_sweep():
    r = sweep(B, Outcome.UP, Side.BUY, D(1000), D("0.51"), OPT)
    assert r.filled == D(150)  # 0.53 level is outside the limit


def test_buy_down_consumes_up_bids():
    r = sweep(B, Outcome.DOWN, Side.BUY, D(150), D("0.53"), OPT)
    # Down asks = 1 - Up bids: 0.52 (qty 100), 0.53 (qty 200)
    assert [(f.qty, f.px) for f in r.fills] == [(D(100), D("0.52")), (D(50), D("0.53"))]


def test_sell_up_hits_bids_and_sell_down_hits_inverted_asks():
    r = sweep(B, Outcome.UP, Side.SELL, D(150), D("0.47"), OPT)
    assert [(f.qty, f.px) for f in r.fills] == [(D(100), D("0.48")), (D(50), D("0.47"))]
    r = sweep(B, Outcome.DOWN, Side.SELL, D(60), D("0.49"), OPT)
    assert [(f.qty, f.px) for f in r.fills] == [(D(50), D("0.50")), (D(10), D("0.49"))]


def test_depth_haircut_and_slippage_ticks():
    cons = PROFILES["conservative"]  # haircut 0.5, +1 tick slippage
    r = sweep(B, Outcome.UP, Side.BUY, D(60), D("0.52"), cons)
    # 0.50 level: 25 available at 0.51; 0.51 level: 50 available at 0.52; 0.53 → 0.54 > limit
    assert [(f.qty, f.px) for f in r.fills] == [(D(25), D("0.51")), (D(35), D("0.52"))]
    stress = PROFILES["stress"]  # +2 ticks: 0.50 → 0.52 ok, 0.51 → 0.53 > limit
    r = sweep(B, Outcome.UP, Side.BUY, D(60), D("0.52"), stress)
    assert r.filled == D("12.5")


def test_partial_fill_when_liquidity_short():
    r = sweep(B, Outcome.UP, Side.BUY, D(5000), D("0.99"), OPT)
    assert r.filled == D(1150) and r.filled < r.requested


def test_consumed_liquidity_is_not_reused():
    used: dict = {}
    a = sweep(B, Outcome.UP, Side.BUY, D(40), D("0.50"), OPT, consumed=used)
    b = sweep(B, Outcome.UP, Side.BUY, D(40), D("0.50"), OPT, consumed=used)
    assert a.filled == D(40) and b.filled == D(10)


def test_quantize_down_to_min_qty():
    assert quantize_qty(D("12.349"), D("0.01")) == D("12.34")
    assert quantize_qty(D("0.004"), D("0.01")) == D(0)


# ---- maker queue model ------------------------------------------------------------------------------


def test_optimistic_fills_on_touch():
    touched = book([("0.48", "100")], [("0.49", "30")])  # best ask reaches our resting 0.49 bid
    upd = maker_step(touched, Outcome.UP, Side.BUY, D("0.49"), D(10), D(100), D(100), OPT)
    assert upd.fill_qty == D(10)


def test_base_does_not_fill_on_touch_with_queue_ahead():
    base = PROFILES["base"]
    at_touch = book([("0.48", "100")], [("0.49", "30")])  # opposite best equals our 0.49 buy: a touch, not a through
    upd = maker_step(at_touch, Outcome.UP, Side.BUY, D("0.49"), D(10), D(80), D(80), base)
    assert upd.fill_qty == 0 and upd.reason == "none"


def test_base_fills_on_touch_after_queue_depleted():
    base = PROFILES["base"]
    # our level (bid 0.49) shrank from 80 to 0 → 40 attributed to fills ahead (50%) … still 40 ahead
    s1 = book([("0.48", "100")], [("0.50", "30")])
    u1 = maker_step(s1, Outcome.UP, Side.BUY, D("0.49"), D(10), D(80), D(80), base)
    assert u1.queue_ahead == D(40)
    # more depletion is impossible (level gone); a touch alone does not fill with 40 still ahead
    s2 = book([("0.48", "100")], [("0.49", "30")])
    u2 = maker_step(s2, Outcome.UP, Side.BUY, D("0.49"), D(10), u1.queue_ahead, u1.level_qty, base)
    assert u2.fill_qty == 0
    # with the queue ahead consumed, a touch fills against displayed opposite size (haircut 0.8)
    u3 = maker_step(s2, Outcome.UP, Side.BUY, D("0.49"), D(10), D(0), D(0), base)
    assert u3.fill_qty == D(10) and u3.reason == "depleted"


def test_trade_through_fills_base_and_conservative():
    through = book([("0.47", "100")], [("0.48", "30")])  # ask 0.48 < our bid 0.49: crossed our level by 1 tick
    for name in ("base", "conservative"):
        upd = maker_step(through, Outcome.UP, Side.BUY, D("0.49"), D(10), D(500), D(500), PROFILES[name])
        assert upd.fill_qty == D(10) and upd.reason == "through"


def test_stress_needs_two_ticks_and_fills_half():
    stress = PROFILES["stress"]
    one_tick = book([("0.47", "100")], [("0.48", "30")])
    assert maker_step(one_tick, Outcome.UP, Side.BUY, D("0.49"), D(10), D(0), D(0), stress).fill_qty == 0
    two_ticks = book([("0.46", "100")], [("0.47", "30")])
    assert maker_step(two_ticks, Outcome.UP, Side.BUY, D("0.49"), D(10), D(0), D(0), stress).fill_qty == D(5)


def test_profiles_are_ordered_from_optimistic_to_stress():
    names = ["optimistic", "base", "conservative", "stress"]
    ps: list[ExecutionProfile] = [PROFILES[n] for n in names]
    assert [p.latency_ms for p in ps] == sorted(p.latency_ms for p in ps)
    assert [p.depth_haircut for p in ps] == sorted((p.depth_haircut for p in ps), reverse=True)
    assert ps[0].diagnostic_only and not any(p.diagnostic_only for p in ps[1:])
