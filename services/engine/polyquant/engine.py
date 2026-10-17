"""Wires the data layer (public REST + authenticated markets WebSocket) together and runs its loops."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import timedelta

from polyquant.clock import Clock, SystemClock
from polyquant.config import Settings
from polyquant.domain.models import Horizon, Phase, phase_of
from polyquant.interfaces import EventSink, FanoutSink, MemorySink
from polyquant.marketdata.bbo import BBOService
from polyquant.marketdata.books import BookService
from polyquant.marketdata.discovery import DiscoveryService, InstrumentRefresher, InstrumentRegistry
from polyquant.marketdata.quality import ClockSkewMonitor, DataHealth
from polyquant.marketdata.reference import ReferenceService
from polyquant.spot.kraken import KrakenTradeStream
from polyquant.venue.gateway import GatewayClient
from polyquant.venue.ws_markets import MarketsStream

log = logging.getLogger(__name__)

REFRESH_PER_CYCLE = 4


class Engine:
    def __init__(self, settings: Settings, gateway: GatewayClient, *sinks: EventSink,
                 clock: Clock | None = None) -> None:
        self.settings = settings
        self.clock = clock or SystemClock()
        self.gateway = gateway
        self.alerts = MemorySink(keep=200)  # recent events for the API
        self.sink = FanoutSink(self.alerts, *sinks)
        self.health = DataHealth(self.sink)
        self.registry = InstrumentRegistry(self.sink, self.clock)
        self.reference = ReferenceService(gateway, self.sink, self.clock,
                                          self.health.register("index", settings.index_stale_after_s),
                                          asset=settings.asset)
        self.discovery = DiscoveryService(gateway, self.registry, self.sink, self.clock,
                                          self.health.register("discovery", settings.discovery_stale_after_s),
                                          asset=settings.asset, horizons=settings.horizons,
                                          lookahead_s=settings.discovery_lookahead_s,
                                          lookback_s=settings.discovery_lookback_s)
        self.refresher = InstrumentRefresher(gateway, self.registry, self.sink, self.clock,
                                             self.reference.value_at)
        self.skew = ClockSkewMonitor(self.sink, threshold_ms=settings.clock_skew_alert_ms)
        self.books = BookService(self.sink, self.clock, self.health, stale_after_s=settings.book_stale_after_s,
                                 skew=self.skew)
        self.stream: MarketsStream | None = None
        if settings.ws_enabled and settings.has_credentials:
            self.stream = MarketsStream(settings.polymarket_us_key_id.get_secret_value(),
                                        settings.polymarket_us_secret_key.get_secret_value(),
                                        on_frame=self._on_ws_frame, on_event=self._on_ws_event, clock=self.clock,
                                        idle_timeout_s=settings.ws_idle_timeout_s)
            self._ws_feed = self.health.register("ws", settings.ws_idle_timeout_s)
        self.spot_buffer: dict[int, float] = {}  # unix second -> last trade px (≈2 h, for live strategies)
        self.spot_stream: KrakenTradeStream | None = None
        if settings.spot_enabled:
            self._spot_feed = self.health.register("spot:kraken", settings.spot_stale_after_s)
            self.spot_stream = KrakenTradeStream(self._on_spot_bars,
                                                 lambda k, d: self.sink.quality_event("spot", k, d, self.clock.now()),
                                                 self.clock)
        self.bbo = BBOService(gateway, self.registry, self.sink, self.clock, self.health,
                              stale_after_s=settings.bbo_stale_after_s,
                              on_snapshot=self.books.reconcile_bbo if self.stream else None)
        self._last_window_seen: dict[Horizon, str | None] = {}
        self._extra_loops: list[tuple[str, float, Callable[[], Awaitable[object]]]] = []

    def add_loop(self, name: str, interval_s: float, step: Callable[[], Awaitable[object]]) -> None:
        self._extra_loops.append((name, interval_s, step))

    # ---- market view for the paper engine (polyquant.paper.engine.MarketView) ---------------------------

    def instrument(self, slug: str):
        return self.registry.get(slug)

    def phase(self, slug: str, now):
        inst = self.registry.get(slug)
        return None if inst is None else phase_of(inst, now)

    def book(self, slug: str):
        return self.books.latest(slug)

    def book_stale(self, slug: str) -> bool:
        from polyquant.marketdata.books import book_feed_name

        name = book_feed_name(slug)
        return self.health.is_stale(name) if name in self.health.feeds else True

    def ws_age_ms(self, now) -> float | None:
        if self.stream is None or self.stream.last_frame_at is None or not self.stream.connected:
            return None
        return (now - self.stream.last_frame_at).total_seconds() * 1000

    def index_stale(self) -> bool:
        return self.health.is_stale("index")

    def clock_alert(self) -> bool:
        return self.skew.alerting

    def settlement_flag(self, slug: str):
        return self.registry.settlement_flags.get(slug)

    def _on_spot_bars(self, bars) -> None:
        for b in bars:
            self.spot_buffer[int(b.ts.timestamp())] = float(b.last_px)
            self._spot_feed.mark(b.recv_at, b.ts, (b.recv_at - b.ts).total_seconds() * 1000)
        if len(self.spot_buffer) > 9000:
            for k in sorted(self.spot_buffer)[: len(self.spot_buffer) - 7200]:
                del self.spot_buffer[k]
        self.sink.spot_bars(bars)

    # ---- websocket callbacks -----------------------------------------------------------------------

    def _on_ws_frame(self, frame: dict, recv_at) -> None:
        self._ws_feed.mark(recv_at)
        self.books.on_frame(frame, recv_at)

    def _on_ws_event(self, kind: str, detail: dict) -> None:
        if kind == "error":
            self._ws_feed.error(detail.get("error", ""))
        self.sink.quality_event("ws", kind, detail, self.clock.now())

    def ws_targets(self, now) -> tuple[list[str], list[str]]:
        """(subscribe, open): current and next window per horizon; only OPEN ones are watched for staleness."""
        subscribe, open_ = [], []
        for h in (Horizon(x) for x in self.settings.horizons):
            for inst in (self.registry.current(h, now), self.registry.next(h, now)):
                if inst is None:
                    continue
                subscribe.append(inst.slug)
                if phase_of(inst, now) == Phase.OPEN:
                    open_.append(inst.slug)
        return subscribe, open_

    def sync_subscriptions(self, now) -> None:
        subscribe, open_ = self.ws_targets(now)
        self.books.track(subscribe)
        self.books.watch_open(open_)
        if self.stream is not None:
            self.stream.set_slugs(subscribe)

    # ---- loops -----------------------------------------------------------------------------------

    async def _loop(self, name: str, interval_s: float, step: Callable[[], Awaitable[object]],
                    stop: asyncio.Event) -> None:
        while not stop.is_set():
            started = asyncio.get_running_loop().time()
            try:
                await step()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # a loop must never die silently
                log.exception("%s loop error", name)
                self.sink.quality_event(name, "loop_error", {"error": f"{type(exc).__name__}: {exc}"},
                                        self.clock.now())
            elapsed = asyncio.get_running_loop().time() - started
            try:
                await asyncio.wait_for(stop.wait(), timeout=max(0.0, interval_s - elapsed))
            except TimeoutError:
                pass

    async def discovery_step(self) -> None:
        await self.discovery.run_once()

    async def refresh_step(self) -> None:
        now = self.clock.now()
        for inst in self.refresher.due(now)[:REFRESH_PER_CYCLE]:
            await self.refresher.refresh(inst)
        self.registry.prune(now - timedelta(hours=6))

    async def rollover_step(self) -> None:
        """Detects window boundaries; triggers discovery when the next window is not yet known."""
        now = self.clock.now()
        for h in (Horizon(x) for x in self.settings.horizons):
            cur = self.registry.current(h, now)
            slug = cur.slug if cur else None
            if self._last_window_seen.get(h, "?") != slug:
                self._last_window_seen[h] = slug
                self.sink.quality_event("rollover", "window_changed", {"horizon": h.value, "current": slug}, now)
                if cur is None or self.registry.next(h, now) is None:
                    await self.discovery.run_once()
        self.sync_subscriptions(now)
        self.health.evaluate(now)
        self.skew.evaluate(now)

    async def run(self, stop: asyncio.Event) -> None:
        await self.discovery.run_once()
        s = self.settings
        self.sync_subscriptions(self.clock.now())
        bbo_interval = s.bbo_reconcile_interval_s if self.stream else s.bbo_poll_interval_s
        tasks = [
            asyncio.create_task(self._loop("index", s.index_poll_interval_s, self.reference.poll_once, stop)),
            asyncio.create_task(self._loop("bbo", bbo_interval, self.bbo.poll_next, stop)),
            asyncio.create_task(self._loop("discovery", s.discovery_interval_s, self.discovery_step, stop)),
            asyncio.create_task(self._loop("refresh", s.instrument_refresh_interval_s, self.refresh_step, stop)),
            asyncio.create_task(self._loop("rollover", 1.0, self.rollover_step, stop)),
        ]
        if self.stream is not None:
            tasks.append(asyncio.create_task(self.stream.run(stop)))
        if self.spot_stream is not None:
            tasks.append(asyncio.create_task(self.spot_stream.run(stop)))
        for name, interval, step in self._extra_loops:
            tasks.append(asyncio.create_task(self._loop(name, interval, step, stop)))
        try:
            await stop.wait()
        finally:
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
