"""PostgreSQL persistence for paper trading (implements interfaces.PortfolioLedger).

Writes are synchronous and transactional: an engine event (submit, fill, cancel, settle) is committed in one
transaction before the in-memory state is considered changed. On restart the full state is rebuilt from the tables.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

import asyncpg

from polyquant.domain.models import Outcome
from polyquant.paper.models import (
    TERMINAL,
    TIF,
    OrderIntent,
    OrderStatus,
    PaperFill,
    PaperOrder,
    Position,
    RiskDecision,
    Side,
)
from polyquant.recorder.store import dumps

ZERO = Decimal(0)


@dataclass
class LedgerState:
    cash: Decimal = ZERO
    reserved: Decimal = ZERO
    starting_capital: Decimal = ZERO
    orders: dict[str, PaperOrder] = field(default_factory=dict)  # non-terminal orders
    positions: dict[tuple[str, Outcome], Position] = field(default_factory=dict)  # open positions
    halts: dict[str, dict] = field(default_factory=dict)  # kind -> latest row
    equity_days: dict[date, Decimal] = field(default_factory=dict)
    attempts: dict[str, int] = field(default_factory=dict)  # slug -> entry attempts (approved + rejected)
    loss_streak: int = 0


def _order_from_row(r) -> PaperOrder:
    intent = OrderIntent(client_order_id=r["client_order_id"], slug=r["slug"], outcome=Outcome(r["outcome"]),
                         side=Side(r["side"]), qty=r["qty"], limit_px=r["limit_px"], tif=TIF(r["tif"]),
                         post_only=r["post_only"], strategy=r["strategy"], model_prob=r["model_prob"],
                         requires_reference=r["requires_reference"])
    return PaperOrder(id=r["id"], intent=intent, profile=r["profile"], created_at=r["created_at"],
                      arrive_at=r["arrive_at"], status=OrderStatus(r["status"]), filled_qty=r["filled_qty"],
                      notional=r["notional"], fees=r["fees"], reserved=r["reserved"], reason=r["reason"],
                      queue_ahead=r["queue_ahead"], last_level_qty=r["last_level_qty"],
                      decision_best=r["decision_best"], decision_mid=r["decision_mid"],
                      taker_fee_exact_cum=r["taker_fee_exact_cum"], taker_fee_collected=r["taker_fee_collected"])


class Tx:
    def __init__(self, conn: asyncpg.Connection, account_id: str) -> None:
        self.conn = conn
        self.account = account_id

    async def ledger(self, ts: datetime, kind: str, *, cash: Decimal = ZERO, reserved: Decimal = ZERO,
                     order_id: str | None = None, fill_id: str | None = None, slug: str | None = None,
                     detail: dict | None = None) -> None:
        await self.conn.execute(
            "INSERT INTO paper_ledger (account_id, ts, kind, cash_delta, reserved_delta, order_id, fill_id, slug,"
            " detail) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)",
            self.account, ts, kind, cash, reserved, order_id, fill_id, slug, dumps(detail or {}))

    async def upsert_order(self, o: PaperOrder, ts: datetime, *, event: str | None = None,
                           detail: dict | None = None) -> None:
        i = o.intent
        await self.conn.execute(
            """INSERT INTO paper_orders (id, account_id, client_order_id, slug, outcome, side, qty, limit_px, tif,
                 post_only, strategy, model_prob, requires_reference, profile, created_at, arrive_at, status,
                 filled_qty, notional, fees, reserved, reason, queue_ahead, last_level_qty, decision_best,
                 decision_mid, taker_fee_exact_cum, taker_fee_collected, updated_at)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23,$24,$25,
                       $26,$27,$28,$29)
               ON CONFLICT (id) DO UPDATE SET status=EXCLUDED.status, filled_qty=EXCLUDED.filled_qty,
                 notional=EXCLUDED.notional, fees=EXCLUDED.fees, reserved=EXCLUDED.reserved, reason=EXCLUDED.reason,
                 queue_ahead=EXCLUDED.queue_ahead, last_level_qty=EXCLUDED.last_level_qty,
                 taker_fee_exact_cum=EXCLUDED.taker_fee_exact_cum, taker_fee_collected=EXCLUDED.taker_fee_collected,
                 updated_at=EXCLUDED.updated_at""",
            o.id, self.account, i.client_order_id, i.slug, i.outcome.value, i.side.value, i.qty, i.limit_px,
            i.tif.value, i.post_only, i.strategy, i.model_prob, i.requires_reference, o.profile, o.created_at,
            o.arrive_at, o.status.value, o.filled_qty, o.notional, o.fees, o.reserved, o.reason, o.queue_ahead,
            o.last_level_qty, o.decision_best, o.decision_mid, o.taker_fee_exact_cum, o.taker_fee_collected, ts)
        if event:
            await self.conn.execute(
                "INSERT INTO paper_order_events (order_id, ts, status, detail) VALUES ($1,$2,$3,$4)",
                o.id, ts, event, dumps(detail or {}))

    async def fill(self, f: PaperFill) -> None:
        await self.conn.execute(
            """INSERT INTO paper_fills (id, order_id, account_id, slug, outcome, side, qty, px, instrument_px,
                 liquidity, fee, fee_exact, fee_version, ts, book_transact_time, spread_cost, slippage, profile)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18)""",
            f.id, f.order_id, self.account, f.slug, f.outcome.value, f.side.value, f.qty, f.px, f.instrument_px,
            f.liquidity, f.fee, f.fee_exact, f.fee_version, f.ts, f.book_transact_time, f.spread_cost, f.slippage,
            f.profile)

    async def settlement(self, slug: str, outcome: Outcome, winning: bool, qty: Decimal, cost: Decimal,
                         payout: Decimal, ts: datetime, detail: dict) -> None:
        await self.conn.execute(
            "INSERT INTO paper_settlements (account_id, slug, outcome, winning, qty, cost, payout, settled_at, detail)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)",
            self.account, slug, outcome.value, winning, qty, cost, payout, ts, dumps(detail))

    async def risk_decision(self, ts: datetime, intent: OrderIntent, decision: RiskDecision) -> None:
        await self.conn.execute(
            "INSERT INTO risk_decisions (account_id, ts, client_order_id, slug, approved, reasons, details, intent)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8)",
            self.account, ts, intent.client_order_id, intent.slug, decision.approved, dumps(decision.reasons),
            dumps(decision.details), dumps({k: getattr(intent, k) for k in intent.__dataclass_fields__}))

    async def halt(self, ts: datetime, kind: str, active: bool, reason: str, *, until: datetime | None = None,
                   trading_day: date | None = None) -> None:
        await self.conn.execute(
            "INSERT INTO trading_halts (account_id, ts, kind, active, until_ts, reason, trading_day)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7)", self.account, ts, kind, active, until, reason, trading_day)

    async def equity_day(self, day: date, equity: Decimal, ts: datetime) -> None:
        await self.conn.execute(
            "INSERT INTO paper_equity_days (account_id, trading_day, start_equity, recorded_at) VALUES ($1,$2,$3,$4)"
            " ON CONFLICT DO NOTHING", self.account, day, equity, ts)


class PostgresLedger:
    def __init__(self, pool: asyncpg.Pool, account_id: str = "paper-main") -> None:
        self.pool = pool
        self.account = account_id

    @asynccontextmanager
    async def tx(self):
        async with self.pool.acquire() as conn, conn.transaction():
            yield Tx(conn, self.account)

    async def ensure_account(self, starting_capital: Decimal, at: datetime) -> bool:
        async with self.pool.acquire() as conn, conn.transaction():
            created = await conn.fetchval(
                "INSERT INTO paper_accounts (id, starting_capital, created_at) VALUES ($1,$2,$3)"
                " ON CONFLICT (id) DO NOTHING RETURNING true", self.account, starting_capital, at)
            if created:
                await Tx(conn, self.account).ledger(at, "DEPOSIT", cash=starting_capital,
                                                    detail={"reason": "simulated starting capital"})
            return bool(created)

    async def load(self) -> LedgerState:
        st = LedgerState()
        async with self.pool.acquire() as conn:
            st.starting_capital = await conn.fetchval("SELECT starting_capital FROM paper_accounts WHERE id=$1",
                                                      self.account) or ZERO
            row = await conn.fetchrow("SELECT coalesce(sum(cash_delta),0) c, coalesce(sum(reserved_delta),0) r"
                                      " FROM paper_ledger WHERE account_id=$1", self.account)
            st.cash, st.reserved = row["c"], row["r"]
            for r in await conn.fetch("SELECT * FROM paper_orders WHERE account_id=$1 AND status <> ALL($2::text[])",
                                      self.account, [s.value for s in TERMINAL]):
                o = _order_from_row(r)
                st.orders[o.id] = o
            # positions from fills minus settlements
            fills = await conn.fetch("SELECT slug, outcome, side, qty, px, fee, ts FROM paper_fills WHERE account_id=$1"
                                     " ORDER BY ts, id", self.account)
            settled = {(r["slug"], r["outcome"]) for r in await conn.fetch(
                "SELECT slug, outcome FROM paper_settlements WHERE account_id=$1", self.account)}
            for f in fills:
                key = (f["slug"], Outcome(f["outcome"]))
                if (f["slug"], f["outcome"]) in settled:
                    continue
                apply_fill_to_position(st.positions, key, Side(f["side"]), f["qty"], f["px"], f["fee"], f["ts"])
            st.positions = {k: p for k, p in st.positions.items() if p.qty > 0}
            for r in await conn.fetch(
                    "SELECT DISTINCT ON (kind) kind, active, until_ts, reason, trading_day, ts FROM trading_halts"
                    " WHERE account_id=$1 ORDER BY kind, ts DESC, id DESC", self.account):
                st.halts[r["kind"]] = dict(r)
            for r in await conn.fetch("SELECT trading_day, start_equity FROM paper_equity_days WHERE account_id=$1",
                                      self.account):
                st.equity_days[r["trading_day"]] = r["start_equity"]
            for r in await conn.fetch("SELECT slug, count(*) n FROM risk_decisions WHERE account_id=$1 AND"
                                      " approved AND (intent->>'side') = 'BUY' GROUP BY slug", self.account):
                st.attempts[r["slug"]] = r["n"]
            st.loss_streak = await self._loss_streak(conn)
        return st

    async def _loss_streak(self, conn) -> int:
        """Consecutive losing settled positions (net of fees), most recent first."""
        rows = await conn.fetch(
            """SELECT s.payout - s.cost - coalesce((SELECT sum(fee) FROM paper_fills f WHERE f.account_id=s.account_id
                   AND f.slug=s.slug AND f.outcome=s.outcome), 0) AS net
               FROM paper_settlements s WHERE s.account_id=$1 ORDER BY s.settled_at DESC, s.id DESC""", self.account)
        n = 0
        for r in rows:
            if r["net"] < 0:
                n += 1
            else:
                break
        return n

    # ---- read models for the API -------------------------------------------------------------------

    async def recent_orders(self, limit: int = 100) -> list[dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM paper_orders WHERE account_id=$1 ORDER BY created_at DESC LIMIT $2",
                                    self.account, limit)
        return [dict(r) for r in rows]

    async def fills(self, limit: int = 200) -> list[dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM paper_fills WHERE account_id=$1 ORDER BY ts DESC LIMIT $2",
                                    self.account, limit)
        return [dict(r) for r in rows]

    async def risk_decisions(self, limit: int = 100, rejected_only: bool = False) -> list[dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT ts, client_order_id, slug, approved, reasons, details, intent FROM risk_decisions"
                " WHERE account_id=$1 AND ($3 = false OR approved = false) ORDER BY ts DESC LIMIT $2",
                self.account, limit, rejected_only)
        return [{**dict(r), "reasons": json.loads(r["reasons"]), "details": json.loads(r["details"]),
                 "intent": json.loads(r["intent"])} for r in rows]

    async def closed_groups(self) -> list[dict]:
        """Per (slug, outcome): buys, sells, payouts and fees, for computing realized PnL of closed positions."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT f.slug, f.outcome,
                          sum(CASE WHEN side='BUY' THEN qty*px ELSE 0 END) AS bought,
                          sum(CASE WHEN side='SELL' THEN qty*px ELSE 0 END) AS sold,
                          sum(fee) AS fees,
                          coalesce((SELECT payout FROM paper_settlements s WHERE s.account_id=f.account_id
                                    AND s.slug=f.slug AND s.outcome=f.outcome), 0) AS payout
                   FROM paper_fills f WHERE f.account_id=$1 GROUP BY f.account_id, f.slug, f.outcome""",
                self.account)
        return [dict(r) for r in rows]

    async def pnl_breakdown(self) -> dict:
        """Totals over all fills and settlements (open and closed). See the API for closed-position PnL."""
        async with self.pool.acquire() as conn:
            f = await conn.fetchrow(
                """SELECT coalesce(sum(CASE WHEN side='SELL' THEN qty*px ELSE -qty*px END),0) AS trade_cash,
                          coalesce(sum(fee),0) AS fees, coalesce(sum(spread_cost),0) AS spread_cost,
                          coalesce(sum(slippage),0) AS slippage, count(*) AS fills,
                          coalesce(sum(CASE WHEN liquidity='maker' THEN 1 ELSE 0 END),0) AS maker_fills
                   FROM paper_fills WHERE account_id=$1""", self.account)
            s = await conn.fetchrow("SELECT coalesce(sum(payout),0) payout, count(*) n, "
                                    "coalesce(sum(CASE WHEN winning THEN 1 ELSE 0 END),0) wins"
                                    " FROM paper_settlements WHERE account_id=$1", self.account)
        return {"trade_cash_flow": f["trade_cash"], "settlement_payouts": s["payout"], "fees": f["fees"],
                "spread_cost": f["spread_cost"], "slippage": f["slippage"], "fills": f["fills"],
                "maker_fills": f["maker_fills"], "settled_positions": s["n"], "winning_positions": s["wins"]}


def apply_fill_to_position(positions: dict, key: tuple[str, Outcome], side: Side, qty: Decimal, px: Decimal,
                           fee: Decimal, ts: datetime) -> Position:
    pos = positions.get(key)
    if pos is None:
        pos = positions[key] = Position(slug=key[0], outcome=key[1])
    if side is Side.BUY:
        if pos.qty == 0:
            pos.opened_at = ts
        pos.qty += qty
        pos.cost += qty * px
    else:
        if qty > pos.qty:
            raise ValueError(f"sell {qty} exceeds position {pos.qty} for {key}")
        avg = pos.cost / pos.qty
        pos.realized_pnl += (px - avg) * qty
        pos.cost -= avg * qty
        pos.qty -= qty
    pos.fees += fee
    return pos
