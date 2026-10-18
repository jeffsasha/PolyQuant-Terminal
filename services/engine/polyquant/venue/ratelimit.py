"""A single process-wide request budget for the public gateway, with a priority lane."""

from __future__ import annotations

import asyncio
import time
from enum import IntEnum


class Priority(IntEnum):
    HIGH = 0  # official reference index
    NORMAL = 1  # BBO, instrument refresh
    LOW = 2  # discovery


class RateLimiter:
    """Evenly spaced requests at `rate` per second; higher-priority callers go first.

    A caller that has waited `max_wait_s` is promoted to HIGH (aging), so a saturated budget can delay
    low-priority work (discovery) but never starve it. Found in a live run: without aging, index + BBO polling
    consumed every slot and discovery never ran again.

    After a 429 the whole budget is paused (`penalize`), because the venue's limit is per IP.
    """

    def __init__(self, rate: float, monotonic=time.monotonic, sleep=asyncio.sleep, max_wait_s: float = 3.0) -> None:
        if rate <= 0:
            raise ValueError("rate must be positive")
        self._interval = 1.0 / rate
        self._monotonic = monotonic
        self._sleep = sleep
        self._max_wait = max_wait_s
        self._next_at = 0.0
        self._lock = asyncio.Lock()
        self._waiting = {p: 0 for p in Priority}
        self.promotions = 0

    def penalize(self, seconds: float) -> None:
        self._next_at = max(self._next_at, self._monotonic() + seconds)

    def _higher_waiting(self, priority: Priority) -> bool:
        return any(self._waiting[p] for p in Priority if p < priority)

    async def acquire(self, priority: Priority = Priority.NORMAL) -> None:
        eff = priority
        started = self._monotonic()
        self._waiting[eff] += 1
        try:
            while True:
                if eff is not Priority.HIGH and self._monotonic() - started >= self._max_wait:
                    self._waiting[eff] -= 1
                    eff = Priority.HIGH
                    self._waiting[eff] += 1
                    self.promotions += 1
                if self._higher_waiting(eff):
                    await self._sleep(self._interval / 4)
                    continue
                async with self._lock:
                    now = self._monotonic()
                    wait = self._next_at - now
                    if wait <= 0 and not self._higher_waiting(eff):
                        self._next_at = now + self._interval
                        return
                await self._sleep(min(max(wait, 0.0), self._interval) or self._interval / 4)
        finally:
            self._waiting[eff] -= 1
