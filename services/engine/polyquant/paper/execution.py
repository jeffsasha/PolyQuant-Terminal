"""Pure execution model: order-book sweeps and a conservative maker queue model, under four assumption profiles.

Nothing here touches I/O, so live paper trading and replay share it exactly.

Mapping onto the single instrument book (RESEARCH_AUDIT §1.6, ARCHITECTURE §3):
- BUY Up   consumes Up asks (book offers) with px ≤ limit
- SELL Up  hits Up bids (book bids) with px ≥ limit
- BUY Down consumes Down asks = 1 − Up bids (so it sells into the Up bids)
- SELL Down hits Down bids = 1 − Up asks
A buy never fills at the last trade or the mid: it walks the opposite side level by level (VWAP across levels).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal

from polyquant.domain.models import ONE, Outcome
from polyquant.marketdata.book import BookSnapshot, Level
from polyquant.paper.models import Side

ZERO = Decimal(0)


@dataclass(frozen=True, slots=True)
class ExecutionProfile:
    name: str
    latency_ms: int  # submit → venue arrival (assumption; no live order latency has been measured)
    depth_haircut: Decimal  # fraction of displayed size assumed actually available to us
    slippage_ticks: int  # adverse ticks applied to every taker fill price (levels pushed past the limit drop out)
    # maker model
    maker_touch_fills: bool  # optimistic: being touched at our price fills us
    maker_depletion_attribution: Decimal  # share of displayed-size decreases at our level counted as fills ahead
    maker_through_ticks: int  # opposite side must trade this many ticks through our price to fill us
    maker_through_fraction: Decimal  # fraction of remaining qty filled on a trade-through
    max_book_age_ms: int  # refuse to fill against a book older than this at arrival
    diagnostic_only: bool = False


PROFILES: dict[str, ExecutionProfile] = {
    # Diagnostic upper bound — never use for decisions or reported performance.
    "optimistic": ExecutionProfile("optimistic", 0, Decimal("1.0"), 0, True, Decimal("1.0"), 0, Decimal("1.0"),
                                   5000, diagnostic_only=True),
    # Base: assumptions, not yet calibrated against real order outcomes (no live orders exist).
    "base": ExecutionProfile("base", 250, Decimal("0.8"), 0, False, Decimal("0.5"), 1, Decimal("1.0"), 2000),
    "conservative": ExecutionProfile("conservative", 750, Decimal("0.5"), 1, False, Decimal("0.0"), 1,
                                     Decimal("1.0"), 1500),
    "stress": ExecutionProfile("stress", 2000, Decimal("0.25"), 2, False, Decimal("0.0"), 2, Decimal("0.5"), 1000),
}

VENUE_LATENCY_REJECT_MS = 5000  # orders not processed within 5 s are rejected by the venue (rate-limits doc)


def outcome_ladders(book: BookSnapshot, outcome: Outcome) -> tuple[tuple[Level, ...], tuple[Level, ...]]:
    """(bids, asks) for the outcome, best first."""
    if outcome is Outcome.UP:
        return book.bids, book.offers
    return book.down_bids(), book.down_asks()


def instrument_px(outcome: Outcome, px: Decimal) -> Decimal:
    return px if outcome is Outcome.UP else ONE - px


def quantize_qty(qty: Decimal, min_qty: Decimal) -> Decimal:
    if qty <= 0:
        return ZERO
    return (qty / min_qty).to_integral_value(rounding=ROUND_DOWN) * min_qty


@dataclass(frozen=True, slots=True)
class SweepFill:
    qty: Decimal
    px: Decimal  # outcome price after slippage
    level_px: Decimal  # displayed level price


@dataclass(frozen=True, slots=True)
class SweepResult:
    fills: tuple[SweepFill, ...]
    requested: Decimal
    best_px: Decimal | None  # best opposite price before the sweep
    mid: Decimal | None  # outcome mid before the sweep

    @property
    def filled(self) -> Decimal:
        return sum((f.qty for f in self.fills), ZERO)

    @property
    def notional(self) -> Decimal:
        return sum((f.qty * f.px for f in self.fills), ZERO)

    @property
    def vwap(self) -> Decimal | None:
        q = self.filled
        return None if q == 0 else self.notional / q


def outcome_mid(book: BookSnapshot, outcome: Outcome) -> Decimal | None:
    bids, asks = outcome_ladders(book, outcome)
    if not bids or not asks:
        return None
    return (bids[0].px + asks[0].px) / 2


def sweep(book: BookSnapshot, outcome: Outcome, side: Side, qty: Decimal, limit_px: Decimal,
          profile: ExecutionProfile, *, tick: Decimal = Decimal("0.01"), min_qty: Decimal = Decimal("0.01"),
          consumed: dict[Decimal, Decimal] | None = None) -> SweepResult:
    """Size-aware sweep of the opposite side within the limit. `consumed` lets callers account for liquidity they
    already took from this book state (so two orders cannot both take the same displayed size)."""
    bids, asks = outcome_ladders(book, outcome)
    levels = asks if side is Side.BUY else bids
    best = levels[0].px if levels else None
    fills: list[SweepFill] = []
    left = qty
    slip = tick * profile.slippage_ticks
    for lv in levels:
        if left <= 0:
            break
        px = lv.px + slip if side is Side.BUY else lv.px - slip
        if (side is Side.BUY and px > limit_px) or (side is Side.SELL and px < limit_px):
            break  # this and all worse levels are outside the limit
        if not (ZERO < px < ONE):
            break
        avail = lv.qty * profile.depth_haircut - (consumed or {}).get(lv.px, ZERO)
        take = quantize_qty(min(left, avail), min_qty)
        if take <= 0:
            continue
        fills.append(SweepFill(take, px, lv.px))
        if consumed is not None:
            consumed[lv.px] = consumed.get(lv.px, ZERO) + take
        left -= take
    return SweepResult(tuple(fills), qty, best, outcome_mid(book, outcome))


def is_marketable(book: BookSnapshot, outcome: Outcome, side: Side, limit_px: Decimal) -> bool:
    bids, asks = outcome_ladders(book, outcome)
    if side is Side.BUY:
        return bool(asks) and asks[0].px <= limit_px
    return bool(bids) and bids[0].px >= limit_px


def level_qty(levels: tuple[Level, ...], px: Decimal) -> Decimal:
    for lv in levels:
        if lv.px == px:
            return lv.qty
    return ZERO


@dataclass(frozen=True, slots=True)
class MakerUpdate:
    fill_qty: Decimal
    queue_ahead: Decimal
    level_qty: Decimal
    reason: str  # touch | through | depleted | none


def maker_step(book: BookSnapshot, outcome: Outcome, side: Side, limit_px: Decimal, remaining: Decimal,
               queue_ahead: Decimal, last_level_qty: Decimal, profile: ExecutionProfile, *,
               tick: Decimal = Decimal("0.01"), min_qty: Decimal = Decimal("0.01")) -> MakerUpdate:
    """Advance a resting order by one book state. Without per-order queue data, being touched is not a fill unless
    the queue ahead is shown to be consumed; a trade-through (opposite side beyond our price, which in the real book
    means aggressive flow crossed our level) fills us according to the profile."""
    bids, asks = outcome_ladders(book, outcome)
    own = bids if side is Side.BUY else asks
    opp = asks if side is Side.BUY else bids
    cur_level = level_qty(own, limit_px)
    # queue depletion: part of any decrease in displayed size at our price is attributed to fills ahead of us
    if cur_level < last_level_qty:
        queue_ahead = max(ZERO, queue_ahead - (last_level_qty - cur_level) * profile.maker_depletion_attribution)
    if not opp:
        return MakerUpdate(ZERO, queue_ahead, cur_level, "none")
    best_opp = opp[0].px
    through = (limit_px - best_opp) if side is Side.BUY else (best_opp - limit_px)  # >0: opposite crossed our px
    ticks_through = (through / tick).to_integral_value(rounding=ROUND_DOWN) if through > 0 else Decimal(-1)
    if profile.maker_touch_fills and through >= 0:
        return MakerUpdate(quantize_qty(remaining, min_qty), ZERO, cur_level, "touch")
    if through > 0 and ticks_through >= profile.maker_through_ticks:
        return MakerUpdate(quantize_qty(remaining * profile.maker_through_fraction, min_qty), ZERO, cur_level,
                           "through")
    if through == 0 and queue_ahead <= 0 and profile.maker_depletion_attribution > 0:
        # touched with the queue ahead consumed: fill against the displayed opposite size at our price
        avail = level_qty(opp, limit_px) * profile.depth_haircut
        return MakerUpdate(quantize_qty(min(remaining, avail), min_qty), ZERO, cur_level, "depleted")
    return MakerUpdate(ZERO, queue_ahead, cur_level, "none")
