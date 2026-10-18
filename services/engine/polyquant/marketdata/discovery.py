"""Discovery and rollover of BTC Up/Down instruments, plus refresh of their official reference fields."""

from __future__ import annotations

import logging
from dataclasses import fields
from datetime import datetime, timedelta

from polyquant.clock import Clock
from polyquant.domain.models import Horizon, Instrument, Phase, phase_of
from polyquant.domain.settlement import check_references, outcome_from_settlement_flag
from polyquant.interfaces import EventSink
from polyquant.marketdata.quality import FeedHealth
from polyquant.venue.gateway import GatewayClient, GatewayError
from polyquant.venue.parsing import ParseError, is_target_market, iter_event_markets, parse_instrument

log = logging.getLogger(__name__)

TRACKED_FIELDS = ("status", "price_to_beat", "settlement_price", "window_start", "window_end", "fee_coefficient")
MAX_PAGES = 20


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class InstrumentRegistry:
    """Current view of every tracked instrument, keyed by slug."""

    def __init__(self, sink: EventSink, clock: Clock) -> None:
        self._sink = sink
        self._clock = clock
        self._by_slug: dict[str, Instrument] = {}
        self.settlement_flags: dict[str, int] = {}

    def upsert(self, inst: Instrument) -> dict:
        now = self._clock.now()
        old = self._by_slug.get(inst.slug)
        if old is None:
            changes = {f: (None, getattr(inst, f)) for f in TRACKED_FIELDS}
            changes["_new"] = True
        else:
            # Never let a later response erase an official value we already saw.
            if old.price_to_beat is not None and inst.price_to_beat is None:
                inst = _replace(inst, price_to_beat=old.price_to_beat)
            if old.settlement_price is not None and inst.settlement_price is None:
                inst = _replace(inst, settlement_price=old.settlement_price)
            changes = {f: (getattr(old, f), getattr(inst, f)) for f in TRACKED_FIELDS
                       if getattr(old, f) != getattr(inst, f)}
            if old.price_to_beat is not None and inst.price_to_beat != old.price_to_beat:
                self._sink.quality_event("discovery", "price_to_beat_changed",
                                         {"slug": inst.slug, "old": str(old.price_to_beat),
                                          "new": str(inst.price_to_beat)}, now)
        self._by_slug[inst.slug] = inst
        if changes:
            self._sink.instrument_changed(inst, changes, now)
        return changes

    def get(self, slug: str) -> Instrument | None:
        return self._by_slug.get(slug)

    def all(self) -> list[Instrument]:
        return sorted(self._by_slug.values(), key=lambda i: (i.window_start, i.horizon))

    def by_phase(self, *phases: Phase, now: datetime | None = None) -> list[Instrument]:
        now = now or self._clock.now()
        return [i for i in self.all() if phase_of(i, now) in phases]

    def current(self, horizon: Horizon, now: datetime | None = None) -> Instrument | None:
        """The instrument whose window contains `now` (half-open [start, end))."""
        now = now or self._clock.now()
        hits = [i for i in self._by_slug.values()
                if i.horizon == horizon and i.window_start <= now < i.window_end]
        if len(hits) > 1:
            self._sink.quality_event("discovery", "overlapping_windows",
                                     {"horizon": horizon.value, "slugs": [i.slug for i in hits]}, now)
            return None  # ambiguous: never pick one silently
        return hits[0] if hits else None

    def next(self, horizon: Horizon, now: datetime | None = None) -> Instrument | None:
        now = now or self._clock.now()
        upcoming = [i for i in self._by_slug.values() if i.horizon == horizon and i.window_start > now]
        return min(upcoming, key=lambda i: i.window_start) if upcoming else None

    def prune(self, older_than: datetime) -> int:
        """Drop settled instruments whose window ended before `older_than` (they stay in the database)."""
        drop = [s for s, i in self._by_slug.items()
                if i.settlement_price is not None and i.window_end < older_than]
        for s in drop:
            del self._by_slug[s]
            self.settlement_flags.pop(s, None)
        return len(drop)


def _replace(inst: Instrument, **kw) -> Instrument:
    data = {f.name: getattr(inst, f.name) for f in fields(inst)}
    data.update(kw)
    return Instrument(**data)


