from __future__ import annotations

import math
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D

import numpy as np
import pytest

from polyquant.domain.models import Horizon, Outcome
from polyquant.domain.timeutil import to_unix
from polyquant.marketdata.book import BookSnapshot, Level
from polyquant.paper.execution import PROFILES
from polyquant.paper.models import TIF, OrderIntent, Side
from polyquant.research import calibration as cal
from polyquant.research.backtest import BookTimeline, replay, report
from polyquant.research.calibration import LabelledMarket, Record
from polyquant.strategy.base import Decision, Signal
from polyquant.venue.parsing import parse_instrument
from tests.conftest import load, utc

BASE = parse_instrument(load("market_15m_resolved_up.json"))  # 05:00-05:15Z, resolved Up


def mk(i: int, horizon=Horizon.M15, outcome=Outcome.UP) -> LabelledMarket:
    length = timedelta(minutes=15 if horizon is Horizon.M15 else 60)
    start = utc(2026, 10, 1) + timedelta(minutes=15 * i)
    inst = replace(BASE, slug=f"m{i}-{horizon.value}", horizon=horizon, window_start=start, window_end=start + length)
    return LabelledMarket(inst, outcome)


def rec(slug, p, y, h=Horizon.M15):
    return Record(slug, h, utc(2026, 10, 1), 60, p, y, 1.0, 0.0, 1.0)


# ---- labels and splits ----------------------------------------------------------------------------------


def test_labels_require_agreement_between_venue_and_rule():
    up = parse_instrument(load("market_15m_resolved_up.json"))
    conflict = replace(up, slug="x", venue_outcome=Outcome.DOWN)
    unresolved = replace(up, slug="y", settlement_price=None)
    markets, stats = cal.label_markets([up, conflict, unresolved])
    assert [m.inst.slug for m in markets] == [up.slug] and markets[0].outcome is Outcome.UP
    assert stats == {"no_reference": 0, "unresolved": 1, "conflict": 1}


def test_chronological_split_is_ordered_disjoint_and_embargoed():
    markets = [mk(i) for i in range(100)] + [mk(i, Horizon.H1) for i in range(2, 100, 4)]  # 1h starts at :30
    parts = cal.chronological_split(markets)
    dev, val, test, emb = parts["dev"], parts["val"], parts["test"], parts["embargoed"]
    assert len(dev) + len(val) + len(test) + len(emb) == len(markets)
    assert max(m.inst.window_end for m in dev) <= min(m.inst.window_start for m in val + test)
    assert max(m.inst.window_end for m in val) <= min(m.inst.window_start for m in test)
    cut1, cut2 = parts["_cuts"]
    for m in emb:  # every embargoed window straddles a cut
        assert any(m.inst.window_start < c < m.inst.window_end for c in (cut1, cut2))
    assert emb, "1h windows across the cuts should have been embargoed"


# ---- metrics -------------------------------------------------------------------------------------------


def test_metrics_known_values():
    rs = [rec("a", 0.8, 1), rec("b", 0.8, 0), rec("c", 0.2, 0), rec("d", 0.5, 1)]
    assert cal.brier(rs) == pytest.approx((0.04 + 0.64 + 0.04 + 0.25) / 4)
    expected_ll = -(math.log(0.8) + math.log(0.2) + math.log(0.8) + math.log(0.5)) / 4
    assert cal.log_loss(rs) == pytest.approx(expected_ll)
    s = cal.summary(rs)
    assert s["log_loss_coinflip"] == pytest.approx(math.log(2)) and s["brier_coinflip"] == pytest.approx(0.25)
    bins = cal.reliability(rs)
    assert bins[8]["n"] == 2 and bins[8]["freq_up"] == 0.5


def test_perfectly_calibrated_has_low_ece():
    rng = np.random.default_rng(4)
    ps = rng.uniform(0.05, 0.95, 20000)
    rs = [rec(f"m{i}", float(p), int(rng.uniform() < p)) for i, p in enumerate(ps)]
    assert cal.ece(rs) < 0.02


def test_bootstrap_resamples_whole_markets_and_is_seeded():
    rs = [rec("a", 0.9, 1), rec("a", 0.9, 1), rec("b", 0.6, 0), rec("b", 0.6, 0)]
    ci1 = cal.bootstrap_ci(rs, cal.logloss_improvement, n=300, seed=5)
    ci2 = cal.bootstrap_ci(rs, cal.logloss_improvement, n=300, seed=5)
    assert ci1 == ci2 and ci1[0] <= ci1[1]


def test_select_variant_uses_lowest_dev_log_loss():
    dev = {"good": [rec("a", 0.9, 1)], "bad": [rec("a", 0.4, 1)]}
    assert cal.select_variant(dev) == "good"


