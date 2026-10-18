from __future__ import annotations

import math
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D

import numpy as np
import pytest

from polyquant.domain.timeutil import to_unix
from polyquant.marketdata.book import BookSnapshot, Level
from polyquant.strategy.base import LookaheadError, MarketSnapshot, PITInstrument, PointInTimeSeries, Signal
from polyquant.strategy.fair_prob import (
    FairProbabilityModel,
    FairProbabilityStrategy,
    ModelParams,
    drift_ma_change,
    estimate_sigma2,
    var_ma_change,
)
from polyquant.venue.parsing import parse_instrument
from tests.conftest import load

W = 60


def moving_average(x: np.ndarray, w: int = W) -> np.ndarray:
    c = np.cumsum(np.concatenate([[0.0], x]))
    return (c[w:] - c[:-w]) / w  # ma[i] = mean(x[i : i + w]) → aligned to x index i + w - 1


# ---- model mathematics (derivation checks by simulation) --------------------------------------------------


def test_variance_formula_limits():
    assert var_ma_change(0, 1.0) == 0
    assert var_ma_change(1, 1.0) == pytest.approx(1 / W)  # one step: the average moves by ε/w, w² terms → 1/w
    # discrete exact value at τ = w vs continuous 2w/3 = 40: close but not equal
    assert var_ma_change(W, 1.0) == pytest.approx(40.0, rel=0.02)
    # large τ: approaches τ − w/3
    assert var_ma_change(3600, 1.0) == pytest.approx(3600 - W / 3, rel=1e-3)


@pytest.mark.parametrize("tau", [10, 30, 60, 120, 300])
def test_variance_of_moving_average_change_matches_simulation(tau):
    rng = np.random.default_rng(1)
    sigma = 3.0
    n_paths, length = 4000, W + tau + 5
    steps = rng.normal(0, sigma, size=(n_paths, length))
    paths = np.cumsum(steps, axis=1)
    ma = np.apply_along_axis(moving_average, 1, paths)
    t = 0
    change = ma[:, t + tau] - ma[:, t]
    assert np.var(change) == pytest.approx(var_ma_change(tau, sigma ** 2), rel=0.06)


def test_sigma_estimator_recovers_spot_vol_from_smoothed_series():
    rng = np.random.default_rng(2)
    sigma = 2.5
    spot = np.cumsum(rng.normal(0, sigma, 200_000))
    ma = moving_average(spot)
    est = estimate_sigma2(ma, lag=120)
    assert math.sqrt(est) == pytest.approx(sigma, rel=0.05)
    # naive 1 s differences of the smoothed series badly underestimate vol — the reason for the correction
    naive = np.std(np.diff(ma))
    assert naive < 0.3 * sigma


@pytest.mark.parametrize("tau", [10, 30, 59, 60, 200])
def test_drift_formula_matches_linear_past_flat_future(tau):
    b = 0.7
    past = 200
    spot = np.concatenate([b * np.arange(past), np.full(tau + 5, b * (past - 1))])  # linear until t, then flat
    ma = moving_average(spot)
    t_idx = past - 1 - (W - 1)  # ma index whose window ends at spot index past-1 (= time t)
    change = ma[t_idx + tau] - ma[t_idx]
    assert change == pytest.approx(drift_ma_change(tau, b), rel=1e-9, abs=1e-9)


# ---- point-in-time data -------------------------------------------------------------------------------------

TS = np.arange(1000, 2000, dtype=np.int64)
VALS = np.linspace(100.0, 200.0, len(TS))


def test_pit_series_blocks_future_access():
    s = PointInTimeSeries(TS, VALS, now_unix=1500)
    assert s.latest()[0] == 1499  # publish lag 1 s
    assert s.value_at(1499) is not None
    with pytest.raises(LookaheadError):
        s.value_at(1500)
    with pytest.raises(LookaheadError):
        s.window(1400, 1600)
    t, v = s.window(1490, 1499)
    assert t[-1] == 1499 and len(t) == 10


def test_pit_instrument_hides_settlement_and_early_reference():
    inst = parse_instrument(load("market_15m_resolved_up.json"))  # fully resolved in reality
    early = PITInstrument.from_instrument(inst, inst.window_start + timedelta(seconds=2))
    later = PITInstrument.from_instrument(inst, inst.window_start + timedelta(seconds=6))
    assert early.price_to_beat is None and later.price_to_beat == inst.price_to_beat
    for leaked in ("settlement_price", "venue_outcome", "status", "settled_outcome"):
        assert not hasattr(later, leaked)


# ---- model behaviour ----------------------------------------------------------------------------------------


def _snap(inst, now, ts, vals, book=None, **kw):
    return MarketSnapshot(now=now, instrument=PITInstrument.from_instrument(inst, now),
                          series=PointInTimeSeries(ts, vals, to_unix(now)), book=book, **kw)


def _series_around(inst, level: float, sigma: float = 2.0, seed: int = 3):
    rng = np.random.default_rng(seed)
    start = to_unix(inst.window_start) - 4 * 3600
    end = to_unix(inst.window_end) + 120
    ts = np.arange(start, end, dtype=np.int64)
    spot = level + np.cumsum(rng.normal(0, sigma, len(ts) + W - 1))
    return ts, moving_average(spot)[: len(ts)]


INST = parse_instrument(load("market_15m_open.json"))  # 05:30-05:45Z, ptb 81487.13


def _visible_level(ts, vals, now):
    return float(vals[int(np.searchsorted(ts, to_unix(now) - 1))])


