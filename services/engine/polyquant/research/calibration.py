"""Probability calibration of the fair-probability model on public history, with leakage-safe evaluation.

Protocol (pre-registered in docs/STRATEGY_RESEARCH.md §6):
- Unit of independence: the market. Every checkpoint of a market lands in the same split.
- Chronological split by window start: development 60 %, validation 20 %, untouched test 20 %. Markets whose window
  straddles a cut are dropped (embargo), because 15m and 1h windows overlap in time.
- Variant selection uses the development set only. Validation is reported for all variants. The test set is
  evaluated once, for the selected variant only.
- Walk-forward: weekly folds; for each fold the variant is re-selected on all earlier markets only.
- Each prediction sees only data visible at its decision time (PointInTimeSeries / PITInstrument).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np

from polyquant.domain.models import Horizon, Instrument, Outcome
from polyquant.domain.timeutil import to_unix
from polyquant.strategy.base import MarketSnapshot, PITInstrument, PointInTimeSeries
from polyquant.strategy.fair_prob import FairProbabilityModel, ModelParams

CHECKPOINTS: dict[Horizon, tuple[int, ...]] = {  # seconds before window end
    Horizon.M15: (600, 300, 120, 60, 30),
    Horizon.H1: (3000, 1800, 900, 300, 60),
}


@dataclass(frozen=True, slots=True)
class Record:
    slug: str
    horizon: Horizon
    window_start: datetime
    seconds_left: int
    p: float
    y: int  # 1 = Up settled
    sigma: float
    d: float
    sd: float


@dataclass
class LabelledMarket:
    inst: Instrument
    outcome: Outcome


def label_markets(instruments: Iterable[Instrument]) -> tuple[list[LabelledMarket], dict]:
    """Resolved markets with an unambiguous label. Venue-declared result and price rule must agree."""
    out, stats_ = [], {"no_reference": 0, "unresolved": 0, "conflict": 0}
    for inst in instruments:
        if inst.price_to_beat is None or inst.settlement_price is None:
            stats_["unresolved" if inst.price_to_beat is not None else "no_reference"] += 1
            continue
        rule = inst.settled_outcome()
        if inst.venue_outcome is not None and inst.venue_outcome != rule:
            stats_["conflict"] += 1
            continue
        out.append(LabelledMarket(inst, rule))
    out.sort(key=lambda m: (m.inst.window_start, m.inst.horizon.value))
    return out, stats_


def chronological_split(markets: list[LabelledMarket], fractions=(0.6, 0.2, 0.2)) -> dict[str, list[LabelledMarket]]:
    if not markets:
        return {"dev": [], "val": [], "test": [], "embargoed": []}
    t0 = min(m.inst.window_start for m in markets)
    t1 = max(m.inst.window_end for m in markets)
    span = (t1 - t0).total_seconds()
    cut1 = t0 + timedelta(seconds=span * fractions[0])
    cut2 = t0 + timedelta(seconds=span * (fractions[0] + fractions[1]))
    parts: dict[str, list[LabelledMarket]] = {"dev": [], "val": [], "test": [], "embargoed": []}
    for m in markets:
        s, e = m.inst.window_start, m.inst.window_end
        if any(s < c < e for c in (cut1, cut2)):
            parts["embargoed"].append(m)
        elif e <= cut1:
            parts["dev"].append(m)
        elif e <= cut2:
            parts["val"].append(m)
        else:
            parts["test"].append(m)
    parts["_cuts"] = [cut1, cut2]  # type: ignore[assignment]
    return parts


def build_records(markets: list[LabelledMarket], ts: np.ndarray, vals: np.ndarray, params: ModelParams,
                  checkpoints: dict[Horizon, tuple[int, ...]] = CHECKPOINTS) -> tuple[list[Record], int]:
    model = FairProbabilityModel(params)
    recs: list[Record] = []
    skipped = 0
    for m in markets:
        inst = m.inst
        for left in checkpoints[inst.horizon]:
            now = inst.window_end - timedelta(seconds=left)
            if now <= inst.window_start:
                continue
            snap = MarketSnapshot(now=now, instrument=PITInstrument.from_instrument(inst, now),
                                  series=PointInTimeSeries(ts, vals, to_unix(now)))
            out = model.predict(snap)
            if out is None:
                skipped += 1
                continue
            recs.append(Record(inst.slug, inst.horizon, inst.window_start, left, out.p_up,
                               1 if m.outcome is Outcome.UP else 0, out.sigma, out.d, out.sd))
    return recs, skipped


# ---- metrics ------------------------------------------------------------------------------------------


def brier(recs: list[Record]) -> float:
    return float(np.mean([(r.p - r.y) ** 2 for r in recs])) if recs else float("nan")


def log_loss(recs: list[Record]) -> float:
    if not recs:
        return float("nan")
    return float(np.mean([-(math.log(r.p) if r.y else math.log(1 - r.p)) for r in recs]))


def reliability(recs: list[Record], bins: int = 10) -> list[dict]:
    out = []
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        sel = [r for r in recs if lo <= r.p < hi or (b == bins - 1 and r.p == 1.0)]
        out.append({"bin": f"{lo:.1f}-{hi:.1f}", "n": len(sel),
                    "mean_p": float(np.mean([r.p for r in sel])) if sel else None,
                    "freq_up": float(np.mean([r.y for r in sel])) if sel else None})
    return out


def ece(recs: list[Record], bins: int = 10) -> float:
    n = len(recs)
    if not n:
        return float("nan")
    return float(sum(b["n"] / n * abs(b["mean_p"] - b["freq_up"]) for b in reliability(recs, bins) if b["n"]))


def summary(recs: list[Record]) -> dict:
    base = float(np.mean([r.y for r in recs])) if recs else float("nan")
    const = [Record(r.slug, r.horizon, r.window_start, r.seconds_left, 0.5, r.y, r.sigma, r.d, r.sd) for r in recs]
    return {"n_predictions": len(recs), "n_markets": len({r.slug for r in recs}), "base_rate_up": base,
            "brier": brier(recs), "log_loss": log_loss(recs), "ece": ece(recs),
            "brier_coinflip": brier(const), "log_loss_coinflip": log_loss(const)}


def bootstrap_ci(recs: list[Record], stat: Callable[[list[Record]], float], *, n: int = 1000, seed: int = 7,
                 alpha: float = 0.10) -> tuple[float, float]:
    """Percentile CI, resampling whole markets (block bootstrap by market)."""
    by: dict[str, list[Record]] = {}
    for r in recs:
        by.setdefault(r.slug, []).append(r)
    keys = list(by)
    if not keys:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n):
        pick = rng.integers(0, len(keys), len(keys))
        sample = [r for i in pick for r in by[keys[i]]]
        vals.append(stat(sample))
    return float(np.quantile(vals, alpha / 2)), float(np.quantile(vals, 1 - alpha / 2))


def logloss_improvement(recs: list[Record]) -> float:
    """Coin-flip log loss minus model log loss (positive = model better)."""
    return math.log(2) - log_loss(recs)


# ---- selection and walk-forward ----------------------------------------------------------------------


@dataclass
class VariantResult:
    params: ModelParams
    dev: dict = field(default_factory=dict)
    val: dict = field(default_factory=dict)


def select_variant(dev_records: dict[str, list[Record]]) -> str:
    """Lowest development log loss. Takes development records only (the test set is not passed in)."""
    return min(dev_records, key=lambda k: log_loss(dev_records[k]))


def weekly_folds(markets: list[LabelledMarket]) -> list[list[LabelledMarket]]:
    if not markets:
        return []
    start = min(m.inst.window_start for m in markets)
    folds: dict[int, list[LabelledMarket]] = {}
    for m in markets:
        folds.setdefault(int((m.inst.window_start - start).total_seconds() // (7 * 86400)), []).append(m)
    return [folds[k] for k in sorted(folds)]


def walk_forward(markets: list[LabelledMarket], ts: np.ndarray, vals: np.ndarray,
                 variants: list[ModelParams]) -> list[dict]:
    """For fold k ≥ 1: select on markets that ended before fold k starts, then evaluate on fold k."""
    folds = weekly_folds(markets)
    results = []
    for k in range(1, len(folds)):
        fold_start = min(m.inst.window_start for m in folds[k])
        history = [m for f in folds[:k] for m in f if m.inst.window_end <= fold_start]
        dev = {v.name: build_records(history, ts, vals, v)[0] for v in variants}
        chosen = select_variant(dev)
        params = next(v for v in variants if v.name == chosen)
        test, _ = build_records(folds[k], ts, vals, params)
        results.append({"fold": k, "fold_start": fold_start.isoformat(), "selected": chosen,
                        "train_markets": len(history), **summary(test)})
    return results
