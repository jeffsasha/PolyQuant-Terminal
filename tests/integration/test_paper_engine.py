"""Paper execution engine against a real PostgreSQL, with a controllable market view and clock."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D

import pytest

from polyquant.clock import FakeClock
from polyquant.domain.models import Outcome, phase_of
from polyquant.interfaces import MemorySink
from polyquant.marketdata.book import BookSnapshot, Level
from polyquant.paper.engine import PaperExecutionEngine
from polyquant.paper.ledger import PostgresLedger
from polyquant.paper.models import TIF, OrderIntent, OrderStatus, Side
from polyquant.paper.risk import CentralRiskManager, RiskConfig
from polyquant.venue.parsing import parse_instrument
from tests.conftest import load, utc

pytestmark = pytest.mark.db

M15 = "cpc-btc-updown-15m-2026-10-17-0530z"  # window 05:30-05:45Z, OPEN, priceToBeat set
H1 = "cpc-btc-updown-1h-2026-10-17-0500z"  # window 05:00-06:00Z


def mkbook(slug, bids, asks, t):
    return BookSnapshot(slug=slug, bids=tuple(Level(D(p), D(q)) for p, q in bids),
                        offers=tuple(Level(D(p), D(q)) for p, q in asks), state="MARKET_STATE_OPEN",
                        transact_time=t, recv_at=t)


BIDS = [("0.48", "100"), ("0.47", "200")]
ASKS = [("0.50", "50"), ("0.51", "100"), ("0.53", "1000")]


class FakeView:
    def __init__(self, clock):
        self.clock = clock
        self.instruments = {M15: parse_instrument(load("market_15m_open.json")),
                            H1: parse_instrument(load("market_1h_open.json"))}
        self.books = {s: mkbook(s, BIDS, ASKS, clock.now()) for s in self.instruments}
        self.stale: set[str] = set()
        self.idx_stale = False
        self.clock_bad = False
        self.ws_age = 100.0
        self.flags: dict[str, int] = {}

    def instrument(self, slug):
        return self.instruments.get(slug)

    def phase(self, slug, now):
        i = self.instruments.get(slug)
        return None if i is None else phase_of(i, now)

    def book(self, slug):
        return self.books.get(slug)

    def book_stale(self, slug):
        return slug in self.stale

    def ws_age_ms(self, now):
        return self.ws_age

    def index_stale(self):
        return self.idx_stale

    def clock_alert(self):
        return self.clock_bad

    def settlement_flag(self, slug):
        return self.flags.get(slug)


async def make(pool, clock=None, view=None, config=None, profile="conservative", account="t"):
    clock = clock or FakeClock(utc(2026, 10, 17, 5, 35))
    view = view or FakeView(clock)
    sink = MemorySink()
    eng = PaperExecutionEngine(PostgresLedger(pool, account), view, sink, clock,
                               risk=CentralRiskManager(config or RiskConfig()), profile=profile)
    await eng.start()
    return eng, view, clock, sink


def intent(cid, slug=M15, outcome=Outcome.UP, side=Side.BUY, qty="9", px="0.52", tif=TIF.IOC, **kw):
    return OrderIntent(client_order_id=cid, slug=slug, outcome=outcome, side=side, qty=D(qty), limit_px=D(px),
                       tif=tif, **kw)


async def assert_ledger_consistent(eng):
    async with eng.ledger.pool.acquire() as conn:
        row = await conn.fetchrow("SELECT sum(cash_delta) c, sum(reserved_delta) r FROM paper_ledger"
                                  " WHERE account_id=$1", eng.ledger.account)
    assert row["c"] == eng.st.cash
    assert row["r"] == eng.st.reserved
    assert eng.st.reserved == sum((o.reserved for o in eng.st.orders.values()), D(0))
    assert eng.st.reserved >= 0


async def run_until_terminal(eng, clock, order, seconds=2.0):
    clock.advance(seconds)
    await eng.step()


# ---- fills ---------------------------------------------------------------------------------------------


async def test_ioc_buy_fills_after_latency_with_fees_and_balanced_ledger(pool):
    eng, view, clock, _ = await make(pool)
    order, dec = await eng.submit(intent("c-ioc-1"))
    assert dec.approved, dec.reasons
    assert order.status is OrderStatus.PENDING and eng.st.reserved > 0
    await eng.step()  # before arrival: nothing happens
    assert order.status is OrderStatus.PENDING
    clock.advance(0.8)  # conservative latency 750 ms
    await eng.step()
    assert order.id not in eng.st.orders and order.status is OrderStatus.FILLED
    # conservative: 0.50 level haircut to 25, +1 tick → 9 @ 0.51
    pos = eng.st.positions[(M15, Outcome.UP)]
    assert pos.qty == D(9) and pos.cost == D("4.59")
    fee = D("0.0695") * 9 * D("0.51") * D("0.49")  # 0.15631… → 0.16
    assert pos.fees == D("0.16") and abs(pos.fees - fee) < D("0.01")
    assert eng.st.cash == D(1000) - D("4.59") - D("0.16") and eng.st.reserved == 0
    await assert_ledger_consistent(eng)
    fills = await eng.ledger.fills()
    assert fills[0]["liquidity"] == "taker" and fills[0]["slippage"] == D("0.09")  # (0.51 - 0.50) × 9


async def test_partial_fill_then_unfilled_ioc(pool):
    cfg = RiskConfig(min_fill_ratio=D(0), max_trade_risk_pct=D(100), max_exposure_pct=D(100),
                     horizon_exposure_pct={})
    eng, view, clock, _ = await make(pool, config=cfg)
    o, dec = await eng.submit(intent("c-part-1", qty="80", px="0.51"))
    assert dec.approved, dec.reasons
    clock.advance(1)
    await eng.step()
    # conservative: 0.50→25 @0.51; 0.51 level → 0.52 > limit → only 25 filled, remainder cancelled
    assert o.status is OrderStatus.CANCELLED and o.filled_qty == D(25) and o.reason == "IOC remainder cancelled"
    o2, dec2 = await eng.submit(intent("c-none-1", qty="5", px="0.45", outcome=Outcome.UP, slug=H1))
    assert dec2.approved
    clock.advance(1)
    await eng.step()
    assert o2.status is OrderStatus.CANCELLED and o2.filled_qty == 0 and "no liquidity" in o2.reason
    await assert_ledger_consistent(eng)


async def test_gtc_rests_then_fills_as_maker_on_trade_through(pool):
    eng, view, clock, _ = await make(pool)
    o, dec = await eng.submit(intent("c-gtc-1", px="0.49", tif=TIF.GTC, qty="5"))
    assert dec.approved, dec.reasons
    clock.advance(1)
    await eng.step()
    assert o.status is OrderStatus.OPEN and o.queue_ahead == 0  # nobody else bids 0.49
    # touch: ask comes to 0.49 — conservative does not count a touch as a fill
    view.books[M15] = mkbook(M15, BIDS, [("0.49", "10")] + ASKS, clock.now())
    clock.advance(0.3)
    await eng.step()
    assert o.status is OrderStatus.OPEN and o.filled_qty == 0
    # trade-through: ask at 0.48 < our 0.49
    view.books[M15] = mkbook(M15, [("0.47", "200")], [("0.48", "10")] + ASKS, clock.now())
    clock.advance(0.3)
    await eng.step()
    assert o.status is OrderStatus.FILLED and o.filled_qty == D(5)
    fills = await eng.ledger.fills()
    f = fills[0]
    assert f["liquidity"] == "maker" and f["px"] == D("0.49")
    # Oct 17: standard maker rebate -0.0125 × 5 × 0.49 × 0.51 = -0.0156… → -0.02 (credit)
    assert f["fee"] == D("-0.02")
    await assert_ledger_consistent(eng)


async def test_maker_rebate_is_zero_for_tier1_after_oct_19(pool):
    clock = FakeClock(utc(2026, 10, 20, 5, 35))
    view = FakeView(clock)
    for s, i in list(view.instruments.items()):
        shift = timedelta(days=3)
        view.instruments[s] = replace(i, window_start=i.window_start + shift, window_end=i.window_end + shift)
    view.books = {s: mkbook(s, BIDS, ASKS, clock.now()) for s in view.instruments}
    eng, *_ = await make(pool, clock=clock, view=view, account="t-oct20")
    o, dec = await eng.submit(intent("c-gtc-20", px="0.49", tif=TIF.GTC, qty="5"))
    assert dec.approved, dec.reasons
    clock.advance(1)
    await eng.step()
    view.books[M15] = mkbook(M15, [("0.47", "200")], [("0.48", "10")], clock.now())
    clock.advance(0.3)
    await eng.step()
    f = (await eng.ledger.fills())[0]
    assert f["liquidity"] == "maker" and f["fee"] == D("0.00") and f["fee_version"] == "2026-10-19-volume-tiers"


async def test_resting_order_expires_at_window_end_and_releases_capital(pool):
    eng, view, clock, _ = await make(pool)
    o, _ = await eng.submit(intent("c-exp-1", px="0.45", tif=TIF.GTC, qty="5"))
    clock.advance(1)
    await eng.step()
    assert o.status is OrderStatus.OPEN and eng.st.reserved > 0
    clock.set(utc(2026, 10, 17, 5, 45))
    await eng.step()
    assert o.status is OrderStatus.EXPIRED and eng.st.reserved == 0
    await assert_ledger_consistent(eng)


# ---- settlement ------------------------------------------------------------------------------------------


async def _filled_position(eng, clock, cid="c-set-1", outcome=Outcome.UP):
    o, dec = await eng.submit(intent(cid, outcome=outcome, px="0.53" if outcome is Outcome.DOWN else "0.52"))
    assert dec.approved, dec.reasons
    clock.advance(1)
    await eng.step()
    assert o.status is OrderStatus.FILLED


async def test_settlement_pays_winner_and_blocks_on_conflict(pool):
    eng, view, clock, sink = await make(pool)
    await _filled_position(eng, clock)
    cash_before = eng.st.cash
    inst = view.instruments[M15]
    # resolved: close 81500 ≥ open 81487.13 → Up
    view.instruments[M15] = replace(inst, status="MARKET_STATUS_RESOLVED", settlement_price=D("81500.00"))
    clock.set(utc(2026, 10, 17, 5, 45, 20))
    view.flags[M15] = 0  # venue says Down: contradicts the rule → must not settle
    await eng.step()
    assert (M15, Outcome.UP) in eng.st.positions
    assert any(k == "settlement_conflict" for _, k, _, _ in sink.quality)
    view.flags[M15] = 1
    await eng.step()
    assert (M15, Outcome.UP) not in eng.st.positions
    assert eng.st.cash == cash_before + D(9)  # $1 per winning contract, no fee at settlement
    pnl = await eng.ledger.pnl_breakdown()
    assert pnl["settlement_payouts"] == D(9) and pnl["winning_positions"] == 1
    await assert_ledger_consistent(eng)


async def test_losing_position_pays_nothing(pool):
    eng, view, clock, _ = await make(pool)
    await _filled_position(eng, clock, outcome=Outcome.DOWN)
    cash = eng.st.cash
    view.instruments[M15] = replace(view.instruments[M15], status="MARKET_STATUS_RESOLVED",
                                    settlement_price=D("81487.13"))  # tie → Up wins
    view.flags[M15] = 1
    clock.set(utc(2026, 10, 17, 5, 45, 20))
    await eng.step()
    assert eng.st.positions == {} and eng.st.cash == cash


# ---- capital, duplicates, limits ------------------------------------------------------------------------


async def test_insufficient_capital_and_per_trade_risk(pool):
    eng, *_ = await make(pool, config=RiskConfig(starting_capital=D(10)))
    _, dec = await eng.submit(intent("c-cap-1", qty="30", px="0.52"))
    assert not dec.approved and "insufficient_capital" in dec.reasons
    eng2, *_ = await make(pool, account="t2")
    _, dec2 = await eng2.submit(intent("c-risk-1", qty="20", px="0.52"))  # $10.4 > 0.5% of $1000
    assert not dec2.approved and any(r.startswith("trade_risk_exceeds") for r in dec2.reasons)


async def test_duplicate_client_order_id_and_duplicate_open_order(pool):
    eng, view, clock, _ = await make(pool)
    o1, d1 = await eng.submit(intent("c-dup-1", px="0.45", tif=TIF.GTC, qty="5"))
    o1b, d1b = await eng.submit(intent("c-dup-1", px="0.45", tif=TIF.GTC, qty="5"))
    assert o1b.id == o1.id and "duplicate_client_order_id_returned_existing" in d1b.reasons
    assert len(eng.st.orders) == 1
    _, d2 = await eng.submit(intent("c-dup-2", px="0.44", tif=TIF.GTC, qty="5"))
    assert not d2.approved and any(r.startswith("duplicate_open_order") for r in d2.reasons)
    async with pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM paper_orders WHERE client_order_id='c-dup-1'") == 1


async def test_position_and_exposure_limits(pool):
    eng, view, clock, _ = await make(pool, config=RiskConfig(max_open_positions=1))
    await _filled_position(eng, clock)
    _, dec = await eng.submit(intent("c-lim-2", slug=H1))
    assert not dec.approved and "max_open_positions" in dec.reasons
    cfg = RiskConfig(max_trade_risk_pct=D(10), max_exposure_pct=D(2), horizon_exposure_pct={})
    eng2, *_ = await make(pool, config=cfg, account="t3")
    _, dec2 = await eng2.submit(intent("c-exp-2", qty="40", px="0.52"))  # $20.8 + fee > 2% of $1000
    assert not dec2.approved and any(r.startswith("exposure_exceeds") for r in dec2.reasons)


async def test_sell_rules(pool):
    eng, view, clock, _ = await make(pool)
    _, dec = await eng.submit(intent("c-naked-1", side=Side.SELL, px="0.47"))
    assert not dec.approved and "sell_exceeds_position" in dec.reasons
    await _filled_position(eng, clock)
    _, dec2 = await eng.submit(intent("c-opp-1", outcome=Outcome.DOWN, px="0.53"))
    assert not dec2.approved and "opposite_side_held" in dec2.reasons
    o, dec3 = await eng.submit(intent("c-exit-1", side=Side.SELL, qty="9", px="0.45"))
    assert dec3.approved, dec3.reasons
    clock.advance(1)
    await eng.step()
    assert o.status is OrderStatus.FILLED and (M15, Outcome.UP) not in eng.st.positions
    await assert_ledger_consistent(eng)


# ---- safety gates ----------------------------------------------------------------------------------------


@pytest.mark.parametrize("mutate,reason", [
    (lambda v, c: v.stale.add(M15), "book_stale_or_missing"),
    (lambda v, c: setattr(v, "idx_stale", True), "index_stale"),
    (lambda v, c: setattr(v, "clock_bad", True), "clock_skew_high"),
    (lambda v, c: v.instruments.__setitem__(M15, replace(v.instruments[M15], price_to_beat=None)),
     "reference_unavailable"),
    (lambda v, c: c.set(utc(2026, 10, 17, 5, 44, 30)), "no_entry_window:30s_to_close"),
    (lambda v, c: c.set(utc(2026, 10, 17, 5, 46)), "market_not_open:AWAITING_SETTLEMENT"),
    (lambda v, c: v.books.__setitem__(M15, mkbook(M15, [("0.40", "100")], [("0.50", "100")], c.now())),
     "spread_too_wide:0.10"),
])
async def test_entry_gates(pool, mutate, reason):
    eng, view, clock, _ = await make(pool)
    mutate(view, clock)
    _, dec = await eng.submit(intent(f"c-gate-{abs(hash(reason)) % 10**8}"))
    assert not dec.approved and reason in dec.reasons, dec.reasons


async def test_edge_after_costs_gate(pool):
    eng, *_ = await make(pool)
    _, dec = await eng.submit(intent("c-edge-1", model_prob=D("0.52")))  # vwap 0.51 + fee ≈ 0.53 > 0.52 - min edge
    assert not dec.approved and any(r.startswith("edge_after_costs_below_min") for r in dec.reasons)
    _, dec2 = await eng.submit(intent("c-edge-2", model_prob=D("0.60")))
    assert dec2.approved, dec2.reasons


async def test_stale_book_at_arrival_rejects_instead_of_filling(pool):
    eng, view, clock, _ = await make(pool)
    o, dec = await eng.submit(intent("c-stale-arr"))
    assert dec.approved
    view.ws_age = 5000.0  # WS went quiet while the order was in flight
    clock.advance(1)
    await eng.step()
    assert o.status is OrderStatus.REJECTED and "no fresh book" in o.reason and eng.st.reserved == 0


async def test_fees_unknown_before_schedule_start(pool):
    """Before 2026-10-07 10:00 ET no fee schedule is documented: entries must not be priced with today's fees."""
    clock = FakeClock(utc(2026, 10, 1, 5, 35))
    view = FakeView(clock)
    for s, i in list(view.instruments.items()):
        view.instruments[s] = replace(i, window_start=i.window_start - timedelta(days=16),
                                      window_end=i.window_end - timedelta(days=16))
    eng, *_ = await make(pool, clock=clock, view=view, account="t-old")
    _, dec = await eng.submit(intent("c-old-1"))
    assert not dec.approved and any(r.startswith("trade_risk_exceeds") for r in dec.reasons), dec.reasons


