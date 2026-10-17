"""Central, strategy-independent risk engine. Every order intent passes here before it can reserve capital.

Binary contracts lose at most the premium, so per-trade "risk" is max loss = qty × limit price + worst-case fee,
not a stop distance. Defaults are research defaults from the spec, not proven-optimal parameters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from polyquant.domain.models import Horizon, Instrument, Outcome, Phase
from polyquant.marketdata.book import BookSnapshot
from polyquant.paper.execution import SweepResult
from polyquant.paper.models import OrderIntent, PaperOrder, Position, RiskDecision, Side

ZERO = Decimal(0)
ONE = Decimal(1)


@dataclass(frozen=True)
class RiskConfig:
    starting_capital: Decimal = Decimal("1000")
    max_trade_risk_pct: Decimal = Decimal("0.5")  # % of equity
    max_exposure_pct: Decimal = Decimal("5")  # combined BTC exposure, % of equity
    horizon_exposure_pct: dict = field(default_factory=lambda: {Horizon.M15: Decimal("3"), Horizon.H1: Decimal("3")})
    max_daily_loss_pct: Decimal = Decimal("2")  # % of start-of-day equity
    max_open_positions: int = 2
    no_entry_before_close_s: dict = field(default_factory=lambda: {Horizon.M15: 60, Horizon.H1: 120})
    no_entry_after_open_s: int = 0  # optional: avoid the first seconds of a window
    max_spread: Decimal = Decimal("0.05")
    min_fill_ratio: Decimal = Decimal("1.0")  # IOC entries must be fully fillable under the gating profile
    min_edge: Decimal = Decimal("0.01")  # per contract, after fees and the gating profile's slippage
    max_attempts_per_market: int = 5
    loss_streak_for_cooldown: int = 3
    cooldown_s: int = 1800
    min_qty: Decimal = Decimal("0.01")
    gating_profile: str = "conservative"  # liquidity/edge checks use the conservative sweep


@dataclass
class RiskContext:
    now: datetime
    instrument: Instrument | None
    phase: Phase | None
    book: BookSnapshot | None
    book_stale: bool
    index_stale: bool
    clock_alert: bool
    equity: Decimal
    available_cash: Decimal
    start_of_day_equity: Decimal
    positions: list[Position]
    open_orders: list[PaperOrder]
    attempts_this_market: int
    loss_streak: int
    cooldown_until: datetime | None
    halted: bool  # manual kill switch
    daily_halt: bool  # daily-loss kill switch for today
    preview: SweepResult | None  # gating-profile sweep for the intent
    preview_fee: Decimal  # rounded taker fee for the preview fills
    worst_fee: Decimal  # taker fee bound at the limit for the full qty
    instrument_horizons: dict[str, Horizon] = field(default_factory=dict)  # slug -> horizon for exposure split


class CentralRiskManager:
    def __init__(self, config: RiskConfig | None = None) -> None:
        self.config = config or RiskConfig()

    def check(self, intent: OrderIntent, ctx: RiskContext) -> RiskDecision:
        c = self.config
        reasons: list[str] = []
        details: dict = {}
        inst = ctx.instrument
        is_exit = intent.side is Side.SELL

        # ---- input validation ----------------------------------------------------------------------
        if intent.qty <= 0 or intent.qty % c.min_qty != 0:
            reasons.append(f"invalid_qty:{intent.qty}")
        if not (ZERO < intent.limit_px < ONE):
            reasons.append(f"invalid_price:{intent.limit_px}")
        elif inst is not None and inst.tick_size and intent.limit_px % inst.tick_size != 0:
            reasons.append(f"price_not_on_tick:{intent.limit_px}")
        if intent.model_prob is not None and not (ZERO <= intent.model_prob <= ONE):
            reasons.append("invalid_model_prob")

        # ---- market state and data quality (apply to exits too: no fills against unknown state) ----
        if inst is None:
            reasons.append("unknown_market")
        else:
            if ctx.phase is not Phase.OPEN:
                reasons.append(f"market_not_open:{ctx.phase}")
            secs_left = (inst.window_end - ctx.now).total_seconds()
            details["seconds_to_close"] = secs_left
            if not is_exit and secs_left <= c.no_entry_before_close_s.get(inst.horizon, 60):
                reasons.append(f"no_entry_window:{int(secs_left)}s_to_close")
            if not is_exit and (ctx.now - inst.window_start).total_seconds() < c.no_entry_after_open_s:
                reasons.append("no_entry_after_open")
            if not is_exit and intent.requires_reference and inst.price_to_beat is None:
                reasons.append("reference_unavailable")
        if ctx.book is None or ctx.book_stale:
            reasons.append("book_stale_or_missing")
        if not is_exit and ctx.index_stale:
            reasons.append("index_stale")
        if ctx.clock_alert:
            reasons.append("clock_skew_high")

        # ---- halts ------------------------------------------------------------------------------------
        if not is_exit:
            if ctx.halted:
                reasons.append("kill_switch_on")
            if ctx.daily_halt:
                reasons.append("daily_loss_halt")
            if ctx.cooldown_until is not None and ctx.now < ctx.cooldown_until:
                reasons.append(f"loss_cooldown_until:{ctx.cooldown_until.isoformat()}")
            daily_loss = ctx.start_of_day_equity - ctx.equity
            details["daily_loss"] = str(daily_loss)
            if daily_loss >= ctx.start_of_day_equity * c.max_daily_loss_pct / 100:
                reasons.append("daily_loss_limit_reached")

        # ---- duplicates and attempts --------------------------------------------------------------
        same = [o for o in ctx.open_orders if o.intent.slug == intent.slug and o.intent.outcome == intent.outcome
                and o.intent.side == intent.side and not o.terminal]
        if same:
            reasons.append(f"duplicate_open_order:{same[0].id}")
        if not is_exit and ctx.attempts_this_market >= c.max_attempts_per_market:
            reasons.append("max_attempts_per_market")

        # ---- positions ----------------------------------------------------------------------------
        held = {(p.slug, p.outcome): p for p in ctx.positions if p.qty > 0}
        if is_exit:
            pos = held.get((intent.slug, intent.outcome))
            pending_sells = sum((o.remaining for o in ctx.open_orders if o.intent.slug == intent.slug
                                 and o.intent.outcome == intent.outcome and o.intent.side is Side.SELL
                                 and not o.terminal), ZERO)
            if pos is None or pos.qty - pending_sells < intent.qty:
                reasons.append("sell_exceeds_position")  # no naked short sales
        else:
            other = Outcome.DOWN if intent.outcome is Outcome.UP else Outcome.UP
            if (intent.slug, other) in held:
                reasons.append("opposite_side_held")  # avoids long/short netting semantics (unverified)
            open_slugs = {p.slug for p in held.values()} | {o.intent.slug for o in ctx.open_orders
                                                            if not o.terminal and o.intent.side is Side.BUY}
            if intent.slug not in open_slugs and len(open_slugs) >= c.max_open_positions:
                reasons.append("max_open_positions")

        # ---- capital and exposure (entries) -------------------------------------------------------
        if not is_exit:
            max_loss = intent.qty * intent.limit_px + ctx.worst_fee
            details["max_loss"] = str(max_loss)
            if max_loss > ctx.available_cash:
                reasons.append("insufficient_capital")
            if max_loss > ctx.equity * c.max_trade_risk_pct / 100:
                reasons.append(f"trade_risk_exceeds_{c.max_trade_risk_pct}%")
            exposure = sum((p.cost for p in held.values()), ZERO) + sum(
                (o.reserved for o in ctx.open_orders if not o.terminal and o.intent.side is Side.BUY), ZERO)
            details["exposure_before"] = str(exposure)
            if exposure + max_loss > ctx.equity * c.max_exposure_pct / 100:
                reasons.append(f"exposure_exceeds_{c.max_exposure_pct}%")
            if inst is not None:
                hz = inst.horizon
                hz_exp = sum((p.cost for p in held.values() if ctx.instrument_horizons.get(p.slug) == hz), ZERO) + \
                    sum((o.reserved for o in ctx.open_orders if not o.terminal and o.intent.side is Side.BUY
                         and ctx.instrument_horizons.get(o.intent.slug) == hz), ZERO)
                lim = c.horizon_exposure_pct.get(hz)
                if lim is not None and hz_exp + max_loss > ctx.equity * lim / 100:
                    reasons.append(f"{hz.value}_exposure_exceeds_{lim}%")

        # ---- book quality, liquidity and edge -----------------------------------------------------
        if ctx.book is not None:
            spread = ctx.book.spread
            details["spread"] = None if spread is None else str(spread)
            if not is_exit and (spread is None or spread > c.max_spread):
                reasons.append(f"spread_too_wide:{spread}")
        prev = ctx.preview
        if prev is not None and intent.tif.value == "IOC":
            details["preview_filled"] = str(prev.filled)
            details["preview_vwap"] = None if prev.vwap is None else str(prev.vwap)
            if prev.filled < intent.qty * c.min_fill_ratio:
                reasons.append(f"insufficient_liquidity:{prev.filled}<{intent.qty}")
            if not is_exit and intent.model_prob is not None and prev.vwap is not None and prev.filled > 0:
                fee_per = ctx.preview_fee / prev.filled
                edge = intent.model_prob - prev.vwap - fee_per
                details["edge_after_costs"] = str(edge)
                if edge < c.min_edge:
                    reasons.append(f"edge_after_costs_below_min:{edge.quantize(Decimal('0.0001'))}")
        elif not is_exit and intent.model_prob is not None and intent.tif.value == "GTC":
            fee_per = ctx.worst_fee / intent.qty if intent.qty > 0 else ZERO
            edge = intent.model_prob - intent.limit_px - fee_per
            details["edge_after_costs"] = str(edge)
            if edge < c.min_edge:
                reasons.append("edge_after_costs_below_min")

        return RiskDecision(approved=not reasons, reasons=reasons, details=details)
