"""Wires the Phase 2a data layer together and runs its loops."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import timedelta

from polyquant.clock import Clock, SystemClock
from polyquant.config import Settings
from polyquant.domain.models import Horizon
from polyquant.interfaces import EventSink, FanoutSink, MemorySink
from polyquant.marketdata.bbo import BBOService
from polyquant.marketdata.discovery import DiscoveryService, InstrumentRefresher, InstrumentRegistry
from polyquant.marketdata.quality import DataHealth
from polyquant.marketdata.reference import ReferenceService
from polyquant.venue.gateway import GatewayClient

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
        self.bbo = BBOService(gateway, self.registry, self.sink, self.clock, self.health,
                              stale_after_s=settings.bbo_stale_after_s)
        self._last_window_seen: dict[Horizon, str | None] = {}

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
        self.health.evaluate(now)

    async def run(self, stop: asyncio.Event) -> None:
        await self.discovery.run_once()
        s = self.settings
        tasks = [
            asyncio.create_task(self._loop("index", s.index_poll_interval_s, self.reference.poll_once, stop)),
            asyncio.create_task(self._loop("bbo", s.bbo_poll_interval_s, self.bbo.poll_next, stop)),
            asyncio.create_task(self._loop("discovery", s.discovery_interval_s, self.discovery_step, stop)),
            asyncio.create_task(self._loop("refresh", s.instrument_refresh_interval_s, self.refresh_step, stop)),
            asyncio.create_task(self._loop("rollover", 1.0, self.rollover_step, stop)),
        ]
        try:
            await stop.wait()
        finally:
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