# ---- kill switches and restart recovery ---------------------------------------------------------------


async def test_daily_loss_halt_blocks_entries_but_allows_exits(pool):
    cfg = RiskConfig(max_trade_risk_pct=D(10), max_exposure_pct=D(10), horizon_exposure_pct={})
    eng, view, clock, sink = await make(pool, config=cfg)
    o, dec = await eng.submit(intent("c-dl-1", qty="45", px="0.52"))
    assert dec.approved, dec.reasons
    clock.advance(1)
    await eng.step()
    assert o.filled_qty > 0
    view.books[M15] = mkbook(M15, [("0.02", "1000")], [("0.03", "1000")], clock.now())  # position collapses
    clock.advance(1)
    await eng.step()
    assert eng.daily_halt(clock.now())
    assert any(k == "daily_loss_halt" for _, k, _, _ in sink.quality)
    _, dec2 = await eng.submit(intent("c-dl-2", slug=H1, qty="1"))
    assert not dec2.approved and "daily_loss_halt" in dec2.reasons
    _, dec3 = await eng.submit(intent("c-dl-exit", side=Side.SELL, qty=str(o.filled_qty), px="0.02"))
    assert "daily_loss_halt" not in dec3.reasons and "kill_switch_on" not in dec3.reasons


async def test_kill_switch_cancels_entries_and_persists_across_restart(pool):
    eng, view, clock, _ = await make(pool)
    o, _ = await eng.submit(intent("c-ks-1", px="0.45", tif=TIF.GTC, qty="5"))
    clock.advance(1)
    await eng.step()
    await eng.set_kill_switch(True, "manual emergency stop test")
    assert o.status is OrderStatus.CANCELLED and eng.st.reserved == 0
    eng2, *_ = await make(pool, clock=clock, view=view)  # restart on the same account
    assert eng2.halted()
    _, dec = await eng2.submit(intent("c-ks-2"))
    assert not dec.approved and "kill_switch_on" in dec.reasons
    await eng2.set_kill_switch(False, "resume")
    _, dec2 = await eng2.submit(intent("c-ks-3"))
    assert dec2.approved, dec2.reasons


