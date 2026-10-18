from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D

import httpx
import numpy as np
import pytest

from polyquant.clock import FakeClock
from polyquant.domain.timeutil import to_unix
from polyquant.spot.kraken import ForbiddenSpotRequest, KrakenRest, KrakenTradeStream, Trade, aggregate, backfill
from polyquant.strategy.base import LookaheadError, MarketSnapshot, PITInstrument, PointInTimeSeries
from polyquant.strategy.fair_prob import FairProbabilityModel, ModelParams, forward_filled, spot_drift
from polyquant.venue.parsing import parse_instrument
from tests.conftest import load, utc

W = 60


def ma(x, w=W):
    c = np.cumsum(np.concatenate([[0.0], x]))
    return (c[w:] - c[:-w]) / w


# ---- formula ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize("tau", [1, 10, 30, 59, 60, 61, 300])
def test_spot_drift_equals_exact_ma_change_with_flat_future(tau):
    rng = np.random.default_rng(5)
    past = 81000 + np.cumsum(rng.normal(0, 3, 200))  # arbitrary observed spot path up to t
    path = np.concatenate([past, np.full(tau + 2, past[-1])])  # flat future
    m = ma(path)
    t_idx = len(past) - W  # ma index whose window ends at the last observed second
    exact = m[t_idx + tau] - m[t_idx]
    assert spot_drift(past[-W:], tau) == pytest.approx(exact, abs=1e-7)  # float cumsum error at $81k level


def test_spot_drift_cancels_constant_basis():
    rng = np.random.default_rng(6)
    x = 81000 + np.cumsum(rng.normal(0, 3, W))
    assert spot_drift(x + 37.5, 120) == pytest.approx(spot_drift(x, 120))
    assert spot_drift(x + 37.5, 20) == pytest.approx(spot_drift(x, 20))


def test_forward_fill_carries_last_trade():
    ts = np.array([100, 103, 110], dtype=np.int64)
    v = np.array([1.0, 2.0, 3.0])
    assert forward_filled(ts, v, 100, 111).tolist() == [1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 3, 3]
    assert forward_filled(ts, v, 99, 105) is None  # nothing known at the start


# ---- model A behaviour ------------------------------------------------------------------------------------

INST = parse_instrument(load("market_15m_open.json"))


def series(inst, level, seed=8):
    rng = np.random.default_rng(seed)
    start, end = to_unix(inst.window_start) - 4 * 3600, to_unix(inst.window_end) + 120
    ts = np.arange(start, end, dtype=np.int64)
    spot = level + np.cumsum(rng.normal(0, 2, len(ts) + W - 1))
    return ts, ma(spot)[: len(ts)], spot[W - 1:]


def snap(inst, now, ts, vals, sts=None, svals=None):
    return MarketSnapshot(now=now, instrument=PITInstrument.from_instrument(inst, now),
                          series=PointInTimeSeries(ts, vals, to_unix(now)),
                          spot=None if sts is None else PointInTimeSeries(sts, svals, to_unix(now)))


A = ModelParams(lookback_s=7200, dist="t4", drift_weight=1.0, drift_source="spot")


def test_model_a_unavailable_without_fresh_spot():
    ts, vals, spot = series(INST, 81000)
    now = INST.window_end - timedelta(seconds=300)
    assert FairProbabilityModel(A).predict(snap(INST, now, ts, vals)) is None  # no spot at all
    stale_ts = ts[ts < to_unix(now) - 120]
    stale = FairProbabilityModel(A).predict(snap(INST, now, ts, vals, stale_ts, spot[: len(stale_ts)]))
    assert stale is None  # last trade 2 min old → unavailable, never silently falls back to B


def test_model_a_moves_probability_with_spot_lead():
    ts, vals, spot = series(INST, 81000)
    now = INST.window_end - timedelta(seconds=300)
    inst = replace(INST, price_to_beat=D(str(round(float(vals[np.searchsorted(ts, to_unix(now) - 1)]), 2))))
    base = FairProbabilityModel(A).predict(snap(inst, now, ts, vals, ts, spot))
    lead = spot.copy()
    cut = int(np.searchsorted(ts, to_unix(now) - 1))
    lead[cut - 10: cut + 1] += 40  # spot jumped $40 in the last 10 s; the average has barely moved
    higher = FairProbabilityModel(A).predict(snap(inst, now, ts, vals, ts, lead))
    assert higher.drift > base.drift + 5 and higher.p_up > base.p_up


