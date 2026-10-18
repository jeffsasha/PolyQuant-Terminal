"""PaperExecutionEngine: risk-gated paper orders filled against the live WebSocket L2 book.

Lifecycle per order: risk check → PENDING (capital reserved, simulated latency) → at arrival: validate state and
sweep the book (taker) → IOC remainder cancelled / GTC remainder rests (maker queue model) → FILLED, CANCELLED,
REJECTED or EXPIRED (at window end). Positions settle from the venue's official settlement. Every event is committed
to Postgres in one transaction before memory changes; on a database error the engine reloads from the database.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Protocol
from zoneinfo import ZoneInfo

from polyquant.domain.models import ONE, Instrument, Phase
from polyquant.domain.settlement import outcome_from_settlement_flag
from polyquant.fees.schedule import FeeSchedule, FeeScheduleUnknown, bankers_cents, capped_taker_charge
from polyquant.interfaces import EventSink
from polyquant.marketdata.book import BookSnapshot
from polyquant.paper.execution import (
    PROFILES,
    VENUE_LATENCY_REJECT_MS,
    ExecutionProfile,
    instrument_px,
    is_marketable,
    level_qty,
    maker_step,
    outcome_ladders,
    sweep,
)
from polyquant.paper.ledger import LedgerState, PostgresLedger, Tx, _order_from_row, apply_fill_to_position
from polyquant.paper.models import TIF, OrderIntent, OrderStatus, PaperFill, PaperOrder, Position, RiskDecision, Side
from polyquant.paper.risk import CentralRiskManager, RiskContext

log = logging.getLogger(__name__)
ZERO = Decimal(0)


class MarketView(Protocol):
    def instrument(self, slug: str) -> Instrument | None: ...
    def phase(self, slug: str, now: datetime) -> Phase | None: ...
    def book(self, slug: str) -> BookSnapshot | None: ...
    def book_stale(self, slug: str) -> bool: ...
    def ws_age_ms(self, now: datetime) -> float | None: ...
    def index_stale(self) -> bool: ...
    def clock_alert(self) -> bool: ...
    def settlement_flag(self, slug: str) -> int | None: ...


def fee_bound_per_contract(limit_px: Decimal) -> Decimal:
    """max p(1-p) over fill prices p ≤ limit (a buy can fill below its limit, where p(1-p) may be larger)."""
    half = Decimal("0.5")
    return half * half if limit_px >= half else limit_px * (ONE - limit_px)


class PaperExecutionEngine:
    def __init__(self, ledger: PostgresLedger, view: MarketView, sink: EventSink, clock, *,
                 fees: FeeSchedule | None = None, risk: CentralRiskManager | None = None,
                 profile: str = "conservative", day_tz: str = "America/New_York") -> None:
        if profile not in PROFILES:
            raise ValueError(f"unknown profile {profile}")
        if PROFILES[profile].diagnostic_only:
            raise ValueError("the optimistic profile is diagnostic only and cannot drive the paper ledger")
        self.ledger = ledger
        self.view = view
        self.sink = sink
        self.clock = clock
        self.fees = fees or FeeSchedule()
        self.risk = risk or CentralRiskManager()
        self.profile: ExecutionProfile = PROFILES[profile]
        self.day_tz = ZoneInfo(day_tz)
        self.st = LedgerState()

    # ---- lifecycle ------------------------------------------------------------------------------------

    async def start(self) -> None:
        now = self.clock.now()
        await self.ledger.ensure_account(self.risk.config.starting_capital, now)
        self.st = await self.ledger.load()
        await self._recover(now)

    async def _reload(self) -> None:
        self.st = await self.ledger.load()

    async def _recover(self, now: datetime) -> None:
        """After a restart, an order that was in flight has no knowable simulated outcome: cancel it and release its
        capital (never assume it filled). Resting orders keep resting but go to the back of the queue."""
        for o in list(self.st.orders.values()):
            if o.status is OrderStatus.PENDING:
                await self._finish(o, OrderStatus.CANCELLED, "restart: in-flight order outcome unknown", now)
            elif o.status in (OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED):
                o.queue_ahead = None  # re-initialised at full displayed size on the next book
                async with self.ledger.tx() as tx:
                    await tx.upsert_order(o, now, event="RECOVERED", detail={"queue": "reset to back of queue"})

    # ---- account views --------------------------------------------------------------------------------

    @property
    def available(self) -> Decimal:
        return self.st.cash - self.st.reserved

    def position_value(self, pos: Position) -> tuple[Decimal, str]:
        """Liquidation value at the outcome's best bid (conservative); cost basis if no book."""
        book = self.view.book(pos.slug)
        if book is not None:
            bids, _ = outcome_ladders(book, pos.outcome)
            if bids:
                return pos.qty * bids[0].px, "best_bid"
            return ZERO, "no_bid"
        return pos.cost, "cost_basis"

    def equity(self) -> Decimal:
        return self.st.cash + sum((self.position_value(p)[0] for p in self.st.positions.values()), ZERO)

    def trading_day(self, now: datetime):
        return now.astimezone(self.day_tz).date()

    def start_of_day_equity(self, now: datetime) -> Decimal:
        return self.st.equity_days.get(self.trading_day(now), self.equity())

    def halted(self) -> bool:
        h = self.st.halts.get("KILL_SWITCH")
        return bool(h and h["active"])

    def daily_halt(self, now: datetime) -> bool:
        h = self.st.halts.get("DAILY_LOSS")
        return bool(h and h["active"] and h["trading_day"] == self.trading_day(now))

    def cooldown_until(self, now: datetime) -> datetime | None:
        h = self.st.halts.get("COOLDOWN")
        return h["until_ts"] if h and h["active"] and h["until_ts"] and h["until_ts"] > now else None

    # ---- submit / cancel ----------------------------------------------------------------------------

    def _context(self, intent: OrderIntent, now: datetime) -> RiskContext:
        inst = self.view.instrument(intent.slug)
        book = self.view.book(intent.slug)
        gating = PROFILES[self.risk.config.gating_profile]
        preview = None
        preview_fee = ZERO
        if book is not None:
            tick = inst.tick_size if inst and inst.tick_size else Decimal("0.01")
            mq = inst.min_qty if inst and inst.min_qty else Decimal("0.01")
            preview = sweep(book, intent.outcome, intent.side, intent.qty, intent.limit_px, gating, tick=tick,
                            min_qty=mq)
            if preview.fills:
                try:
                    fees = self.fees.order_fills([(f.qty, instrument_px(intent.outcome, f.px)) for f in preview.fills],
                                                 now, liquidity="taker", theta_override=self._theta(inst, now))
                    preview_fee = sum((f.charged for f in fees), ZERO)
                except FeeScheduleUnknown:
                    preview_fee = ZERO
        worst_fee = self._worst_fee(intent, inst, now)
        horizons = {}
        for slug in {p.slug for p in self.st.positions.values()} | {o.intent.slug for o in self.st.orders.values()} \
                | {intent.slug}:
            i = self.view.instrument(slug)
            if i is not None:
                horizons[slug] = i.horizon
        return RiskContext(
            now=now, instrument=inst, phase=self.view.phase(intent.slug, now), book=book,
            book_stale=self.view.book_stale(intent.slug), index_stale=self.view.index_stale(),
            clock_alert=self.view.clock_alert(), equity=self.equity(), available_cash=self.available,
            start_of_day_equity=self.start_of_day_equity(now), positions=list(self.st.positions.values()),
            open_orders=list(self.st.orders.values()), attempts_this_market=self.st.attempts.get(intent.slug, 0),
            loss_streak=self.st.loss_streak, cooldown_until=self.cooldown_until(now), halted=self.halted(),
            daily_halt=self.daily_halt(now), preview=preview, preview_fee=preview_fee, worst_fee=worst_fee,
            instrument_horizons=horizons)

    def _theta(self, inst: Instrument | None, now: datetime) -> Decimal:
        """Use the higher of the schedule's taker coefficient and the market's own feeCoefficient (conservative)."""
        sched = self.fees.version_at(now).taker_theta
        if inst is not None and inst.fee_coefficient is not None and inst.fee_coefficient > sched:
            return inst.fee_coefficient
        return sched

    def _worst_fee(self, intent: OrderIntent, inst: Instrument | None, now: datetime) -> Decimal:
        try:
            theta = self._theta(inst, now)
        except FeeScheduleUnknown:
            return intent.qty  # unknown schedule: reserve absurdly high so risk rejects
        return bankers_cents(theta * intent.qty * fee_bound_per_contract(intent.limit_px)) + Decimal("0.01")

    async def submit(self, intent: OrderIntent) -> tuple[PaperOrder | None, RiskDecision]:
        now = self.clock.now()
        existing = await self._find_client_order(intent.client_order_id)
        if existing is not None:  # idempotent: same client id never creates a second order
            return existing, RiskDecision(True, ["duplicate_client_order_id_returned_existing"])
        ctx = self._context(intent, now)
        decision = self.risk.check(intent, ctx)
        order_id = uuid.uuid4().hex
        order = PaperOrder(id=order_id, intent=intent, profile=self.profile.name, created_at=now,
                           arrive_at=now + timedelta(milliseconds=self.profile.latency_ms))
        if ctx.preview is not None:
            order.decision_best = ctx.preview.best_px
            order.decision_mid = ctx.preview.mid
        try:
            async with self.ledger.tx() as tx:
                await tx.risk_decision(now, intent, decision)
                if not decision.approved:
                    order.status = OrderStatus.REJECTED
                    order.reason = "risk: " + ", ".join(decision.reasons)
                    await tx.upsert_order(order, now, event="REJECTED", detail={"reasons": decision.reasons})
                else:
                    if intent.side is Side.BUY:
                        order.reserved = intent.qty * intent.limit_px + ctx.worst_fee
                        await tx.ledger(now, "RESERVE", reserved=order.reserved, order_id=order.id, slug=intent.slug)
                    await tx.upsert_order(order, now, event="PENDING", detail={"arrive_at": order.arrive_at})
        except Exception:
            await self._reload()
            raise
        if decision.approved and intent.side is Side.BUY:
            self.st.attempts[intent.slug] = self.st.attempts.get(intent.slug, 0) + 1
        if decision.approved:
            self.st.reserved += order.reserved
            self.st.orders[order.id] = order
        return order, decision

    async def _find_client_order(self, client_order_id: str) -> PaperOrder | None:
        for o in self.st.orders.values():
            if o.intent.client_order_id == client_order_id:
                return o
        async with self.ledger.pool.acquire() as conn:
            r = await conn.fetchrow("SELECT * FROM paper_orders WHERE account_id=$1 AND client_order_id=$2",
                                    self.ledger.account, client_order_id)
        return None if r is None else _order_from_row(r)

    async def cancel(self, order_id: str, reason: str = "cancelled by user") -> PaperOrder | None:
        o = self.st.orders.get(order_id)
        if o is None:
            return None
        await self._finish(o, OrderStatus.CANCELLED, reason, self.clock.now())
        return o

    async def _finish(self, o: PaperOrder, status: OrderStatus, reason: str, now: datetime,
                      tx: Tx | None = None) -> None:
        release = o.reserved
        o.status = status
        o.reason = reason
        o.reserved = ZERO

        async def write(t: Tx) -> None:
            if release:
                await t.ledger(now, "RELEASE", reserved=-release, order_id=o.id, slug=o.intent.slug,
                               detail={"reason": reason})
            await t.upsert_order(o, now, event=status.value, detail={"reason": reason})

        try:
            if tx is not None:
                await write(tx)
            else:
                async with self.ledger.tx() as t:
                    await write(t)
        except Exception:
            await self._reload()
            raise
        self.st.reserved -= release
        self.st.orders.pop(o.id, None)

    # ---- simulation step ----------------------------------------------------------------------------

    async def step(self) -> None:
        now = self.clock.now()
        await self._daily_bookkeeping(now)
        for o in sorted(list(self.st.orders.values()), key=lambda x: x.created_at):
            if o.id not in self.st.orders:
                continue
            inst = self.view.instrument(o.intent.slug)
            if inst is not None and now >= inst.window_end:
                await self._finish(o, OrderStatus.EXPIRED, "window closed", now)
            elif o.status is OrderStatus.PENDING and now >= o.arrive_at:
                await self._arrive(o, now)
            elif o.status in (OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED):
                await self._rest(o, now)
        await self._settle(now)

    async def _arrive(self, o: PaperOrder, now: datetime) -> None:
        i = o.intent
        inst = self.view.instrument(i.slug)
        book = self.view.book(i.slug)
        ws_age = self.view.ws_age_ms(now)
        if self.profile.latency_ms > VENUE_LATENCY_REJECT_MS:
            return await self._finish(o, OrderStatus.REJECTED, "venue latency stopgap (>5 s)", now)
        if inst is None or self.view.phase(i.slug, now) is not Phase.OPEN:
            return await self._finish(o, OrderStatus.REJECTED, "market not open at arrival", now)
        if book is None or self.view.book_stale(i.slug) or ws_age is None or ws_age > self.profile.max_book_age_ms:
            return await self._finish(o, OrderStatus.REJECTED, f"no fresh book at arrival (ws age {ws_age} ms)", now)
        marketable = is_marketable(book, i.outcome, i.side, i.limit_px)
        if i.post_only and marketable:
            return await self._finish(o, OrderStatus.REJECTED, "post-only order would have matched", now)
        tick = inst.tick_size or Decimal("0.01")
        mq = inst.min_qty or Decimal("0.01")
        if marketable:
            res = sweep(book, i.outcome, i.side, o.remaining, i.limit_px, self.profile, tick=tick, min_qty=mq)
            if res.fills:
                await self._apply_fills(o, [(f.qty, f.px) for f in res.fills], "taker", book, now)
        if o.id not in self.st.orders:
            return
        if o.remaining <= 0:
            return await self._finish(o, OrderStatus.FILLED, "filled", now)
        if i.tif is TIF.IOC:
            reason = "IOC remainder cancelled" if o.filled_qty else "IOC: no liquidity within limit"
            return await self._finish(o, OrderStatus.CANCELLED, reason, now)
        # GTC remainder rests at the back of the queue at our price
        own = outcome_ladders(book, i.outcome)[0 if i.side is Side.BUY else 1]
        o.queue_ahead = level_qty(own, i.limit_px)
        o.last_level_qty = o.queue_ahead
        o.status = OrderStatus.PARTIALLY_FILLED if o.filled_qty > 0 else OrderStatus.OPEN
        try:
            async with self.ledger.tx() as tx:
                await tx.upsert_order(o, now, event=o.status.value, detail={"queue_ahead": o.queue_ahead})
        except Exception:
            await self._reload()
            raise

    async def _rest(self, o: PaperOrder, now: datetime) -> None:
        i = o.intent
        book = self.view.book(i.slug)
        if book is None or self.view.book_stale(i.slug):
            return  # no fills against unknown state
        inst = self.view.instrument(i.slug)
        if o.queue_ahead is None:  # after restart
            own = outcome_ladders(book, i.outcome)[0 if i.side is Side.BUY else 1]
            o.queue_ahead = level_qty(own, i.limit_px)
            o.last_level_qty = o.queue_ahead
            return
        upd = maker_step(book, i.outcome, i.side, i.limit_px, o.remaining, o.queue_ahead, o.last_level_qty or ZERO,
                         self.profile, tick=inst.tick_size or Decimal("0.01"), min_qty=inst.min_qty or Decimal("0.01"))
        o.queue_ahead, o.last_level_qty = upd.queue_ahead, upd.level_qty
        if upd.fill_qty > 0:
            await self._apply_fills(o, [(upd.fill_qty, i.limit_px)], "maker", book, now,
                                    detail={"maker_reason": upd.reason})
            if o.id in self.st.orders and o.remaining <= 0:
                await self._finish(o, OrderStatus.FILLED, "filled", now)

    async def _apply_fills(self, o: PaperOrder, fills: list[tuple[Decimal, Decimal]], liquidity: str,
                           book: BookSnapshot, now: datetime, detail: dict | None = None) -> None:
        i = o.intent
        inst = self.view.instrument(i.slug)
        try:
            v = self.fees.version_at(now)
            theta = self._theta(inst, now) if liquidity == "taker" else v.maker_theta(self.fees.maker_tier)
        except FeeScheduleUnknown as exc:
            return await self._finish(o, OrderStatus.REJECTED, f"fee schedule unknown: {exc}", now)
        new_fills: list[PaperFill] = []
        positions = {k: replace(p) for k, p in self.st.positions.items()}
        cash = ZERO
        reserved_release = ZERO
        o2 = replace(o)
        for qty, px in fills:
            ipx = instrument_px(i.outcome, px)
            exact = theta * qty * ipx * (ONE - ipx)
            if liquidity == "taker":  # cumulative cap across all taker fills of this order (shared helper)
                charge, o2.taker_fee_exact_cum, o2.taker_fee_collected = capped_taker_charge(
                    exact, o2.taker_fee_exact_cum, o2.taker_fee_collected)
            else:
                charge = bankers_cents(exact)
            best, mid = o.decision_best, o.decision_mid
            if liquidity == "maker":
                spread_cost = ((px - mid) if i.side is Side.BUY else (mid - px)) * qty if mid is not None else ZERO
                slippage = ZERO
            else:
                spread_cost = (((best - mid) if i.side is Side.BUY else (mid - best)) * qty
                               if best is not None and mid is not None else ZERO)
                slippage = (((px - best) if i.side is Side.BUY else (best - px)) * qty) if best is not None else ZERO
            f = PaperFill(id=uuid.uuid4().hex, order_id=o.id, slug=i.slug, outcome=i.outcome, side=i.side, qty=qty,
                          px=px, instrument_px=ipx, liquidity=liquidity, fee=charge, fee_exact=exact,
                          fee_version=v.name, ts=now, book_transact_time=book.transact_time,
                          spread_cost=spread_cost, slippage=slippage, profile=self.profile.name)
            new_fills.append(f)
            if i.side is Side.BUY:
                per_unit = o2.reserved / o2.remaining if o2.remaining > 0 else ZERO
                rel = min(o2.reserved, per_unit * qty)
                o2.reserved -= rel
                reserved_release += rel
                cash -= qty * px
            else:
                cash += qty * px
            cash -= charge
            o2.filled_qty += qty
            o2.notional += qty * px
            o2.fees += charge
            apply_fill_to_position(positions, (i.slug, i.outcome), i.side, qty, px, charge, now)
        o2.status = OrderStatus.FILLED if o2.remaining <= 0 else OrderStatus.PARTIALLY_FILLED
        try:
            async with self.ledger.tx() as tx:
                for f in new_fills:
                    await tx.fill(f)
                    kind = "BUY" if i.side is Side.BUY else "SELL"
                    amt = f.qty * f.px
                    await tx.ledger(now, kind, cash=-amt if kind == "BUY" else amt, order_id=o.id, fill_id=f.id,
                                    slug=i.slug, detail={"qty": f.qty, "px": f.px, "liquidity": liquidity})
                    if f.fee:
                        await tx.ledger(now, "FEE" if f.fee > 0 else "REBATE", cash=-f.fee, order_id=o.id,
                                        fill_id=f.id, slug=i.slug, detail={"version": f.fee_version})
                if reserved_release:
                    await tx.ledger(now, "RELEASE", reserved=-reserved_release, order_id=o.id, slug=i.slug,
                                    detail={"reason": "filled"})
                await tx.upsert_order(o2, now, event="FILL", detail={"fills": len(new_fills), **(detail or {})})
        except Exception:
            await self._reload()
            raise
        # commit to memory
        o.taker_fee_exact_cum, o.taker_fee_collected = o2.taker_fee_exact_cum, o2.taker_fee_collected
        o.reserved, o.filled_qty, o.notional, o.fees, o.status = (o2.reserved, o2.filled_qty, o2.notional, o2.fees,
                                                                  o2.status)
        self.st.cash += cash
        self.st.reserved -= reserved_release
        self.st.positions = {k: p for k, p in positions.items() if p.qty > 0}
        for f in new_fills:
            self.sink.quality_event("paper", "fill", {"order": o.id, "slug": f.slug, "outcome": f.outcome.value,
                                                      "side": f.side.value, "qty": str(f.qty), "px": str(f.px),
                                                      "fee": str(f.fee), "liquidity": f.liquidity}, now)

    # ---- settlement, daily limits, kill switch ------------------------------------------------------

    async def _settle(self, now: datetime) -> None:
        by_slug: dict[str, list[Position]] = {}
        for p in self.st.positions.values():
            by_slug.setdefault(p.slug, []).append(p)
        for slug, positions in by_slug.items():
            inst = self.view.instrument(slug)
            if inst is None or inst.settlement_price is None or self.view.phase(slug, now) is not Phase.SETTLED:
                continue
            # Sources: the venue-declared result on the (uncached) instrument, and the CDN-cached /settlement flag.
            # Settle on whichever is available, but only if every available source agrees with the price rule.
            flag = self.view.settlement_flag(slug)
            sources = {}
            if inst.venue_outcome is not None:
                sources["outcome_prices"] = inst.venue_outcome
            if flag is not None:
                sources["settlement_flag"] = outcome_from_settlement_flag(flag)
            rule = inst.settled_outcome()
            if not sources:
                continue  # resolved price but no venue-declared result yet
            if rule is not None:
                sources["price_rule"] = rule
            if len(set(sources.values())) != 1:
                self.sink.quality_event("paper", "settlement_conflict",
                                        {"slug": slug, **{k: v.value for k, v in sources.items()}}, now)
                continue  # never settle on contradictory information; needs manual review
            venue = next(iter(sources.values()))
            try:
                async with self.ledger.tx() as tx:
                    for p in positions:
                        win = p.outcome is venue
                        payout = p.qty if win else ZERO
                        await tx.settlement(slug, p.outcome, win, p.qty, p.cost, payout, now,
                                            {"settlement_price": inst.settlement_price,
                                             "price_to_beat": inst.price_to_beat, "flag": flag,
                                             "sources": sorted(sources)})
                        if payout:
                            await tx.ledger(now, "SETTLEMENT", cash=payout, slug=slug,
                                            detail={"outcome": p.outcome.value, "qty": p.qty})
                    net = sum(((p.qty if p.outcome is venue else ZERO) - p.cost - p.fees for p in positions), ZERO)
                    streak = self.st.loss_streak + 1 if net < 0 else 0
                    if streak >= self.risk.config.loss_streak_for_cooldown:
                        until = now + timedelta(seconds=self.risk.config.cooldown_s)
                        await tx.halt(now, "COOLDOWN", True, f"{streak} consecutive losing positions", until=until)
            except Exception:
                await self._reload()
                raise
            for p in positions:
                self.st.cash += p.qty if p.outcome is venue else ZERO
                self.st.positions.pop((p.slug, p.outcome), None)
            self.st.loss_streak = streak
            if streak >= self.risk.config.loss_streak_for_cooldown:
                self.st.halts["COOLDOWN"] = {"active": True, "until_ts": now + timedelta(
                    seconds=self.risk.config.cooldown_s), "reason": "loss streak", "trading_day": None, "ts": now}
            self.sink.quality_event("paper", "settled", {"slug": slug, "winner": venue.value, "net": str(net)}, now)

    async def _daily_bookkeeping(self, now: datetime) -> None:
        day = self.trading_day(now)
        if day not in self.st.equity_days:
            eq = self.equity()
            async with self.ledger.tx() as tx:
                await tx.equity_day(day, eq, now)
            self.st.equity_days[day] = eq
        sod = self.st.equity_days[day]
        if not self.daily_halt(now) and sod - self.equity() >= sod * self.risk.config.max_daily_loss_pct / 100:
            async with self.ledger.tx() as tx:
                await tx.halt(now, "DAILY_LOSS", True, "daily loss limit reached", trading_day=day)
            self.st.halts["DAILY_LOSS"] = {"active": True, "trading_day": day, "reason": "daily loss", "ts": now,
                                           "until_ts": None}
            self.sink.quality_event("risk", "daily_loss_halt", {"day": day.isoformat()}, now)
            for o in list(self.st.orders.values()):
                if o.intent.side is Side.BUY:
                    await self._finish(o, OrderStatus.CANCELLED, "daily loss halt", now)

    async def set_kill_switch(self, active: bool, reason: str) -> None:
        now = self.clock.now()
        async with self.ledger.tx() as tx:
            await tx.halt(now, "KILL_SWITCH", active, reason)
        self.st.halts["KILL_SWITCH"] = {"active": active, "reason": reason, "ts": now, "until_ts": None,
                                        "trading_day": None}
        self.sink.quality_event("risk", "kill_switch_on" if active else "kill_switch_off", {"reason": reason}, now)
        if active:  # emergency stop: cancel every working entry order
            for o in list(self.st.orders.values()):
                if o.intent.side is Side.BUY:
                    await self._finish(o, OrderStatus.CANCELLED, f"kill switch: {reason}", now)

    def account_view(self) -> dict:
        now = self.clock.now()
        positions = []
        for p in self.st.positions.values():
            val, basis = self.position_value(p)
            positions.append({"slug": p.slug, "outcome": p.outcome.value, "qty": str(p.qty), "cost": str(p.cost),
                              "avg_cost": None if p.avg_cost is None else str(p.avg_cost), "value": str(val),
                              "value_basis": basis, "unrealized": str(val - p.cost), "fees": str(p.fees)})
        eq = self.equity()
        sod = self.start_of_day_equity(now)
        return {"mode": "PAPER", "profile": self.profile.name, "starting_capital": str(self.st.starting_capital),
                "cash": str(self.st.cash), "reserved": str(self.st.reserved), "available": str(self.available),
                "equity": str(eq), "start_of_day_equity": str(sod), "daily_pnl": str(eq - sod),
                "kill_switch": self.halted(), "daily_loss_halt": self.daily_halt(now),
                "cooldown_until": (c.isoformat() if (c := self.cooldown_until(now)) else None),
                "loss_streak": self.st.loss_streak, "positions": positions,
                "working_orders": [{"id": o.id, "slug": o.intent.slug, "outcome": o.intent.outcome.value,
                                    "side": o.intent.side.value, "qty": str(o.intent.qty),
                                    "filled": str(o.filled_qty), "limit": str(o.intent.limit_px),
                                    "status": o.status.value, "reserved": str(o.reserved)}
                                   for o in self.st.orders.values()]}

