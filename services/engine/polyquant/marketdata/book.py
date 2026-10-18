"""Local L2 order book for one instrument, fed by full-book WebSocket frames.

Observed (docs/RESEARCH_AUDIT.md §1.6): every MARKET_DATA frame carries the complete book, not a delta, so applying a
frame means validating it and replacing the book. Validation failures reject the frame and keep the previous book.
Prices are for the long (Up) side; Down liquidity is the opposite side of the same book.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from polyquant.domain.models import ONE, Source
from polyquant.domain.timeutil import parse_utc


@dataclass(frozen=True, slots=True)
class Level:
    px: Decimal
    qty: Decimal


class BookRejected(ValueError):
    def __init__(self, kind: str, detail: str) -> None:
        super().__init__(f"{kind}: {detail}")
        self.kind = kind
        self.detail = detail


@dataclass(frozen=True, slots=True)
class BookSnapshot:
    slug: str
    bids: tuple[Level, ...]  # best (highest) first
    offers: tuple[Level, ...]  # best (lowest) first
    state: str | None
    transact_time: datetime
    recv_at: datetime
    stats: dict = field(default_factory=dict, compare=False, repr=False)
    source: Source = Source.WS

    @property
    def best_bid(self) -> Decimal | None:
        return self.bids[0].px if self.bids else None

    @property
    def best_ask(self) -> Decimal | None:
        return self.offers[0].px if self.offers else None

    @property
    def spread(self) -> Decimal | None:
        if self.best_bid is None or self.best_ask is None:
            return None
        return self.best_ask - self.best_bid

    @property
    def mid(self) -> Decimal | None:
        if self.best_bid is None or self.best_ask is None:
            return None
        return (self.best_bid + self.best_ask) / 2

    def microprice(self) -> Decimal | None:
        """Size-weighted mid using top-of-book quantities (meaningful only when both sides are quoted)."""
        if not self.bids or not self.offers:
            return None
        b, a = self.bids[0], self.offers[0]
        tot = b.qty + a.qty
        return None if tot == 0 else (a.px * b.qty + b.px * a.qty) / tot

    def imbalance(self, levels: int = 1) -> Decimal | None:
        """(bid qty - ask qty) / (bid qty + ask qty) over the top `levels` levels; in [-1, 1]."""
        bq = sum((lv.qty for lv in self.bids[:levels]), Decimal(0))
        aq = sum((lv.qty for lv in self.offers[:levels]), Decimal(0))
        tot = bq + aq
        return None if tot == 0 else (bq - aq) / tot

    # Down (short side) as seen by a Down buyer/seller.
    def down_asks(self) -> tuple[Level, ...]:
        """Buying Down = selling Up into the bids: Down ask levels are 1 - bid px, best first."""
        return tuple(Level(ONE - lv.px, lv.qty) for lv in self.bids)

    def down_bids(self) -> tuple[Level, ...]:
        return tuple(Level(ONE - lv.px, lv.qty) for lv in self.offers)

    def depth(self, side: str, max_levels: int | None = None) -> Decimal:
        levels = self.bids if side == "bid" else self.offers
        return sum((lv.qty for lv in levels[:max_levels]), Decimal(0))


def _levels(raw: list, slug: str, side: str) -> tuple[Level, ...]:
    out = []
    for lv in raw or []:
        try:
            px = lv["px"]["value"] if isinstance(lv.get("px"), dict) else lv["px"]
            if isinstance(lv.get("px"), dict) and lv["px"].get("currency") not in (None, "USD"):
                raise BookRejected("bad_level", f"{slug} {side} non-USD price")
            if isinstance(px, float) or isinstance(lv["qty"], float):
                raise BookRejected("bad_level", f"{slug} {side} binary float")
            out.append(Level(Decimal(str(px)), Decimal(str(lv["qty"]))))
        except (KeyError, TypeError, ArithmeticError) as exc:
            raise BookRejected("bad_level", f"{slug} {side} malformed level {lv!r}") from exc
    return tuple(out)


def validate_levels(slug: str, bids: tuple[Level, ...], offers: tuple[Level, ...]) -> None:
    for side, levels, desc in (("bids", bids, True), ("offers", offers, False)):
        pxs = [lv.px for lv in levels]
        if pxs != sorted(pxs, reverse=desc):
            raise BookRejected("unsorted", f"{slug} {side} not sorted best-first")
        if len(pxs) != len(set(pxs)):
            raise BookRejected("duplicate_level", f"{slug} {side} repeats a price")
        if any(lv.qty <= 0 for lv in levels):
            raise BookRejected("non_positive_qty", f"{slug} {side} has qty <= 0")
        if any(not (Decimal(0) < lv.px < ONE) for lv in levels):
            raise BookRejected("price_out_of_range", f"{slug} {side} price outside (0, 1)")
    if bids and offers and bids[0].px >= offers[0].px:
        raise BookRejected("crossed", f"{slug} bid {bids[0].px} >= ask {offers[0].px}")


def parse_book_frame(payload: dict, recv_at: datetime) -> BookSnapshot:
    md = payload.get("marketData")
    if not isinstance(md, dict) or not md.get("marketSlug"):
        raise BookRejected("malformed", "frame without marketData.marketSlug")
    slug = md["marketSlug"]
    if not md.get("transactTime"):
        raise BookRejected("malformed", f"{slug} frame without transactTime")
    bids = _levels(md.get("bids"), slug, "bids")
    offers = _levels(md.get("offers"), slug, "offers")
    validate_levels(slug, bids, offers)
    return BookSnapshot(slug=slug, bids=bids, offers=offers, state=md.get("state"),
                        transact_time=parse_utc(md["transactTime"]), recv_at=recv_at, stats=md.get("stats") or {})


class L2Book:
    """Current validated book for one instrument with ordering protection."""

    def __init__(self, slug: str) -> None:
        self.slug = slug
        self.snapshot: BookSnapshot | None = None
        self.frames = 0
        self.rejected = 0

    def apply(self, snap: BookSnapshot) -> bool:
        """Returns True if the book changed. Raises BookRejected for out-of-order frames."""
        if snap.slug != self.slug:
            raise BookRejected("slug_mismatch", f"{snap.slug} applied to {self.slug}")
        prev = self.snapshot
        if prev is not None and snap.transact_time < prev.transact_time:
            self.rejected += 1
            raise BookRejected("out_of_order", f"{self.slug} {snap.transact_time} < {prev.transact_time}")
        self.frames += 1
        self.snapshot = snap
        return prev is None or prev.bids != snap.bids or prev.offers != snap.offers or prev.state != snap.state