def test_model_a_cannot_see_future_spot():
    ts, vals, spot = series(INST, 81000)
    now = INST.window_end - timedelta(seconds=300)
    s = PointInTimeSeries(ts, spot, to_unix(now))
    with pytest.raises(LookaheadError):
        s.window(to_unix(now) - 10, to_unix(now) + 5)
    cut = int(np.searchsorted(ts, to_unix(now) - 1, side="right"))
    noisy = spot.copy()
    noisy[cut:] = 1e9
    a = FairProbabilityModel(A).predict(snap(INST, now, ts, vals, ts, spot))
    b = FairProbabilityModel(A).predict(snap(INST, now, ts, vals, ts, noisy))
    assert a == b


# ---- Kraken feed ------------------------------------------------------------------------------------------


def tr(sec, frac, px, qty="0.1"):
    return Trade(datetime.fromtimestamp(sec + frac, UTC), D(px), D(qty), None)


def test_aggregate_groups_by_trade_second():
    bars = aggregate([tr(100, 0.1, "10"), tr(100, 0.9, "12"), tr(102, 0.5, "11")], utc(2026, 1, 1))
    assert [(int(b.ts.timestamp()), b.first_px, b.last_px, b.high_px, b.low_px, b.n_trades) for b in bars] == [
        (100, D(10), D(12), D(12), D(10), 2), (102, D(11), D(11), D(11), D(11), 1)]


async def test_backfill_pages_and_never_splits_a_second():
    pages = {
        "1000000000000": ([tr(1000, .1, "1"), tr(1000, .5, "2"), tr(1001, .2, "3")], 1001_200_000_000),
        "1001200000000": ([tr(1001, .2, "3"), tr(1001, .8, "4"), tr(1003, .1, "5")], 1003_100_000_000),
        "1003100000000": ([], 1003_100_000_000),
    }

    class FakeRest:
        async def trades_since(self, since_ns):
            return pages[str(since_ns)]

    out = []
    n = await backfill(FakeRest(), out.extend, since=datetime.fromtimestamp(1000, UTC),
                       until=datetime.fromtimestamp(1010, UTC))
    by_sec = {int(b.ts.timestamp()): b for b in out}
    assert sorted(by_sec) == [1000, 1001, 1003] and n >= 2
    # second 1001 straddled a page boundary: emitted once, with its true last trade
    assert by_sec[1001].last_px == D(4)
    assert len([b for b in out if int(b.ts.timestamp()) == 1001]) == 1


def test_stream_emits_completed_seconds_and_ignores_snapshot():
    clock = FakeClock(utc(2026, 10, 17, 12, 0, 0))
    got, events = [], []
    s = KrakenTradeStream(got.extend, lambda k, d: events.append(k), clock)
    snap_msg = {"channel": "trade", "type": "snapshot", "data": [
        {"symbol": "BTC/USD", "price": 1, "qty": 1, "timestamp": "2026-10-17T11:59:00.000000Z"}]}
    s.handle(snap_msg)
    upd = lambda ts, px: {"channel": "trade", "type": "update", "data": [  # noqa: E731
        {"symbol": "BTC/USD", "side": "buy", "price": px, "qty": 0.01, "trade_id": 1, "timestamp": ts}]}
    s.handle(upd("2026-10-17T12:00:00.100000Z", 81000.5))
    s.handle(upd("2026-10-17T12:00:00.900000Z", 81001.0))
    assert got == []  # second 12:00:00 still open
    s.handle(upd("2026-10-17T12:00:01.200000Z", 81002.0))
    assert len(got) == 1 and got[0].last_px == D("81001.0") and got[0].n_trades == 2
    clock.set(utc(2026, 10, 17, 12, 0, 4))
    s.tick()  # quiet market: 12:00:01 flushed after 2 s
    assert len(got) == 2 and got[1].last_px == D("81002.0")
    assert s.trades == 3  # snapshot trades were not counted


async def test_kraken_rest_is_get_only_and_host_locked():
    rest = KrakenRest(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"error": [], "result": {}})))
    rest._http.base_url = httpx.URL("https://evil.example.com")
    with pytest.raises(ForbiddenSpotRequest):
        await rest.get("/0/public/Trades", {})
    await rest.aclose()