async def test_restart_rebuilds_state_and_cancels_inflight_orders(pool):
    eng, view, clock, _ = await make(pool, config=RiskConfig(max_open_positions=3))
    third = "cpc-btc-updown-15m-third"
    view.instruments[third] = replace(view.instruments[M15], slug=third)
    view.books[third] = mkbook(third, BIDS, ASKS, clock.now())
    await _filled_position(eng, clock)
    resting, d1 = await eng.submit(intent("c-rs-rest", slug=H1, px="0.45", tif=TIF.GTC, qty="5"))
    assert d1.approved, d1.reasons
    clock.advance(1)
    await eng.step()
    assert resting.status is OrderStatus.OPEN
    inflight, d2 = await eng.submit(intent("c-rs-fly", slug=third, qty="1", px="0.52"))
    assert d2.approved, d2.reasons
    assert inflight.status is OrderStatus.PENDING and inflight.reserved > 0  # restart happens before arrival
    cash = eng.st.cash
    positions = {k: (p.qty, p.cost) for k, p in eng.st.positions.items()}
    resting_reserve = resting.reserved

    eng2, *_ = await make(pool, clock=clock, view=view, config=RiskConfig(max_open_positions=3))  # restart
    assert eng2.st.cash == cash
    assert {k: (p.qty, p.cost) for k, p in eng2.st.positions.items()} == positions
    assert resting.id in eng2.st.orders and eng2.st.orders[resting.id].queue_ahead is None  # back of queue
    assert inflight.id not in eng2.st.orders  # in-flight outcome unknown → cancelled, never assumed filled
    assert eng2.st.reserved == resting_reserve  # only the resting order still holds capital
    async with pool.acquire() as conn:
        st, reason = await conn.fetchrow("SELECT status, reason FROM paper_orders WHERE id=$1", inflight.id)
    assert st == "CANCELLED" and reason.startswith("restart")
    await assert_ledger_consistent(eng2)
    # the resting order re-initialises its queue on the next book and keeps working
    clock.advance(0.3)
    await eng2.step()
    assert eng2.st.orders[resting.id].queue_ahead is not None

