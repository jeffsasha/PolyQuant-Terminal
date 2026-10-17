"""Turns markets-WebSocket frames into validated L2 books and trade prints, and reconciles them with REST BBO."""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

from polyquant.clock import Clock
from polyquant.domain.models import BBOSnapshot, TradePrint
from polyquant.domain.timeutil import parse_utc
from polyquant.interfaces import EventSink
from polyquant.marketdata.book import BookRejected, BookSnapshot, L2Book, parse_book_frame
from polyquant.marketdata.quality import ClockSkewMonitor, DataHealth

log = logging.getLogger(__name__)


def book_feed_name(slug: str) -> str:
    return f"book:{slug}"


@dataclass
class ReconcileStats:
    """REST BBO vs WS top-of-book.

    - match: a WS top within the window around the REST body's production time equals it (strict, time-aligned).
    - corroborated: the REST top appears anywhere in the WS history from `lookback` before that time to the end of
      the window. Live finding: REST is CDN-cached (≤30 s) and its origin sometimes lags the WS by a further 3-9 s,
      so "corroborated" is the meaningful integrity signal and "match" measures REST staleness.
    """

    samples: int = 0
    matches: int = 0
    corroborated: int = 0
    no_ws_data: int = 0
    level_count_samples: int = 0
    level_count_matches: int = 0
    mismatches: deque = field(default_factory=lambda: deque(maxlen=50))

    @property
    def match_rate(self) -> float | None:
        compared = self.samples - self.no_ws_data
        return None if compared <= 0 else self.matches / compared

    def as_dict(self) -> dict:
        lc = self.level_count_samples
        compared = self.samples - self.no_ws_data
        return {"samples": self.samples, "compared": compared, "matches": self.matches,
                "match_rate": self.match_rate, "corroborated": self.corroborated,
                "corroborated_rate": None if compared <= 0 else self.corroborated / compared,
                "no_ws_data": self.no_ws_data,
                "level_count_match_rate": None if lc == 0 else self.level_count_matches / lc,
                "recent_mismatches": list(self.mismatches)[-10:]}