class DiscoveryService:
    """Finds target instruments by metadata (never by hard-coded slug).

    Upcoming windows are listed with closed=true (RESEARCH_AUDIT §1.1), so both closed=false and closed=true
    are queried over [now - lookback, now + lookahead] on the event end date.
    """

    def __init__(self, gateway: GatewayClient, registry: InstrumentRegistry, sink: EventSink, clock: Clock,
                 health: FeedHealth, *, asset: str, horizons: tuple[str, ...], lookahead_s: int,
                 lookback_s: int) -> None:
        self._gw = gateway
        self._registry = registry
        self._sink = sink
        self._clock = clock
        self._health = health
        self._asset = asset
        self._horizons = horizons
        self._lookahead = timedelta(seconds=lookahead_s)
        self._lookback = timedelta(seconds=lookback_s)

    async def run_once(self) -> int:
        now = self._clock.now()
        end_min, end_max = _iso(now - self._lookback), _iso(now + self._lookahead)
        seen = 0
        rejected = 0
        try:
            for closed in (False, True):
                offset = 0
                for _ in range(MAX_PAGES):
                    resp = await self._gw.events(closed=closed, end_min=end_min, end_max=end_max, offset=offset)
                    if not resp.ok:
                        raise GatewayError(f"events HTTP {resp.status}", resp.status)
                    events = resp.data.get("events") or []
                    for event_slug, market in iter_event_markets(resp.data):
                        if not is_target_market(market, self._asset, self._horizons):
                            continue
                        try:
                            self._registry.upsert(parse_instrument(market, event_slug=event_slug))
                            seen += 1
                        except ParseError as exc:
                            rejected += 1
                            self._sink.quality_event("discovery", "parse_rejected",
                                                     {"slug": market.get("slug"), "error": str(exc)}, now)
                    if len(events) < 100:
                        break
                    offset += len(events)
        except GatewayError as exc:
            self._health.error(str(exc))
            log.warning("discovery failed: %s", exc)
            return 0
        self._health.mark(self._clock.now())
        log.info("discovery: %d target instruments seen, %d rejected", seen, rejected)
        return seen


class InstrumentRefresher:
    """Polls single instruments that are waiting on an official value: priceToBeat after open, and
    settlementPrice + settlement flag after close. Cross-checks both against the recorded index series."""

    def __init__(self, gateway: GatewayClient, registry: InstrumentRegistry, sink: EventSink, clock: Clock,
                 index_lookup) -> None:
        self._gw = gateway
        self._registry = registry
        self._sink = sink
        self._clock = clock
        self._index_lookup = index_lookup  # callable(ts) -> Decimal | None
        self._checked: set[tuple[str, str]] = set()

    def due(self, now: datetime) -> list[Instrument]:
        out = []
        for inst in self._registry.all():
            ph = phase_of(inst, now)
            if (
                (ph == Phase.OPEN and inst.price_to_beat is None)
                # listing still says CLOSED although the window has (nearly) started
                or (ph == Phase.UPCOMING and now >= inst.window_start - timedelta(seconds=1))
                or ph in (Phase.AWAITING_SETTLEMENT, Phase.UNKNOWN)
                or (inst.settlement_price is not None and inst.slug not in self._registry.settlement_flags)
            ):
                out.append(inst)
        return out

    async def refresh(self, inst: Instrument) -> Instrument | None:
        try:
            resp = await self._gw.market_by_slug(inst.slug)
            if not resp.ok:
                return None
            fresh = parse_instrument(resp.data, event_slug=inst.event_slug)
        except (GatewayError, ParseError) as exc:
            self._sink.quality_event("refresh", "refresh_failed", {"slug": inst.slug, "error": str(exc)},
                                     self._clock.now())
            return None
        self._registry.upsert(fresh)
        fresh = self._registry.get(inst.slug) or fresh
        if fresh.settlement_price is not None and fresh.slug not in self._registry.settlement_flags:
            await self._fetch_flag(fresh)
        self._cross_check(fresh)
        return fresh

    async def _fetch_flag(self, inst: Instrument) -> None:
        try:
            resp = await self._gw.settlement(inst.slug)
        except GatewayError:
            return
        if not resp.ok or "settlement" not in resp.data:
            return
        flag = int(resp.data["settlement"])
        self._registry.settlement_flags[inst.slug] = flag
        now = self._clock.now()
        expected = inst.settled_outcome()
        actual = outcome_from_settlement_flag(flag)
        self._sink.instrument_changed(inst, {"settlement_flag": (None, flag), "outcome": (None, actual.value)}, now)
        if expected is not None and expected != actual:
            self._sink.quality_event("settlement", "outcome_rule_mismatch",
                                     {"slug": inst.slug, "rule": expected.value, "venue": actual.value,
                                      "price_to_beat": str(inst.price_to_beat),
                                      "settlement_price": str(inst.settlement_price)}, now)

    def _cross_check(self, inst: Instrument) -> None:
        now = self._clock.now()
        for chk in check_references(inst, _LookupMapping(self._index_lookup)):
            key = (inst.slug, chk.kind)
            if key in self._checked or not chk.comparable:
                continue
            self._checked.add(key)
            if not chk.matches:
                self._sink.quality_event("reference", "reference_rule_mismatch",
                                         {"slug": inst.slug, "kind": chk.kind, "official": str(chk.official),
                                          "derived": str(chk.derived)}, now)
            else:
                log.debug("reference %s %s verified: %s", inst.slug, chk.kind, chk.official)


class _LookupMapping:
    """Adapts a ts -> value callable to the Mapping.get interface used by check_references."""

    def __init__(self, fn) -> None:
        self._fn = fn

    def get(self, key, default=None):
        v = self._fn(key)
        return default if v is None else v

