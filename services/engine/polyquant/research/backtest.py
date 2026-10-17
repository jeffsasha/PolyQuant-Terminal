"""Event-driven execution replay over recorded WebSocket books.

Uses exactly the paper engine's pure pieces (sweep, fee schedule, central risk gates) so replay and live paper share
fill and cost logic. Fills see the book state at decision time + profile latency, never the decision-time book.

Scope and honesty limits:
- Only windows with recorded full-depth books can be replayed. Before Phase 2b there is no executable price
  history, so earlier markets support probability calibration only, never PnL.
- IOC taker entries held to settlement (the baseline strategy's behaviour). Maker fills are not replayed here.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

import numpy as np

from polyquant.domain.models import Outcome, Phase
from polyquant.domain.timeutil import to_unix
from polyquant.fees.schedule import FeeSchedule, FeeScheduleUnknown, capped_taker_charge
from polyquant.marketdata.book import BookSnapshot
from polyquant.paper.execution import PROFILES, ExecutionProfile, instrument_px, outcome_ladders, outcome_mid, sweep
from polyquant.paper.models import Position
from polyquant.paper.risk import CentralRiskManager, RiskConfig, RiskContext
from polyquant.research.calibration import LabelledMarket
from polyquant.strategy.base import MarketSnapshot, PITInstrument, PointInTimeSeries, Signal, Strategy

ZERO = Decimal(0)


@dataclass
class ReplayTrade:
    slug: str
    horizon: str
    outcome: Outcome
    won: bool
    qty: Decimal
    requested: Decimal
    notional: Decimal
    fee: Decimal
    payout: Decimal
    decision_time: datetime
    p_model: float
    edge: float
    spread_cost: Decimal
    slippage: Decimal

    @property
    def net(self) -> Decimal:
        return self.payout - self.notional - self.fee

    @property
    def gross(self) -> Decimal:
        return self.payout - self.notional


@dataclass
class ReplayResult:
    profile: str
    strategy: str
    trades: list[ReplayTrade] = field(default_factory=list)
    markets_replayed: int = 0
    decisions: int = 0
    signals: int = 0
    risk_rejections: dict[str, int] = field(default_factory=dict)
    arrival_rejections: dict[str, int] = field(default_factory=dict)
    unfilled: int = 0


class BookTimeline:
    def __init__(self, books: list[BookSnapshot]) -> None:
        self.books = books
        self._t = [b.recv_at for b in books]

    def at(self, t: datetime) -> BookSnapshot | None:
        i = bisect_right(self._t, t) - 1
        return self.books[i] if i >= 0 else None

    @property
    def start(self) -> datetime | None:
        return self._t[0] if self._t else None

    @property
    def end(self) -> datetime | None:
        return self._t[-1] if self._t else None


def replay(markets: list[LabelledMarket], books: dict[str, BookTimeline], ts: np.ndarray, vals: np.ndarray,
           strategy: Strategy, profile: ExecutionProfile, *, risk_config: RiskConfig | None = None,
           fees: FeeSchedule | None = None, step_s: int = 5, book_stale_s: float = 30.0) -> ReplayResult:
    fees = fees or FeeSchedule()
    risk = CentralRiskManager(risk_config or RiskConfig())
    res = ReplayResult(profile=profile.name, strategy=strategy.name)
    equity = risk.config.starting_capital
    for m in sorted(markets, key=lambda x: x.inst.window_start):
        inst = m.inst
        tl = books.get(inst.slug)
        if tl is None or tl.start is None:
            continue
        res.markets_replayed += 1
        t = max(inst.window_start + timedelta(seconds=step_s), tl.start)
        while t < inst.window_end:
            book = tl.at(t)
            snap = MarketSnapshot(now=t, instrument=PITInstrument.from_instrument(inst, t),
                                  series=PointInTimeSeries(ts, vals, to_unix(t)), book=book)
            res.decisions += 1
            dec = strategy.decide(snap)
            if dec.signal in (Signal.BUY_UP, Signal.BUY_DOWN) and dec.intents:
                res.signals += 1
                intent = dec.intents[0]
                book_stale = book is None or (t - book.recv_at).total_seconds() > book_stale_s
                # replay of a single market: the WS-connection freshness proxy is this market's book age
                ctx = RiskContext(
                    now=t, instrument=inst, phase=Phase.OPEN, book=book, book_stale=book_stale, index_stale=False,
                    clock_alert=False, equity=equity, available_cash=equity, start_of_day_equity=equity,
                    positions=[], open_orders=[], attempts_this_market=0, loss_streak=0, cooldown_until=None,
                    halted=False, daily_halt=False,
                    preview=sweep(book, intent.outcome, intent.side, intent.qty, intent.limit_px,
                                  PROFILES[risk.config.gating_profile], tick=inst.tick_size or Decimal("0.01"),
                                  min_qty=inst.min_qty or Decimal("0.01")) if book else None,
                    preview_fee=ZERO, worst_fee=intent.qty * Decimal("0.0695") * Decimal("0.25") + Decimal("0.01"),
                    instrument_horizons={inst.slug: inst.horizon})
                decision = risk.check(intent, ctx)
                if not decision.approved:
                    for r in decision.reasons:
                        key = r.split(":")[0]
                        res.risk_rejections[key] = res.risk_rejections.get(key, 0) + 1
                else:
                    arrive = t + timedelta(milliseconds=profile.latency_ms)
                    if arrive >= inst.window_end:
                        res.arrival_rejections["window_closed"] = res.arrival_rejections.get("window_closed", 0) + 1
                        break
                    abook = tl.at(arrive)
                    if abook is None or (arrive - abook.recv_at).total_seconds() > book_stale_s:
                        res.arrival_rejections["stale_book"] = res.arrival_rejections.get("stale_book", 0) + 1
                    else:
                        trade = _fill(m, intent, abook, book, profile, fees, arrive, dec.p_up, dec.why)
                        if trade is None:
                            res.unfilled += 1
                        else:
                            res.trades.append(trade)
                            equity += trade.net
                        break  # one entry per market (held to settlement)
            t += timedelta(seconds=step_s)
    return res


def _fill(m: LabelledMarket, intent, abook: BookSnapshot, dbook: BookSnapshot | None, profile: ExecutionProfile,
          fees: FeeSchedule, at: datetime, p_up: float | None, why: dict) -> ReplayTrade | None:
    inst = m.inst
    r = sweep(abook, intent.outcome, intent.side, intent.qty, intent.limit_px, profile,
              tick=inst.tick_size or Decimal("0.01"), min_qty=inst.min_qty or Decimal("0.01"))
    if not r.fills:
        return None
    try:
        v = fees.version_at(at)
    except FeeScheduleUnknown:
        return None
    theta = max(v.taker_theta, inst.fee_coefficient or ZERO)
    cum, collected, fee = ZERO, ZERO, ZERO
    for f in r.fills:
        ipx = instrument_px(intent.outcome, f.px)
        charge, cum, collected = capped_taker_charge(theta * f.qty * ipx * (1 - ipx), cum, collected)
        fee += charge
    # cost attribution vs the decision-time book (what the strategy saw)
    spread_cost = slippage = ZERO
    if dbook is not None:
        _, asks = outcome_ladders(dbook, intent.outcome)
        mid = outcome_mid(dbook, intent.outcome)
        if asks and mid is not None:
            spread_cost = (asks[0].px - mid) * r.filled
            slippage = r.notional - asks[0].px * r.filled
    won = intent.outcome is m.outcome
    pos = Position(slug=inst.slug, outcome=intent.outcome, qty=r.filled, cost=r.notional)
    return ReplayTrade(slug=inst.slug, horizon=inst.horizon.value, outcome=intent.outcome, won=won, qty=pos.qty,
                       requested=intent.qty, notional=r.notional, fee=fee, payout=pos.qty if won else ZERO,
                       decision_time=at, p_model=float(p_up or 0), edge=float(why.get("edge", 0)),
                       spread_cost=spread_cost, slippage=slippage)


def report(res: ReplayResult, *, seed: int = 11, n_boot: int = 2000) -> dict:
    tr = res.trades
    nets = [float(t.net) for t in tr]
    gross_win = sum(n for n in nets if n > 0)
    gross_loss = -sum(n for n in nets if n < 0)
    cum = np.cumsum(nets) if nets else np.array([0.0])
    peak = np.maximum.accumulate(np.concatenate([[0.0], cum]))
    dd = float(np.max(peak - np.concatenate([[0.0], cum])))
    streak = best = 0
    for n in nets:
        streak = streak + 1 if n < 0 else 0
        best = max(best, streak)
    deployed = sum(float(t.notional + t.fee) for t in tr)
    ci = (float("nan"), float("nan"))
    if len(nets) >= 2:
        rng = np.random.default_rng(seed)
        arr = np.array(nets)
        means = [float(np.mean(arr[rng.integers(0, len(arr), len(arr))])) for _ in range(n_boot)]
        ci = (float(np.quantile(means, 0.05)), float(np.quantile(means, 0.95)))
    by_h: dict[str, dict] = {}
    for h in {t.horizon for t in tr}:
        sub = [float(t.net) for t in tr if t.horizon == h]
        by_h[h] = {"trades": len(sub), "net": sum(sub)}
    requested = sum(float(t.requested) for t in tr) + 0.0
    return {
        "profile": res.profile, "strategy": res.strategy, "markets_replayed": res.markets_replayed,
        "decisions": res.decisions, "signals": res.signals, "trades": len(tr),
        "independent_markets_traded": len({t.slug for t in tr}),
        "net_pnl": sum(nets), "gross_pnl": sum(float(t.gross) for t in tr), "fees": sum(float(t.fee) for t in tr),
        "spread_cost": sum(float(t.spread_cost) for t in tr), "slippage": sum(float(t.slippage) for t in tr),
        "roi_on_deployed": (sum(nets) / deployed) if deployed else None,
        "win_rate": (sum(1 for t in tr if t.won) / len(tr)) if tr else None,
        "profit_factor": (gross_win / gross_loss) if gross_loss else None,
        "ev_per_trade": (sum(nets) / len(tr)) if tr else None, "ev_per_trade_90ci": ci,
        "max_drawdown": dd, "max_losing_streak": best,
        "fill_rate": (sum(float(t.qty) for t in tr) / requested) if requested else None,
        "unfilled_signals": res.unfilled, "risk_rejections": res.risk_rejections,
        "arrival_rejections": res.arrival_rejections, "by_horizon": by_h,
        "sample_adequate": len({t.slug for t in tr}) >= 300,
    }
