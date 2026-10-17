"""Settlement rule for BTC Up/Down markets.

Documented rule (docs.polymarket.us/trader-guide/crypto-schema): open and close are each the mean of the
60 per-second BRTI prices in [T-60s, T), rounded to 2 dp; Up pays if close >= open (a flat result is Up).

Empirical finding (docs/RESEARCH_AUDIT.md §1.3): the venue's public 1s index series is already that
trailing average, so the official value for instant T equals the series point stamped T-1s.
The venue's own priceToBeat / settlementPrice stay authoritative; derived values are cross-checks only.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from polyquant.domain.models import Instrument, Outcome

REFERENCE_OFFSET = timedelta(seconds=1)


def outcome_from_prices(open_price: Decimal, close_price: Decimal) -> Outcome:
    return Outcome.UP if close_price >= open_price else Outcome.DOWN


def outcome_from_settlement_flag(flag: int) -> Outcome:
    """Map the venue's /settlement value (1 = long/Yes paid, 0 = short/No paid)."""
    if flag == 1:
        return Outcome.UP
    if flag == 0:
        return Outcome.DOWN
    raise ValueError(f"unexpected settlement flag {flag!r}")


def reference_ts(instant: datetime) -> datetime:
    """Timestamp of the index point that carries the official reference for `instant`."""
    return instant - REFERENCE_OFFSET


def derived_reference(series: Mapping[datetime, Decimal], instant: datetime) -> Decimal | None:
    return series.get(reference_ts(instant))


@dataclass(frozen=True, slots=True)
class ReferenceCheck:
    slug: str
    kind: str  # "open" | "close"
    official: Decimal | None
    derived: Decimal | None

    @property
    def comparable(self) -> bool:
        return self.official is not None and self.derived is not None

    @property
    def matches(self) -> bool:
        return self.comparable and self.official == self.derived


def check_references(inst: Instrument, series: Mapping[datetime, Decimal]) -> list[ReferenceCheck]:
    return [
        ReferenceCheck(inst.slug, "open", inst.price_to_beat, derived_reference(series, inst.window_start)),
        ReferenceCheck(inst.slug, "close", inst.settlement_price, derived_reference(series, inst.window_end)),
    ]
