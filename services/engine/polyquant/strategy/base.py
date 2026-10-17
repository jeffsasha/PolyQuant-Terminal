"""Strategy interface shared by backtest, replay and live paper trading, with structural look-ahead protection.

Strategies never see the full instrument or the full series:
- `PITInstrument` has no settlement fields at all, and `price_to_beat` is only present once it was available.
- `PointInTimeSeries` raises `LookaheadError` on any access past the decision time minus the publish lag.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

import numpy as np

from polyquant.domain.models import Horizon, Instrument
from polyquant.domain.timeutil import to_unix
from polyquant.marketdata.book import BookSnapshot
from polyquant.paper.models import OrderIntent

# priceToBeat is observed live a few seconds after window start (RESEARCH_AUDIT §1.2: ~4 s). Backtests treat it as
# unavailable before this delay so they never act on a value the live system could not yet have had.
PRICE_TO_BEAT_AVAILABLE_AFTER_S = 5
INDEX_PUBLISH_LAG_S = 1


class LookaheadError(RuntimeError):
    pass


class PointInTimeSeries:
    """Read-only view of the 1s reference series as of `now`. Index points are stamped with the second they
    describe; the point for second s is treated as observable from s + publish_lag."""

    def __init__(self, ts: np.ndarray, values: np.ndarray, now_unix: int, publish_lag_s: int = INDEX_PUBLISH_LAG_S):
        self._ts = ts
        self._v = values
        self.now_unix = now_unix
        self.cutoff = now_unix - publish_lag_s
        self._hi = int(np.searchsorted(ts, self.cutoff, side="right"))  # exclusive end of visible data

    def _check(self, t: int) -> None:
        if t > self.cutoff:
            raise LookaheadError(f"access to index second {t} at decision time {self.now_unix} (cutoff {self.cutoff})")

    def latest(self) -> tuple[int, float] | None:
        if self._hi == 0:
            return None
        return int(self._ts[self._hi - 1]), float(self._v[self._hi - 1])

    def value_at(self, t: int) -> float | None:
        self._check(t)
        i = int(np.searchsorted(self._ts, t))
        if i < self._hi and self._ts[i] == t:
            return float(self._v[i])
        return None

    def window(self, start: int, end: int) -> tuple[np.ndarray, np.ndarray]:
        """Points with start <= ts <= end. Raises if end is in the future."""
        self._check(end)
        lo = int(np.searchsorted(self._ts, start, side="left"))
        hi = min(self._hi, int(np.searchsorted(self._ts, end, side="right")))
        return self._ts[lo:hi], self._v[lo:hi]


@dataclass(frozen=True, slots=True)
class PITInstrument:
    slug: str
    horizon: Horizon
    window_start: datetime
    window_end: datetime
    price_to_beat: Decimal | None  # None until observable
    tick_size: Decimal
    min_qty: Decimal
    fee_coefficient: Decimal | None

    @classmethod
    def from_instrument(cls, inst: Instrument, now: datetime) -> PITInstrument:
        ptb_visible = (now - inst.window_start).total_seconds() >= PRICE_TO_BEAT_AVAILABLE_AFTER_S
        return cls(slug=inst.slug, horizon=inst.horizon, window_start=inst.window_start,
                   window_end=inst.window_end, price_to_beat=inst.price_to_beat if ptb_visible else None,
                   tick_size=inst.tick_size or Decimal("0.01"), min_qty=inst.min_qty or Decimal("0.01"),
                   fee_coefficient=inst.fee_coefficient)

    @property
    def target_unix(self) -> int:
        """Second whose index value is the official close (window_end − 1 s)."""
        return to_unix(self.window_end) - 1


@dataclass(frozen=True, slots=True)
class MarketSnapshot:
    now: datetime
    instrument: PITInstrument
    series: PointInTimeSeries
    book: BookSnapshot | None = None
    held_up: Decimal = Decimal(0)
    held_down: Decimal = Decimal(0)


class Signal(StrEnum):
    BUY_UP = "BUY_UP"
    BUY_DOWN = "BUY_DOWN"
    EXIT = "EXIT"
    HOLD = "HOLD"
    NO_TRADE = "NO_TRADE"


@dataclass(frozen=True, slots=True)
class Decision:
    signal: Signal
    p_up: float | None
    intents: tuple[OrderIntent, ...] = ()
    why: dict = field(default_factory=dict)


class Strategy(Protocol):
    name: str

    def decide(self, snap: MarketSnapshot) -> Decision: ...

