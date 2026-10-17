"""End-to-end research runs: calibration (public history) and execution replay (recorded books). Writes reports."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

from polyquant.domain.models import Outcome
from polyquant.paper.execution import PROFILES, outcome_mid
from polyquant.research.backtest import BookTimeline, replay, report
from polyquant.research.calibration import (
    CHECKPOINTS,
    Record,
    bootstrap_ci,
    build_records,
    chronological_split,
    label_markets,
    logloss_improvement,
    reliability,
    select_variant,
    summary,
    walk_forward,
)
from polyquant.research.data import book_coverage, load_books, load_index, load_instruments
from polyquant.strategy.fair_prob import FairProbabilityModel, FairProbabilityStrategy, ModelParams

VARIANTS = [ModelParams(lookback_s=L, dist=d, drift_weight=w)
            for L in (1800, 3600, 7200) for d in ("gauss", "t4") for w in (0.0, 1.0)]


def _f(x, nd=4):
    return "—" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{nd}f}"


async def run_calibration(pool, out_dir: Path) -> dict:
    instruments = await load_instruments(pool, until=datetime.now(UTC) - timedelta(minutes=5))
    markets, label_stats = label_markets(instruments)
    parts = chronological_split(markets)
    t0 = min(m.inst.window_start for m in markets) - timedelta(hours=3)
    ts, vals = await load_index(pool, start=t0)
    gaps = int(np.sum(np.diff(ts) > 1)) if len(ts) > 1 else 0

    dev = {v.name: build_records(parts["dev"], ts, vals, v)[0] for v in VARIANTS}
    val = {v.name: build_records(parts["val"], ts, vals, v)[0] for v in VARIANTS}
    chosen = select_variant(dev)  # development data only
    params = next(v for v in VARIANTS if v.name == chosen)
    test, skipped = build_records(parts["test"], ts, vals, params)  # evaluated once

    # vol regimes defined on development data only
    dev_sig = np.array([r.sigma for r in dev[chosen]])
    q1, q2 = (float(np.quantile(dev_sig, 1 / 3)), float(np.quantile(dev_sig, 2 / 3))) if len(dev_sig) else (0, 0)

    def regime(r: Record) -> str:
        return "low" if r.sigma < q1 else ("mid" if r.sigma < q2 else "high")

    breakdown = {
        "by_horizon": {h.value: summary([r for r in test if r.horizon == h]) for h in CHECKPOINTS},
        "by_seconds_left": {f"{r_h.value}:{s}": summary([r for r in test if r.horizon == r_h and r.seconds_left == s])
                            for r_h, ss in CHECKPOINTS.items() for s in ss},
        "by_vol_regime": {g: summary([r for r in test if regime(r) == g]) for g in ("low", "mid", "high")},
    }
    wf = walk_forward(markets, ts, vals, VARIANTS)
    market_cmp = await _market_comparison(pool, markets, ts, vals, params)

    result = {
        "generated_at": datetime.now(UTC).isoformat(),
        "data": {"instruments": len(instruments), "labelled_markets": len(markets), **label_stats,
                 "index_points": int(len(ts)), "index_gaps": gaps,
                 "first_window": markets[0].inst.window_start.isoformat() if markets else None,
                 "last_window": markets[-1].inst.window_start.isoformat() if markets else None,
                 "split_markets": {k: len(v) for k, v in parts.items() if not k.startswith("_")},
                 "cuts": [c.isoformat() for c in parts.get("_cuts", [])]},
        "selected_variant": chosen,
        "variants": {k: {"dev": summary(dev[k]), "val": summary(val[k])} for k in dev},
        "test": {**summary(test), "skipped_predictions": skipped,
                 "logloss_improvement_vs_coinflip": logloss_improvement(test),
                 "logloss_improvement_90ci": bootstrap_ci(test, logloss_improvement),
                 "reliability": reliability(test)},
        "breakdown": breakdown, "vol_regime_cuts": [q1, q2], "walk_forward": wf, "market_comparison": market_cmp,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "calibration.json").write_text(json.dumps(result, indent=1, default=str))
    (out_dir / "calibration.md").write_text(_calibration_md(result))
    return result


async def _market_comparison(pool, markets, ts, vals, params: ModelParams) -> dict:
    """Model vs market-implied mid on decision points where a recorded WS book exists. Tiny sample, labelled so."""
    cover = {c["slug"]: c for c in await book_coverage(pool)}
    model_recs, market_recs = [], []
    for m in markets:
        if m.inst.slug not in cover:
            continue
        tl = BookTimeline(await load_books(pool, m.inst.slug))
        recs, _ = build_records([m], ts, vals, params)
        for r in recs:
            t = m.inst.window_end - timedelta(seconds=r.seconds_left)
            b = tl.at(t)
            if b is None or (t - b.recv_at).total_seconds() > 30:
                continue
            mid = outcome_mid(b, Outcome.UP)
            if mid is None:
                continue
            p_mkt = min(0.999, max(0.001, float(mid)))
            model_recs.append(r)
            market_recs.append(Record(r.slug, r.horizon, r.window_start, r.seconds_left, p_mkt, r.y, r.sigma, r.d,
                                      r.sd))
    return {"n_predictions": len(model_recs), "n_markets": len({r.slug for r in model_recs}),
            "model": summary(model_recs) if model_recs else None,
            "market_mid": summary(market_recs) if market_recs else None,
            "note": "sample far too small for conclusions; recorded books exist only since 2026-10-17"}


def _calibration_md(r: dict) -> str:
    d, t = r["data"], r["test"]
    lines = [
        "# Phase 4 — Fair-probability calibration report", "",
        f"Generated {r['generated_at']}. Data: {d['labelled_markets']} labelled BTC up/down markets "
        f"({d['first_window']} → {d['last_window']}), {d['index_points']:,} official 1 s index points "
        f"({d['index_gaps']} gaps). Excluded: no reference {d['no_reference']}, unresolved {d['unresolved']}, "
        f"label conflicts {d['conflict']}.", "",
        f"Split (chronological, embargoed): {d['split_markets']}. Cuts: {d['cuts']}.", "",
        "## Variant selection (development set only; validation shown for transparency)", "",
        "| variant | dev log loss | dev Brier | val log loss | val Brier | val ECE |", "|---|---|---|---|---|---|",
    ]
    for k, v in sorted(r["variants"].items(), key=lambda kv: kv[1]["dev"]["log_loss"]):
        mark = " **(selected)**" if k == r["selected_variant"] else ""
        lines.append(f"| {k}{mark} | {_f(v['dev']['log_loss'])} | {_f(v['dev']['brier'])} | "
                     f"{_f(v['val']['log_loss'])} | {_f(v['val']['brier'])} | {_f(v['val']['ece'])} |")
    lo, hi = t["logloss_improvement_90ci"]
    lines += [
        "", "## Untouched test set (selected variant, evaluated once)", "",
        f"- Predictions: {t['n_predictions']} across {t['n_markets']} markets (skipped: {t['skipped_predictions']})",
        f"- Base rate Up: {_f(t['base_rate_up'], 3)}",
        f"- **Log loss {_f(t['log_loss'])}** vs coin-flip {_f(t['log_loss_coinflip'])}; "
        f"improvement {_f(t['logloss_improvement_vs_coinflip'])} (90 % market-block bootstrap CI {_f(lo)} … {_f(hi)})",
        f"- **Brier {_f(t['brier'])}** vs coin-flip {_f(t['brier_coinflip'])}; ECE {_f(t['ece'])}", "",
        "### Reliability (test)", "", "| p bin | n | mean p | observed Up freq |", "|---|---|---|---|",
    ]
    for b in t["reliability"]:
        lines.append(f"| {b['bin']} | {b['n']} | {_f(b['mean_p'], 3)} | {_f(b['freq_up'], 3)} |")
    lines += ["", "### Test breakdown", "", "| slice | n | log loss | Brier | ECE |", "|---|---|---|---|---|"]
    for group, items in r["breakdown"].items():
        for k, s in items.items():
            lines.append(f"| {group}: {k} | {s['n_predictions']} | {_f(s['log_loss'])} | {_f(s['brier'])} | "
                         f"{_f(s['ece'])} |")
    lines += ["", "## Walk-forward (weekly folds; variant re-selected on prior data only)", "",
              "| fold | start | selected | train markets | n | log loss | coin-flip | Brier |",
              "|---|---|---|---|---|---|---|---|"]
    for f in r["walk_forward"]:
        lines.append(f"| {f['fold']} | {f['fold_start'][:10]} | {f['selected']} | {f['train_markets']} | "
                     f"{f['n_predictions']} | {_f(f['log_loss'])} | {_f(f['log_loss_coinflip'])} | {_f(f['brier'])} |")
    mc = r["market_comparison"]
    lines += ["", "## Model vs market mid (recorded books only)", ""]
    if mc["model"]:
        lines += [f"{mc['n_predictions']} decision points across {mc['n_markets']} markets — {mc['note']}.", "",
                  "| | log loss | Brier |", "|---|---|---|",
                  f"| model | {_f(mc['model']['log_loss'])} | {_f(mc['model']['brier'])} |",
                  f"| market mid | {_f(mc['market_mid']['log_loss'])} | {_f(mc['market_mid']['brier'])} |"]
    else:
        lines.append("No decision points with recorded books.")
    lines += ["", "## Interpretation limits", "",
              "- Calibration says how well the model predicts the *official index rule*; it says nothing about "
              "profitability until compared with executable prices after costs (see backtest report).",
              "- Checkpoints within a market are correlated; CIs resample whole markets.",
              "- About 3.5 weeks of history; one volatility environment. Results may not transfer."]
    return "\n".join(lines) + "\n"


async def run_backtest(pool, out_dir: Path, params: ModelParams | None = None) -> dict:
    instruments = await load_instruments(pool, until=datetime.now(UTC) - timedelta(minutes=5))
    markets, _ = label_markets(instruments)
    cover = {c["slug"] for c in await book_coverage(pool)}
    markets = [m for m in markets if m.inst.slug in cover]
    if not markets:
        return {"error": "no resolved markets with recorded books"}
    t0 = min(m.inst.window_start for m in markets) - timedelta(hours=3)
    ts, vals = await load_index(pool, start=t0)
    books = {m.inst.slug: BookTimeline(await load_books(pool, m.inst.slug)) for m in markets}
    if params is None:
        cal = out_dir / "calibration.json"
        chosen = json.loads(cal.read_text())["selected_variant"] if cal.exists() else ModelParams().name
        params = next((v for v in VARIANTS if v.name == chosen), ModelParams())
    reports = {}
    for name, prof in PROFILES.items():
        strat = FairProbabilityStrategy(FairProbabilityModel(params))
        reports[name] = report(replay(markets, books, ts, vals, strat, prof))
    result = {"generated_at": datetime.now(UTC).isoformat(), "variant": params.name,
              "markets_with_books": len(markets), "profiles": reports}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "backtest.json").write_text(json.dumps(result, indent=1, default=str))
    (out_dir / "backtest.md").write_text(_backtest_md(result))
    return result


def _backtest_md(r: dict) -> str:
    lines = ["# Phase 4 — Execution replay (recorded WS books)", "",
             f"Generated {r['generated_at']}. Strategy fair_prob[{r['variant']}], IOC entries held to settlement, "
             f"min edge 0.02 after conservative costs. Resolved markets with recorded books: "
             f"{r['markets_with_books']}.", "",
             "**Sample warning:** recorded books exist only since 2026-10-17. Results below are a pipeline check, "
             "not evidence of edge (gate: ≥ 300 independent markets out of sample).", "",
             "| profile | markets | signals | trades | net PnL | gross | fees | slippage | win rate | EV/trade "
             "(90 % CI) | max DD | fill rate |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for name, p in r["profiles"].items():
        lo, hi = p["ev_per_trade_90ci"]
        tag = " (diagnostic)" if name == "optimistic" else ""
        lines.append(f"| {name}{tag} | {p['markets_replayed']} | {p['signals']} | {p['trades']} | "
                     f"{_f(p['net_pnl'], 2)} | {_f(p['gross_pnl'], 2)} | {_f(p['fees'], 2)} | {_f(p['slippage'], 2)} | "
                     f"{_f(p['win_rate'], 2)} | {_f(p['ev_per_trade'], 3)} ({_f(lo, 3)} … {_f(hi, 3)}) | "
                     f"{_f(p['max_drawdown'], 2)} | {_f(p['fill_rate'], 2)} |")
    lines += ["", "Risk rejections / arrival rejections per profile:", ""]
    for name, p in r["profiles"].items():
        lines.append(f"- {name}: risk {p['risk_rejections']}, arrival {p['arrival_rejections']}, "
                     f"unfilled {p['unfilled_signals']}")
    return "\n".join(lines) + "\n"
