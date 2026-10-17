"""Explicit interfaces shared by live, paper, replay and (future) live-trading code paths.

Phase 2a implements the market-data side. Execution-side protocols are declared now so later phases build on a
fixed contract; their implementations arrive in Phase 3 (see docs/IMPLEMENTATION_PLAN.md).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol

from polyquant.domain.models import BBOSnapshot, Horizon, IndexPoint, Instrument, TradePrint


class MarketDataProvider(Protocol):
    def instruments(self) -> list[Instrument]: ...
    def current(self, horizon: Horizon, now: datetime) -> Instrument | None: ...
    def next(self, horizon: Horizon, now: datetime) -> Instrument | None: ...
    def latest_bbo(self, slug: str) -> BBOSnapshot | None: ...


class ReferencePriceProvider(Protocol):
    def latest(self) -> IndexPoint | None: ...
    def value_at(self, ts: datetime) -> Decimal | None: ...
    def is_stale(self, now: datetime) -> bool: ...


class SettlementProvider(Protocol):
    async def settlement_flag(self, slug: str) -> int | None: ...


class EventSink(Protocol):
    """Receives everything the data layer observes. Implementations must not block the caller."""

    def instrument_changed(self, inst: Instrument, changes: dict[str, Any], observed_at: datetime) -> None: ...
    def index_points(self, points: list[IndexPoint]) -> None: ...
    def bbo(self, snap: BBOSnapshot) -> None: ...
    def book(self, snap: Any) -> None: ...  # marketdata.book.BookSnapshot (full validated L2 book)
    def trade(self, trade: TradePrint) -> None: ...
    def spot_bars(self, bars: list) -> None: ...  # spot.kraken.SpotBar
    def quality_event(self, feed: str, kind: str, detail: dict[str, Any], at: datetime) -> None: ...


# ---- Phase 3+ (declared, not implemented in 2a) ----------------------------------------------------

class FeeModel(Protocol):
    def taker_fee(self, qty: Decimal, price: Decimal, at: datetime) -> Decimal: ...


class RiskManager(Protocol):
    def check(self, intent: Any, context: Any) -> Any: ...


class ExecutionEngine(Protocol):
    async def submit(self, order: Any) -> Any: ...
    async def cancel(self, order_id: str) -> Any: ...


class PortfolioLedger(Protocol):
    async def record_fill(self, fill: Any) -> None: ...


class Strategy(Protocol):
    name: str

    def on_market(self, snapshot: Any) -> Any: ...


class FanoutSink:
    def __init__(self, *sinks: EventSink) -> None:
        self._sinks = list(sinks)

    def add(self, sink: EventSink) -> None:
        self._sinks.append(sink)

    def instrument_changed(self, inst, changes, observed_at) -> None:
        for s in self._sinks:
            s.instrument_changed(inst, changes, observed_at)

    def index_points(self, points) -> None:
        for s in self._sinks:
            s.index_points(points)

    def bbo(self, snap) -> None:
        for s in self._sinks:
            s.bbo(snap)

    def book(self, snap) -> None:
        for s in self._sinks:
            s.book(snap)

    def trade(self, trade) -> None:
        for s in self._sinks:
            s.trade(trade)

    def spot_bars(self, bars) -> None:
        for s in self._sinks:
            s.spot_bars(bars)

    def quality_event(self, feed, kind, detail, at) -> None:
        for s in self._sinks:
            s.quality_event(feed, kind, detail, at)


class NullSink(FanoutSink):
    def __init__(self) -> None:
        super().__init__()


class MemorySink:
    """Collects events in lists; used by tests and the API's recent-alerts view."""

    def __init__(self, keep: int = 1000) -> None:
        self.keep = keep
        self.instrument_events: list[tuple[Instrument, dict, datetime]] = []
        self.points: list[IndexPoint] = []
        self.bbos: list[BBOSnapshot] = []
        self.books: list = []
        self.trades: list[TradePrint] = []
        self.spot: list = []
        self.quality: list[tuple[str, str, dict, datetime]] = []

    def _trim(self, xs: list) -> None:
        if len(xs) > self.keep:
            del xs[: len(xs) - self.keep]

    def instrument_changed(self, inst, changes, observed_at) -> None:
        self.instrument_events.append((inst, changes, observed_at))
        self._trim(self.instrument_events)

    def index_points(self, points) -> None:
        self.points.extend(points)
        self._trim(self.points)

    def bbo(self, snap) -> None:
        self.bbos.append(snap)
        self._trim(self.bbos)

    def book(self, snap) -> None:
        self.books.append(snap)
        self._trim(self.books)

    def trade(self, trade) -> None:
        self.trades.append(trade)
        self._trim(self.trades)

    def spot_bars(self, bars) -> None:
        self.spot.extend(bars)
        self._trim(self.spot)

    def quality_event(self, feed, kind, detail, at) -> None:
        self.quality.append((feed, kind, detail, at))
        self._trim(self.quality)