def test_walk_forward_only_trains_on_prior_markets(monkeypatch):
    calls = []

    def fake_build(ms, ts, vals, params, checkpoints=cal.CHECKPOINTS):
        calls.append([m.inst for m in ms])
        return [rec(m.inst.slug, 0.6, 1) for m in ms], 0

    monkeypatch.setattr(cal, "build_records", fake_build)
    from polyquant.strategy.fair_prob import ModelParams

    variants = [ModelParams(), ModelParams(dist="t4")]
    markets = [mk(i * 8) for i in range(84)] + [mk(700 + i * 8) for i in range(84)] + [mk(1400 + i * 8)
                                                                                       for i in range(84)]
    out = cal.walk_forward(markets, np.array([]), np.array([]), variants)
    folds = cal.weekly_folds(markets)
    assert len(out) == len(folds) - 1 >= 2
    per_fold = len(variants) + 1  # one selection call per variant, then one evaluation call
    assert len(calls) == per_fold * len(out)
    for k, f in enumerate(out, start=1):
        chunk = calls[(k - 1) * per_fold: k * per_fold]
        fold_start = min(m.inst.window_start for m in folds[k])
        for train in chunk[:-1]:
            assert train and all(i.window_end <= fold_start for i in train)  # strictly prior data
            assert len(train) == f["train_markets"]
        assert {i.slug for i in chunk[-1]} == {m.inst.slug for m in folds[k]}  # evaluated on the fold itself


# ---- execution replay -----------------------------------------------------------------------------------


class AlwaysBuyUp:
    name = "always_up"

    def decide(self, snap):
        if snap.book is None:
            return Decision(Signal.NO_TRADE, None)
        it = OrderIntent(client_order_id=f"t-{to_unix(snap.now)}", slug=snap.instrument.slug, outcome=Outcome.UP,
                         side=Side.BUY, qty=D("5"), limit_px=D("0.70"), tif=TIF.IOC, model_prob=D("0.9"))
        return Decision(Signal.BUY_UP, 0.9, (it,), why={"edge": 0.1})


def _bk(slug, t, ask):
    return BookSnapshot(slug=slug, bids=(Level(D(ask) - D("0.02"), D("1000")),), offers=(Level(D(ask), D("1000")),),
                        state="MARKET_STATE_OPEN", transact_time=t, recv_at=t)


def test_replay_fills_at_arrival_book_not_decision_book_and_settles():
    m = LabelledMarket(BASE, Outcome.UP)
    t0 = BASE.window_start + timedelta(seconds=5)
    # the price jumps 1 s after the first decision: latency must expose the later price
    books = {BASE.slug: BookTimeline([_bk(BASE.slug, t0 - timedelta(seconds=1), "0.50"),
                                      _bk(BASE.slug, t0 + timedelta(milliseconds=500), "0.60")])}
    ts = np.arange(to_unix(BASE.window_start) - 4000, to_unix(BASE.window_end) + 10, dtype=np.int64)
    vals = np.full(len(ts), 81421.82)
    res_base = replay([m], books, ts, vals, AlwaysBuyUp(), PROFILES["base"])  # 250 ms → still 0.50 book
    res_cons = replay([m], books, ts, vals, AlwaysBuyUp(), PROFILES["conservative"])  # 750 ms → 0.60 book
    tb, tc = res_base.trades[0], res_cons.trades[0]
    assert tb.notional / tb.qty == D("0.50")
    assert tc.notional / tc.qty == D("0.61")  # 0.60 + 1 adverse tick
    assert tb.won and tb.payout == tb.qty
    assert tc.slippage == (D("0.61") - D("0.50")) * tc.qty  # vs the book the strategy saw
    rep = report(res_cons)
    assert rep["trades"] == 1 and rep["sample_adequate"] is False and rep["win_rate"] == 1.0


def test_report_drawdown_streak_and_profit_factor():
    from polyquant.research.backtest import ReplayResult, ReplayTrade

    def t(net_payout, cost):
        return ReplayTrade("s", "15m", Outcome.UP, net_payout > 0, D(1), D(1), D(cost), D(0), D(net_payout),
                           utc(2026, 10, 1), 0.6, 0.05, D(0), D(0))

    res = ReplayResult("base", "x", trades=[t(1, "0.4"), t(0, "0.5"), t(0, "0.5"), t(1, "0.3")])
    rep = report(res)
    assert rep["net_pnl"] == pytest.approx(0.6 - 0.5 - 0.5 + 0.7)
    assert rep["max_losing_streak"] == 2
    assert rep["max_drawdown"] == pytest.approx(1.0)
    assert rep["profit_factor"] == pytest.approx(1.3 / 1.0)