def test_optimistic_profile_cannot_drive_the_ledger():
    with pytest.raises(ValueError, match="diagnostic"):
        PaperExecutionEngine(None, None, None, None, profile="optimistic")


def test_live_execution_is_still_impossible():
    from polyquant.execution.live import LiveExecutionEngine, LiveTradingDisabled

    with pytest.raises(LiveTradingDisabled):
        import asyncio

        asyncio.run(LiveExecutionEngine().submit({}))


async def test_partially_filled_gtc_releases_reserve_proportionally(pool):
    cfg = RiskConfig(max_trade_risk_pct=D(10), max_exposure_pct=D(10), horizon_exposure_pct={})
    eng, view, clock, _ = await make(pool, config=cfg)
    o, dec = await eng.submit(intent("c-pgtc-1", qty="60", px="0.51", tif=TIF.GTC))
    assert dec.approved, dec.reasons
    initial = o.reserved
    clock.advance(1)
    await eng.step()
    # conservative: 25 fill as taker at 0.51 (0.50 level halved, +1 tick); 35 rest at 0.51
    assert o.status is OrderStatus.PARTIALLY_FILLED and o.filled_qty == D(25)
    assert o.reserved == initial * D(35) / D(60)
    assert eng.available == eng.st.cash - eng.st.reserved
    await assert_ledger_consistent(eng)


