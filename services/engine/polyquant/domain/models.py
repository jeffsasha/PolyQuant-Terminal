"""Core domain types. Money and prices are Decimal everywhere; nothing here touches float."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

ONE = Decimal(1)


class Horizon(StrEnum):
    M15 = "15m"
    H1 = "1h"


class Outcome(StrEnum):
    UP = "UP"  # instrument long side, "Yes"
    DOWN = "DOWN"  # instrument short side, "No"


class Phase(StrEnum):
    UPCOMING = "UPCOMING"
    OPEN = "OPEN"
    AWAITING_SETTLEMENT = "AWAITING_SETTLEMENT"
    SETTLED = "SETTLED"
    # Venue fields and clock disagree. Always treated as not tradable.
    UNKNOWN = "UNKNOWN"


class Source(StrEnum):
    GATEWAY = "gateway"
    WS = "ws"
    FIXTURE = "fixture"
    REPLAY = "replay"


@dataclass(frozen=True, slots=True)
class Instrument:
    """One BTC Up/Down market: a single venue instrument whose long side is Up and short side is Down."""

    slug: str
    market_id: str
    event_slug: str | None
    asset: str
    horizon: Horizon
    index_symbol: str
    window_start: datetime
    window_end: datetime
    status: str
    price_to_beat: Decimal | None
    settlement_price: Decimal | None
    fee_coefficient: Decimal | None
    tick_size: Decimal | None
    min_qty: Decimal | None
    up_side_label: str
    down_side_label: str
    description: str
    source: Source = Source.GATEWAY

    def seconds_to_close(self, now: datetime) -> float:
        return (self.window_end - now).total_seconds()

    def settled_outcome(self) -> Outcome | None:
        if self.price_to_beat is None or self.settlement_price is None:
            return None
        from polyquant.domain.settlement import outcome_from_prices

        return outcome_from_prices(self.price_to_beat, self.settlement_price)


def phase_of(inst: Instrument, now: datetime) -> Phase:
    """Derive the lifecycle phase from venue status, settlement fields and the clock together.

    Observed venue behaviour (docs/RESEARCH_AUDIT.md §1.2): upcoming windows report
    MARKET_STATUS_CLOSED, open windows MARKET_STATUS_OPEN, settled ones MARKET_STATUS_RESOLVED.
    """
    resolved = inst.status == "MARKET_STATUS_RESOLVED"
    if inst.settlement_price is not None:
        return Phase.SETTLED if (resolved or now >= inst.window_end) else Phase.UNKNOWN
    if resolved:
        return Phase.UNKNOWN  # resolved without a settlement price: never guess
    if now < inst.window_start:
        return Phase.UPCOMING
    if now < inst.window_end:
        return Phase.OPEN if inst.status == "MARKET_STATUS_OPEN" else Phase.UNKNOWN
    return Phase.AWAITING_SETTLEMENT


@dataclass(frozen=True, slots=True)
class IndexPoint:
    """One point of the venue's 1s reference series (trailing 60s average of BRTI, see RESEARCH_AUDIT §1.3)."""

    asset: str
    ts: datetime  # candle timestamp from the venue (source time)
    value: Decimal
    tick_count: int
    recv_at: datetime
    source: Source = Source.GATEWAY


@dataclass(frozen=True, slots=True)
class BBOSnapshot:
    """Top of book for one instrument. Prices are for the long (Up) side as quoted by the venue."""

    slug: str
    best_bid: Decimal | None
    best_ask: Decimal | None
    bid_depth: int | None  # number of price levels
    ask_depth: int | None
    bid_shares: Decimal | None  # semantics unverified (RESEARCH_AUDIT §4)
    ask_shares: Decimal | None
    last_trade_px: Decimal | None
    current_px: Decimal | None
    shares_traded: Decimal | None
    open_interest: Decimal | None
    state: str | None
    last_trade_ts: datetime | None  # venue trade time, NOT a quote timestamp
    sent_at: datetime
    recv_at: datetime
    source: Source = Source.GATEWAY
    raw: dict = field(default_factory=dict, compare=False, repr=False)

    # Up = long side of the instrument.
    @property
    def up_bid(self) -> Decimal | None:
        return self.best_bid

    @property
    def up_ask(self) -> Decimal | None:
        return self.best_ask

    # Down = short side of the same book: buying Down sells into the Up bid, and vice versa.
    @property
    def down_bid(self) -> Decimal | None:
        return None if self.best_ask is None else ONE - self.best_ask

    @property
    def down_ask(self) -> Decimal | None:
        return None if self.best_bid is None else ONE - self.best_bid

    @property
    def spread(self) -> Decimal | None:
        if self.best_bid is None or self.best_ask is None:
            return None
        return self.best_ask - self.best_bid

    @property
    def mid(self) -> Decimal | None:
        if self.best_bid is None or self.best_ask is None:
            return None
        return (self.best_ask + self.best_bid) / 2

    @property
    def crossed(self) -> bool:
        return self.best_bid is not None and self.best_ask is not None and self.best_bid >= self.best_ask

    @property
    def rtt_ms(self) -> float:
        return (self.recv_at - self.sent_at).total_seconds() * 1000
