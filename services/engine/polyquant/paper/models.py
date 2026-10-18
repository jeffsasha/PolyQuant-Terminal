"""Paper-trading order, fill and position types. Prices are in *outcome* terms (an Up price or a Down price),
always in (0, 1); `instrument_px` on fills is the long-side price used for fees."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from polyquant.domain.models import Outcome


class Side(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class TIF(StrEnum):
    IOC = "IOC"  # marketable limit: take what is available within the limit, cancel the rest
    GTC = "GTC"  # take what is marketable, rest the remainder (until window end)


class OrderStatus(StrEnum):
    PENDING = "PENDING"  # submitted, travelling to the venue (simulated latency); capital reserved
    OPEN = "OPEN"  # resting on the book
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


TERMINAL = frozenset({OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.EXPIRED})


@dataclass(frozen=True, slots=True)
class OrderIntent:
    """What a strategy or the operator asks for. Every intent goes through the risk engine first."""

    client_order_id: str
    slug: str
    outcome: Outcome
    side: Side
    qty: Decimal
    limit_px: Decimal
    tif: TIF = TIF.IOC
    post_only: bool = False
    strategy: str = "manual"
    model_prob: Decimal | None = None  # strategy's P(outcome); enables the edge-after-costs gate
    requires_reference: bool = True  # strategy needs an official priceToBeat to be meaningful


@dataclass
class PaperOrder:
    id: str
    intent: OrderIntent
    profile: str
    created_at: datetime
    arrive_at: datetime
    status: OrderStatus = OrderStatus.PENDING
    filled_qty: Decimal = Decimal(0)
    notional: Decimal = Decimal(0)  # sum(qty * px) of fills, outcome terms
    fees: Decimal = Decimal(0)
    reserved: Decimal = Decimal(0)  # cash reserved for the unfilled part (BUY) — released on fill/cancel
    reason: str | None = None
    queue_ahead: Decimal | None = None  # maker model state (outcome-side qty ahead of us)
    last_level_qty: Decimal | None = None
    decision_best: Decimal | None = None  # best opposite price when the order was created (for spread/slippage)
    decision_mid: Decimal | None = None
    taker_fee_exact_cum: Decimal = Decimal(0)  # cumulative exact taker fee (for the per-order rounding cap)
    taker_fee_collected: Decimal = Decimal(0)

    @property
    def remaining(self) -> Decimal:
        return self.intent.qty - self.filled_qty

    @property
    def avg_px(self) -> Decimal | None:
        return None if self.filled_qty == 0 else self.notional / self.filled_qty

    @property
    def terminal(self) -> bool:
        return self.status in TERMINAL


@dataclass(frozen=True, slots=True)
class PaperFill:
    id: str
    order_id: str
    slug: str
    outcome: Outcome
    side: Side
    qty: Decimal
    px: Decimal  # outcome price
    instrument_px: Decimal  # long-side price (fee basis)
    liquidity: str  # taker | maker
    fee: Decimal  # charged (negative = rebate credit)
    fee_exact: Decimal
    fee_version: str
    ts: datetime  # simulated execution time
    book_transact_time: datetime | None
    spread_cost: Decimal  # (best at decision − mid at decision) × qty, sign so that a cost is positive
    slippage: Decimal  # (fill px − best at decision) × qty, cost-positive
    profile: str


@dataclass
class Position:
    slug: str
    outcome: Outcome
    qty: Decimal = Decimal(0)
    cost: Decimal = Decimal(0)  # cash paid for the open quantity (outcome px × qty), excluding fees
    realized_pnl: Decimal = Decimal(0)  # gross, excluding fees
    fees: Decimal = Decimal(0)
    opened_at: datetime | None = None

    @property
    def avg_cost(self) -> Decimal | None:
        return None if self.qty == 0 else self.cost / self.qty


@dataclass
class RiskDecision:
    approved: bool
    reasons: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)
