"""Strategy B: fair probability that the official close (60 s average of BRTI at window_end − 1 s) is ≥ priceToBeat.

Model (interpretable baseline; docs/STRATEGY_RESEARCH.md §2):
- The observable series S̄ is the average of w = 60 per-second spot prices (discrete). Model spot as a driftless
  random walk with per-second variance σ². For a decision whose last visible point is S̄_t and target second T
  (τ = T − t), with m = min(w, τ), M = max(w, τ):
      Var(S̄_T − S̄_t) = σ²/w² · [ (m−1)m(2m−1)/3 + (M−m+1)m² ]
  (exact for the discrete window; continuous limit σ²(τ − w/3) for τ ≥ w. Verified by simulation in tests.)
- σ² is estimated from the *same smoothed series*, using non-overlapping lag-k differences (k ≥ w) and the same
  formula inverted. That corrects for the smoothing instead of underestimating vol from 1 s diffs.
- Optional MA-lag drift: when S̄ trends with slope b and spot then stays flat, the average keeps moving by
      E[S̄_T − S̄_t] = b (τ − τ(τ+1)/(2w)) for τ < w,  b(w−1)/2 for τ ≥ w   (exact, discrete).
- P(Up) = P(d + Δ ≥ 0), d = S̄_t − priceToBeat, with Δ Gaussian or Student-t (same variance).

Strategy A (external spot as a leading feature): instead of extrapolating the slope, use the actual external spot
path x (Kraken BTC/USD, a BRTI constituent). With future spot flat at x_t, the average's expected move is
    E[S̄_T − S̄_t] = x_t − mean(x_{t−w+1..t})                        for τ ≥ w
                 = (1/w) Σ_{u=t−w+1}^{t−w+τ} (x_t − x_u)             for τ < w
Only differences of x enter, so a constant Kraken–BRTI basis cancels.

Trading rule: buy the side whose model probability exceeds its all-in executable cost (conservative sweep incl.
fees) by at least `min_edge`. No claim of edge is made by this code; see the calibration report.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal

import numpy as np
from scipy import stats

from polyquant.domain.models import Outcome
from polyquant.domain.timeutil import to_unix
from polyquant.fees.schedule import FeeSchedule, FeeScheduleUnknown
from polyquant.paper.execution import PROFILES, instrument_px, sweep
from polyquant.paper.models import TIF, OrderIntent, Side
from polyquant.strategy.base import Decision, MarketSnapshot, Signal

W = 60.0  # averaging window of the official index, seconds


def _overlap_factor(tau: float, w: float = W) -> float:
    """Σ c_k² / w² for the change of a w-sample moving average over τ steps of a unit random walk."""
    if tau <= 0:
        return 0.0
    m, big = min(w, tau), max(w, tau)
    return ((m - 1) * m * (2 * m - 1) / 3.0 + (big - m + 1) * m * m) / (w * w)


def var_ma_change(tau: float, sigma2: float, w: float = W) -> float:
    return sigma2 * _overlap_factor(tau, w)


def drift_ma_change(tau: float, slope: float, w: float = W) -> float:
    if tau <= 0:
        return 0.0
    if tau >= w:
        return slope * (w - 1) / 2.0
    return slope * (tau - tau * (tau + 1) / (2.0 * w))


def spot_drift(x_path: np.ndarray, tau: float, w: int = int(W)) -> float:
    """Expected move of the w-sample average given the last w per-second spot values x_path (oldest first, last =
    current) and flat future spot. See module docstring."""
    if tau <= 0 or len(x_path) < w:
        return 0.0
    x = x_path[-w:]
    xt = x[-1]
    if tau >= w:
        return float(xt - np.mean(x))
    k = int(tau)
    return float(np.sum(xt - x[:k]) / w)


def forward_filled(ts: np.ndarray, vals: np.ndarray, start: int, end: int) -> np.ndarray | None:
    """Per-second values on [start, end] carrying the last trade forward; None if nothing at or before start."""
    if len(ts) == 0 or ts[0] > start:
        return None
    grid = np.arange(start, end + 1)
    idx = np.searchsorted(ts, grid, side="right") - 1
    return vals[idx]


def estimate_sigma2(values: np.ndarray, lag: int, w: float = W) -> float | None:
    """Per-second variance of spot from a 1 s series of the w-sample moving average (mean-zero estimator)."""
    if lag < w or len(values) <= 2 * lag:
        return None
    sampled = values[::lag]
    d = np.diff(sampled)
    if len(d) < 5:
        return None
    return float(np.mean(d * d) / _overlap_factor(lag, w))


@dataclass(frozen=True)
class ModelParams:
    lookback_s: int = 3600
    lag_s: int = 120
    dist: str = "gauss"  # gauss | t4
    drift_weight: float = 0.0  # 0 = driftless (B0), 1 = MA-lag drift (B1)
    drift_source: str = "slope"  # slope (Strategy B) | spot (Strategy A: external spot path)
    spot_max_age_s: int = 30  # external spot older than this at decision time → model unavailable
    slope_window_s: int = 30
    sigma_floor: float = 0.5  # $/sqrt(s) floor: avoids certainty from a quiet lookback
    p_clip: float = 0.001

    @property
    def name(self) -> str:
        src = "" if self.drift_source == "slope" else f"_{self.drift_source}"
        return f"L{self.lookback_s}_k{self.lag_s}_{self.dist}_drift{self.drift_weight:g}{src}"


@dataclass(frozen=True)
class ModelOutput:
    p_up: float
    d: float  # current distance S̄_t − priceToBeat
    tau: float
    sigma: float  # per-second vol estimate
    sd: float  # std of the remaining change
    drift: float


class FairProbabilityModel:
    def __init__(self, params: ModelParams | None = None) -> None:
        self.p = params or ModelParams()

    def predict(self, snap: MarketSnapshot) -> ModelOutput | None:
        inst = snap.instrument
        if inst.price_to_beat is None:
            return None
        latest = snap.series.latest()
        if latest is None:
            return None
        t_last, s_now = latest
        tau = float(inst.target_unix - t_last)
        if tau < 0:
            return None
        _, vals = snap.series.window(t_last - self.p.lookback_s, t_last)
        s2 = estimate_sigma2(vals, self.p.lag_s)
        if s2 is None:
            return None
        sigma = max(math.sqrt(s2), self.p.sigma_floor)
        sd = math.sqrt(var_ma_change(tau, sigma * sigma))
        drift = 0.0
        if self.p.drift_weight and self.p.drift_source == "spot":
            if snap.spot is None:
                return None
            sts, svals = snap.spot.window(t_last - 300, t_last)
            if len(sts) == 0 or t_last - int(sts[-1]) > self.p.spot_max_age_s:
                return None  # no fresh external spot: Strategy A is unavailable rather than silently degraded
            path = forward_filled(sts, svals, t_last - int(W) + 1, t_last)
            if path is None:
                return None
            drift = self.p.drift_weight * spot_drift(path, tau)
        elif self.p.drift_weight:
            past = snap.series.value_at(t_last - self.p.slope_window_s)
            if past is not None:
                drift = self.p.drift_weight * drift_ma_change(tau, (s_now - past) / self.p.slope_window_s)
        d = s_now - float(inst.price_to_beat)
        if sd <= 0:
            p = 1.0 if d + drift >= 0 else 0.0
        else:
            z = (d + drift) / sd
            if self.p.dist == "t4":
                nu = 4.0
                p = float(stats.t.cdf(z * math.sqrt(nu / (nu - 2.0)), df=nu))
            else:
                p = float(stats.norm.cdf(z))
        p = min(1 - self.p.p_clip, max(self.p.p_clip, p))
        return ModelOutput(p_up=p, d=d, tau=tau, sigma=sigma, sd=sd, drift=drift)


class FairProbabilityStrategy:
    """Buys the side with positive edge after conservative execution costs. One entry per market."""

    def __init__(self, model: FairProbabilityModel | None = None, *, min_edge: Decimal = Decimal("0.02"),
                 budget: Decimal = Decimal("4"), min_seconds_to_close: int = 60, gating_profile: str = "conservative",
                 fees: FeeSchedule | None = None) -> None:
        self.model = model or FairProbabilityModel()
        self.name = f"fair_prob[{self.model.p.name}]"
        self.min_edge = min_edge
        self.budget = budget
        self.min_seconds_to_close = min_seconds_to_close
        self.gating = PROFILES[gating_profile]
        self.fees = fees or FeeSchedule()

    def _all_in(self, snap: MarketSnapshot, outcome: Outcome, qty: Decimal) -> tuple[Decimal, Decimal] | None:
        book = snap.book
        r = sweep(book, outcome, Side.BUY, qty, Decimal("0.99"), self.gating, tick=snap.instrument.tick_size,
                  min_qty=snap.instrument.min_qty)
        if r.filled < qty or r.vwap is None:
            return None
        try:
            fee = sum((f.charged for f in self.fees.order_fills(
                [(f.qty, instrument_px(outcome, f.px)) for f in r.fills], snap.now, liquidity="taker",
                theta_override=snap.instrument.fee_coefficient)), Decimal(0))
        except FeeScheduleUnknown:
            return None
        worst_px = max(f.px for f in r.fills)
        return (r.notional + fee) / qty, worst_px

    def decide(self, snap: MarketSnapshot) -> Decision:
        out = self.model.predict(snap)
        if out is None:
            return Decision(Signal.NO_TRADE, None, why={"reason": "model_unavailable"})
        why = {"d": round(out.d, 2), "tau": out.tau, "sigma": round(out.sigma, 3), "sd": round(out.sd, 2),
               "drift": round(out.drift, 2), "p_up": round(out.p_up, 4)}
        secs_left = (snap.instrument.window_end - snap.now).total_seconds()
        if secs_left <= self.min_seconds_to_close:
            return Decision(Signal.NO_TRADE, out.p_up, why={**why, "reason": "too_close_to_settlement"})
        if snap.held_up > 0 or snap.held_down > 0:
            return Decision(Signal.HOLD, out.p_up, why={**why, "reason": "already_positioned"})
        if snap.book is None:
            return Decision(Signal.NO_TRADE, out.p_up, why={**why, "reason": "no_book"})
        best = None
        for outcome, p in ((Outcome.UP, out.p_up), (Outcome.DOWN, 1.0 - out.p_up)):
            asks = snap.book.offers if outcome is Outcome.UP else snap.book.down_asks()
            if not asks:
                continue
            # size on the expected fill price incl. the gating profile's adverse ticks, so the budget holds
            est_px = min(Decimal("0.99"), asks[0].px + snap.instrument.tick_size * self.gating.slippage_ticks)
            qty = (self.budget / est_px).quantize(snap.instrument.min_qty, rounding="ROUND_DOWN")
            if qty <= 0:
                continue
            cost = self._all_in(snap, outcome, qty)
            if cost is None:
                continue
            per, worst = cost
            edge = Decimal(str(round(p, 6))) - per
            why[f"edge_{outcome.value}"] = float(round(edge, 4))
            if edge >= self.min_edge and (best is None or edge > best[0]):
                best = (edge, outcome, qty, worst, p)
        if best is None:
            return Decision(Signal.NO_TRADE, out.p_up, why={**why, "reason": "no_edge_after_costs"})
        edge, outcome, qty, worst, p = best
        intent = OrderIntent(
            client_order_id=f"{self.name[:24]}-{snap.instrument.slug[-14:]}-{to_unix(snap.now)}",
            slug=snap.instrument.slug, outcome=outcome, side=Side.BUY, qty=qty, limit_px=worst, tif=TIF.IOC,
            strategy=self.name, model_prob=Decimal(str(round(p, 6))))
        sig = Signal.BUY_UP if outcome is Outcome.UP else Signal.BUY_DOWN
        return Decision(sig, out.p_up, (intent,), why={**why, "edge": float(edge)})