def test_probability_is_symmetric_and_monotone_in_distance():
    ts, vals = _series_around(INST, 81000.0)
    now = INST.window_end - timedelta(seconds=300)
    level = _visible_level(ts, vals, now)
    m = FairProbabilityModel()
    p = {dist: m.predict(_snap(replace(INST, price_to_beat=D(str(round(level - dist, 2)))), now, ts, vals)).p_up
         for dist in (-20, -5, 0, 5, 20)}
    assert p[-20] < p[-5] < p[0] < p[5] < p[20]
    assert p[0] == pytest.approx(0.5, abs=0.01)
    assert p[5] + p[-5] == pytest.approx(1.0, abs=2e-3) and p[20] + p[-20] == pytest.approx(1.0, abs=2e-3)


def test_uncertainty_shrinks_toward_settlement():
    ts, vals = _series_around(INST, float(INST.price_to_beat) + 15)
    m = FairProbabilityModel()
    sds = [m.predict(_snap(INST, INST.window_end - timedelta(seconds=s), ts, vals)).sd for s in (600, 120, 30, 5)]
    assert sds == sorted(sds, reverse=True)


def test_student_t_has_fatter_tails_than_gaussian():
    ts, vals = _series_around(INST, 81000.0, sigma=1.0)
    now = INST.window_end - timedelta(seconds=300)
    level = _visible_level(ts, vals, now)
    sd = FairProbabilityModel().predict(_snap(INST, now, ts, vals)).sd
    inst = replace(INST, price_to_beat=D(str(round(level - 2.5 * sd, 2))))  # 2.5 sd above the strike
    g = FairProbabilityModel(ModelParams(dist="gauss")).predict(_snap(inst, now, ts, vals)).p_up
    t = FairProbabilityModel(ModelParams(dist="t4")).predict(_snap(inst, now, ts, vals)).p_up
    assert 0.5 < t < g < 0.999  # same variance, more tail mass → less certain far from the strike


def test_model_needs_reference_and_history():
    ts, vals = _series_around(INST, 81000)
    early = INST.window_start + timedelta(seconds=2)
    assert FairProbabilityModel().predict(_snap(INST, early, ts, vals)) is None  # ptb not yet observable
    short_ts, short_vals = ts[-200:], vals[-200:]
    assert FairProbabilityModel().predict(_snap(INST, INST.window_end - timedelta(seconds=60), short_ts,
                                                short_vals)) is None


# ---- leakage: decisions must not depend on anything after the decision time --------------------------------


def test_future_perturbation_does_not_change_predictions_or_decisions():
    ts, vals = _series_around(INST, float(INST.price_to_beat) + 20)
    book = BookSnapshot(slug=INST.slug, bids=(Level(D("0.30"), D("500")),), offers=(Level(D("0.32"), D("500")),),
                        state="MARKET_STATE_OPEN", transact_time=INST.window_start, recv_at=INST.window_start)
    strat = FairProbabilityStrategy()
    rng = np.random.default_rng(9)
    for secs in (600, 300, 120):
        now = INST.window_end - timedelta(seconds=secs)
        cut = int(np.searchsorted(ts, to_unix(now) - 1, side="right"))
        scrambled = vals.copy()
        scrambled[cut:] = rng.normal(0, 1e6, len(vals) - cut)  # garbage after the cutoff
        a = strat.decide(_snap(INST, now, ts, vals, book))
        b = strat.decide(_snap(INST, now, ts, scrambled, book))
        assert (a.signal, a.p_up, a.intents) == (b.signal, b.p_up, b.intents)


# ---- strategy -------------------------------------------------------------------------------------------------


def _book(bid, ask, qty="1000"):
    t = INST.window_start
    return BookSnapshot(slug=INST.slug, bids=(Level(D(bid), D(qty)),), offers=(Level(D(ask), D(qty)),),
                        state="MARKET_STATE_OPEN", transact_time=t, recv_at=t)


def test_strategy_buys_underpriced_side_within_budget():
    ts, vals = _series_around(INST, float(INST.price_to_beat) + 80, sigma=1.0)  # far above strike → p_up high
    now = INST.window_end - timedelta(seconds=300)
    d = FairProbabilityStrategy().decide(_snap(INST, now, ts, vals, _book("0.60", "0.62")))
    assert d.signal is Signal.BUY_UP and d.p_up > 0.9
    it = d.intents[0]
    assert it.qty * it.limit_px <= D("4.00") and it.model_prob is not None and it.tif.value == "IOC"


def test_strategy_no_trade_when_price_reflects_probability():
    ts, vals = _series_around(INST, float(INST.price_to_beat) + 80, sigma=1.0)
    now = INST.window_end - timedelta(seconds=300)
    d = FairProbabilityStrategy().decide(_snap(INST, now, ts, vals, _book("0.98", "0.99")))
    assert d.signal is Signal.NO_TRADE and d.why["reason"] == "no_edge_after_costs"


def test_strategy_respects_settlement_window_and_existing_position():
    ts, vals = _series_around(INST, float(INST.price_to_beat) + 80, sigma=1.0)
    late = INST.window_end - timedelta(seconds=30)
    assert FairProbabilityStrategy().decide(_snap(INST, late, ts, vals, _book("0.6", "0.62"))).signal is \
        Signal.NO_TRADE
    now = INST.window_end - timedelta(seconds=300)
    held = FairProbabilityStrategy().decide(_snap(INST, now, ts, vals, _book("0.6", "0.62"), held_up=D(3)))
    assert held.signal is Signal.HOLD