class BookService:
    def __init__(self, sink: EventSink, clock: Clock, health: DataHealth, *, stale_after_s: float = 10.0,
                 reconcile_window_s: float = 2.0, reconcile_lookback_s: float = 60.0,
                 reconcile_min_history_s: float = 15.0,
                 skew: ClockSkewMonitor | None = None) -> None:
        self._sink = sink
        self._clock = clock
        self._health = health
        self._stale_after = stale_after_s
        self._window = timedelta(seconds=reconcile_window_s)
        self._lookback = timedelta(seconds=reconcile_lookback_s)
        self._min_history = timedelta(seconds=reconcile_min_history_s)
        self.books: dict[str, L2Book] = {}
        self._tops: dict[str, deque] = {}  # slug -> deque[(recv_at, bid, ask, n_bids, n_offers)]
        self.reconcile = ReconcileStats()
        self.rejected: dict[str, int] = {}
        self.trades = 0
        self.heartbeats = 0
        self.control_frames = 0
        self.skew = skew

    # ---- subscription bookkeeping --------------------------------------------------------------

    def track(self, slugs: list[str]) -> None:
        """Keep books/feeds only for the given slugs."""
        want = set(slugs)
        for s in list(self.books):
            if s not in want:
                del self.books[s]
                self._tops.pop(s, None)
                self._health.unregister(book_feed_name(s))
        for s in want:
            if s not in self.books:
                self.books[s] = L2Book(s)
                self._tops[s] = deque(maxlen=3000)  # ~5 min of tops at observed rates

    def watch_open(self, open_slugs: list[str]) -> None:
        """Only OPEN instruments get a staleness feed: upcoming markets legitimately send nothing."""
        for s in self.books:
            name = book_feed_name(s)
            if s in open_slugs:
                self._health.register(name, self._stale_after)
            else:
                self._health.unregister(name)

    def latest(self, slug: str) -> BookSnapshot | None:
        b = self.books.get(slug)
        return None if b is None else b.snapshot

    # ---- frames ----------------------------------------------------------------------------------

    def on_frame(self, frame: dict, recv_at: datetime) -> None:
        if "marketData" in frame:
            self._on_book(frame, recv_at)
        elif "trade" in frame:
            self._on_trade(frame, recv_at)
        elif "heartbeat" in frame:
            self.heartbeats += 1
        elif "unsubscribed" in frame or "subscribed" in frame:
            self.control_frames += 1  # server acknowledgements of (un)subscribe requests (observed live)
        elif "error" in frame:
            self._sink.quality_event("ws", "server_error", {"error": str(frame.get("error")),
                                                            "requestId": frame.get("requestId")}, recv_at)
        else:
            self._sink.quality_event("ws", "unknown_frame", {"keys": sorted(frame.keys())}, recv_at)

    def _reject(self, kind: str, detail: str, at: datetime) -> None:
        self.rejected[kind] = self.rejected.get(kind, 0) + 1
        self._sink.quality_event("book", f"frame_rejected:{kind}", {"detail": detail}, at)

    def _on_book(self, frame: dict, recv_at: datetime) -> None:
        try:
            snap = parse_book_frame(frame, recv_at)
        except BookRejected as exc:
            self._reject(exc.kind, exc.detail, recv_at)
            return
        book = self.books.get(snap.slug)
        if book is None:
            return  # frame for a market we no longer track (late frame after unsubscribe)
        try:
            changed = book.apply(snap)
        except BookRejected as exc:
            self._reject(exc.kind, exc.detail, recv_at)
            return
        if self.skew is not None:
            self.skew.observe(recv_at, snap.transact_time)
        self._tops[snap.slug].append((recv_at, snap.best_bid, snap.best_ask, len(snap.bids), len(snap.offers)))
        fh = self._health.feeds.get(book_feed_name(snap.slug))
        if fh is not None:
            fh.mark(recv_at, snap.transact_time, (recv_at - snap.transact_time).total_seconds() * 1000)
        if changed:
            self._sink.book(snap)

    def _on_trade(self, frame: dict, recv_at: datetime) -> None:
        t = frame.get("trade") or {}
        try:
            qty = t["quantity"]
            tp = TradePrint(
                trade_id=str(t["id"]) if t.get("id") is not None else None,
                slug=t["marketSlug"],
                price=Decimal(str(t["price"]["value"])),
                quantity=Decimal(str(qty["value"] if isinstance(qty, dict) else qty)),
                quantity_unit=qty.get("currency") if isinstance(qty, dict) else None,
                trade_time=parse_utc(t["tradeTime"]),
                maker_side=(t.get("maker") or {}).get("side"),
                taker_side=(t.get("taker") or {}).get("side"),
                recv_at=recv_at,
                raw=t,
            )
        except (KeyError, TypeError, ValueError, ArithmeticError) as exc:
            self._reject("bad_trade", f"{exc!r}", recv_at)
            return
        self.trades += 1
        self._sink.trade(tp)

    # ---- reconciliation with REST BBO ----------------------------------------------------------------

    def reconcile_bbo(self, rest: BBOSnapshot) -> bool | None:
        """Compare a REST BBO sample with WS tops seen around the same time. None = nothing to compare."""
        tops = self._tops.get(rest.slug)
        self.reconcile.samples += 1
        if not tops:
            self.reconcile.no_ws_data += 1
            return None
        # Align on when the REST body was produced (CDN-cached up to 30 s), not when we received it.
        # Last-Modified has 1 s precision (floored), hence the asymmetric window.
        if rest.data_as_of is not None:
            lo, hi = rest.data_as_of - self._window, rest.data_as_of + timedelta(seconds=1) + self._window
        else:
            lo, hi = rest.sent_at - self._window, rest.recv_at + self._window
        # Need WS history from well before the REST body's time: REST can reflect the book several seconds earlier
        # still (origin lag). Live finding: right after start-up this produced false "uncorroborated" results.
        rest_time = rest.data_as_of or rest.sent_at
        if tops[0][0] > rest_time - self._min_history:
            self.reconcile.no_ws_data += 1
            return None
        near = [t for t in tops if lo <= t[0] <= hi]
        history = [t for t in tops if lo - self._lookback <= t[0] <= hi]
        if not history:
            self.reconcile.no_ws_data += 1
            return None
        same = lambda t: t[1] == rest.best_bid and t[2] == rest.best_ask  # noqa: E731
        ok = any(same(t) for t in near)
        corroborated = any(same(t) for t in history)
        if corroborated:
            self.reconcile.corroborated += 1
        if rest.bid_depth is not None and rest.ask_depth is not None:
            self.reconcile.level_count_samples += 1
            if any(t[3] == rest.bid_depth and t[4] == rest.ask_depth for t in near):
                self.reconcile.level_count_matches += 1
        if ok:
            self.reconcile.matches += 1
        else:
            last = (near or history)[-1]
            detail = {"slug": rest.slug, "rest_bid": str(rest.best_bid), "rest_ask": str(rest.best_ask),
                      "ws_bid": str(last[1]), "ws_ask": str(last[2]), "at": rest.recv_at.isoformat(),
                      "rest_data_as_of": rest.data_as_of.isoformat() if rest.data_as_of else None,
                      "cache": rest.cache_status, "corroborated": corroborated}
            self.reconcile.mismatches.append(detail)
            # Only values never seen in the WS book are an integrity problem; delayed REST is expected.
            kind = "bbo_delayed" if corroborated else "bbo_uncorroborated"
            self._sink.quality_event("reconcile", kind, detail, rest.recv_at)
        return ok