async def test_settles_on_venue_outcome_without_waiting_for_cached_flag(pool):
    """Live finding: the /settlement flag is CDN-cached and arrived ~5 min after resolution; the uncached instrument
    already carries status RESOLVED + outcomePrices. Settle on that when it agrees with the price rule."""
    from polyquant.domain.models import Outcome as O

    eng, view, clock, _ = await make(pool)
    await _filled_position(eng, clock)
    cash = eng.st.cash
    view.instruments[M15] = replace(view.instruments[M15], status="MARKET_STATUS_RESOLVED",
                                    settlement_price=D("81500.00"), venue_outcome=O.UP)
    clock.set(utc(2026, 10, 17, 5, 45, 20))
    await eng.step()  # no flag yet
    assert eng.st.positions == {} and eng.st.cash == cash + D(9)
    async with pool.acquire() as conn:
        detail = await conn.fetchval("SELECT detail FROM paper_settlements WHERE account_id=$1", eng.ledger.account)
    assert "outcome_prices" in detail and "price_rule" in detail


async def test_venue_outcome_contradicting_flag_blocks_settlement(pool):
    from polyquant.domain.models import Outcome as O

    eng, view, clock, sink = await make(pool)
    await _filled_position(eng, clock)
    view.instruments[M15] = replace(view.instruments[M15], status="MARKET_STATUS_RESOLVED",
                                    settlement_price=D("81500.00"), venue_outcome=O.UP)
    view.flags[M15] = 0
    clock.set(utc(2026, 10, 17, 5, 45, 20))
    await eng.step()
    assert (M15, O.UP) in eng.st.positions
    assert any(k == "settlement_conflict" for _, k, _, _ in sink.quality)
