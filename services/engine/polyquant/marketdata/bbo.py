"""Round-robin BBO poller over OPEN instruments (REST; replaced by the authenticated WS in Phase 2b)."""

from __future__ import annotations

import logging
from datetime import datetime

from polyquant.clock import Clock
from polyquant.domain.models import BBOSnapshot, Phase, phase_of
from polyquant.interfaces import EventSink
from polyquant.marketdata.discovery import InstrumentRegistry
from polyquant.marketdata.quality import DataHealth
from polyquant.venue.gateway import GatewayClient, GatewayError
from polyquant.venue.parsing import ParseError, parse_bbo

log = logging.getLogger(__name__)


def bbo_feed_name(slug: str) -> str:
    return f"bbo:{slug}"


class BBOService:
    def __init__(self, gateway: GatewayClient, registry: InstrumentRegistry, sink: EventSink, clock: Clock,
                 health: DataHealth, *, stale_after_s: float, on_snapshot=None) -> None:
        self._gw = gateway
        self._registry = registry
        self._sink = sink
        self._clock = clock
        self._health = health
        self._stale_after = stale_after_s
        self._latest: dict[str, BBOSnapshot] = {}
        self._cursor = 0
        self._on_snapshot = on_snapshot  # e.g. BookService.reconcile_bbo

    def latest(self, slug: str) -> BBOSnapshot | None:
        return self._latest.get(slug)

    def targets(self, now: datetime) -> list[str]:
        return [i.slug for i in self._registry.all() if phase_of(i, now) == Phase.OPEN]

    def _sync_feeds(self, targets: list[str]) -> None:
        wanted = {bbo_feed_name(s) for s in targets}
        for name in list(self._health.feeds):
            if name.startswith("bbo:") and name not in wanted:
                self._health.unregister(name)
                self._latest.pop(name[4:], None)
        for s in targets:
            self._health.register(bbo_feed_name(s), self._stale_after)

    async def poll_next(self) -> BBOSnapshot | None:
        now = self._clock.now()
        targets = self.targets(now)
        self._sync_feeds(targets)
        if not targets:
            return None
        slug = targets[self._cursor % len(targets)]
        self._cursor += 1
        feed = self._health.feeds[bbo_feed_name(slug)]
        try:
            resp = await self._gw.bbo(slug)
            if not resp.ok:
                raise GatewayError(f"bbo HTTP {resp.status}: {resp.data}", resp.status)
            c = resp.cache
            snap = parse_bbo(resp.data, sent_at=resp.sent_at, recv_at=resp.recv_at,
                             data_as_of=c.data_as_of(resp.recv_at) if c else None,
                             cache_status=c.status if c else None, cache_age_s=c.age_s if c else None)
        except (GatewayError, ParseError) as exc:
            feed.error(str(exc))
            log.warning("bbo %s failed: %s", slug, exc)
            return None
        if snap.slug != slug:
            self._sink.quality_event("bbo", "slug_mismatch", {"requested": slug, "got": snap.slug}, snap.recv_at)
            return None
        if snap.crossed:
            self._sink.quality_event("bbo", "crossed_book", {"slug": slug, "bid": str(snap.best_bid),
                                                             "ask": str(snap.best_ask)}, snap.recv_at)
        self._latest[slug] = snap
        # BBO has no quote timestamp and is CDN-cached for up to 30 s: freshness is the data's age (from
        # Last-Modified/Age), not the request round trip, and the feed is marked as of when the data was produced.
        as_of = snap.data_as_of or snap.recv_at
        feed.mark(as_of, snap.last_trade_ts, (snap.recv_at - as_of).total_seconds() * 1000)
        self._sink.bbo(snap)
        if self._on_snapshot is not None:
            self._on_snapshot(snap)
        return snap
