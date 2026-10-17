"""Thin, read-only client for the public Polymarket US gateway.

Why not the SDK for public data: we need exact send/receive timestamps per request, one rate budget shared by
all pollers, and explicit handling of Cloudflare HTML 429s (docs/RESEARCH_AUDIT.md §1.4, §2).

Safety: GET only, allow-listed hosts only. Any other request raises before a socket is opened.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any
from urllib.parse import urlsplit

import httpx

from polyquant.clock import Clock, SystemClock
from polyquant.config import GATEWAY_BASE_URL
from polyquant.venue.ratelimit import Priority, RateLimiter

log = logging.getLogger(__name__)

ALLOWED_HOSTS = frozenset({"gateway.polymarket.us"})
ALLOWED_METHODS = frozenset({"GET"})
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class ForbiddenRequest(RuntimeError):
    """A request this read-only client must never send."""


class GatewayError(RuntimeError):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True, slots=True)
class GatewayResponse:
    status: int
    data: Any
    sent_at: datetime
    recv_at: datetime

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    @property
    def rtt_ms(self) -> float:
        return (self.recv_at - self.sent_at).total_seconds() * 1000


@dataclass
class GatewayStats:
    requests: int = 0
    ok: int = 0
    rate_limited: int = 0
    errors: int = 0
    retries: int = 0
    last_error: str | None = None
    last_rate_limited_at: datetime | None = None
    rtt_ms: list[float] = field(default_factory=list)

    def record_rtt(self, ms: float, keep: int = 500) -> None:
        self.rtt_ms.append(ms)
        if len(self.rtt_ms) > keep:
            del self.rtt_ms[: len(self.rtt_ms) - keep]


class GatewayClient:
    def __init__(
        self,
        *,
        base_url: str = GATEWAY_BASE_URL,
        max_rps: float = 2.0,
        timeout_s: float = 10.0,
        max_attempts: int = 4,
        clock: Clock | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        limiter: RateLimiter | None = None,
        sleep=asyncio.sleep,
    ) -> None:
        host = urlsplit(base_url).hostname
        if host not in ALLOWED_HOSTS:
            raise ForbiddenRequest(f"host {host!r} is not allow-listed")
        self._clock = clock or SystemClock()
        self._limiter = limiter or RateLimiter(max_rps)
        self._max_attempts = max_attempts
        self._sleep = sleep
        self._http = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout_s,
            transport=transport,
            headers={"Accept": "application/json", "User-Agent": "polyquant/0.1 (paper-research)"},
            follow_redirects=False,
        )
        self.stats = GatewayStats()

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> GatewayClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    def _guard(self, method: str, url: httpx.URL) -> None:
        if method.upper() not in ALLOWED_METHODS:
            raise ForbiddenRequest(f"{method} is not permitted by the read-only gateway client")
        if url.host not in ALLOWED_HOSTS:
            raise ForbiddenRequest(f"host {url.host!r} is not allow-listed")

    async def request(self, method: str, path: str, *, params: dict | None = None,
                      priority: Priority = Priority.NORMAL) -> GatewayResponse:
        request = self._http.build_request(method, path, params=params)
        self._guard(request.method, request.url)

        backoff = 1.0
        for attempt in range(1, self._max_attempts + 1):
            await self._limiter.acquire(priority)
            sent_at = self._clock.now()
            self.stats.requests += 1
            try:
                resp = await self._http.send(request)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                recv_at = self._clock.now()
                self.stats.errors += 1
                self.stats.last_error = f"{type(exc).__name__}: {exc}"
                if attempt == self._max_attempts:
                    raise GatewayError(f"GET {path} failed: {self.stats.last_error}") from exc
                await self._retry_sleep(backoff)
                backoff *= 2
                continue
            recv_at = self._clock.now()
            self.stats.record_rtt((recv_at - sent_at).total_seconds() * 1000)

            if resp.status_code == 429:
                # Body may be Cloudflare HTML, not the documented JSON. Pause the whole budget (limit is per IP).
                self.stats.rate_limited += 1
                self.stats.last_rate_limited_at = recv_at
                pause = max(1.0, backoff)
                self._limiter.penalize(pause)
                log.warning("gateway 429 on %s; pausing %.1fs (attempt %d)", path, pause, attempt)
            elif resp.status_code in RETRYABLE_STATUS:
                self.stats.errors += 1
                self.stats.last_error = f"HTTP {resp.status_code}"
            else:
                data = self._decode(resp, path)
                if 200 <= resp.status_code < 300:
                    self.stats.ok += 1
                return GatewayResponse(resp.status_code, data, sent_at, recv_at)

            if attempt == self._max_attempts:
                raise GatewayError(f"GET {path} gave HTTP {resp.status_code} after {attempt} attempts",
                                   status=resp.status_code)
            self.stats.retries += 1
            await self._retry_sleep(backoff)
            backoff *= 2
        raise AssertionError("unreachable")

    async def get(self, path: str, *, params: dict | None = None,
                  priority: Priority = Priority.NORMAL) -> GatewayResponse:
        return await self.request("GET", path, params=params, priority=priority)

    async def _retry_sleep(self, base: float) -> None:
        await self._sleep(base + random.uniform(0, base / 2))  # noqa: S311 - jitter, not crypto

    def _decode(self, resp: httpx.Response, path: str) -> Any:
        try:
            # parse_float keeps every JSON number exact; money must never pass through float.
            return json.loads(resp.content, parse_float=Decimal)
        except ValueError as exc:
            self.stats.errors += 1
            self.stats.last_error = f"non-JSON response ({resp.status_code}) for {path}"
            raise GatewayError(self.stats.last_error, status=resp.status_code) from exc

    # ---- typed endpoint helpers -------------------------------------------------------------------

    async def market_by_slug(self, slug: str) -> GatewayResponse:
        return await self.get(f"/v1/market/slug/{slug}")

    async def bbo(self, slug: str) -> GatewayResponse:
        return await self.get(f"/v1/markets/{slug}/bbo")

    async def settlement(self, slug: str) -> GatewayResponse:
        return await self.get(f"/v1/markets/{slug}/settlement")

    async def events(self, *, closed: bool, end_min: str, end_max: str, limit: int = 100,
                     offset: int = 0) -> GatewayResponse:
        params = {"categories": "crypto", "closed": str(closed).lower(), "endDateMin": end_min,
                  "endDateMax": end_max, "limit": limit, "offset": offset}
        return await self.get("/v1/events", params=params, priority=Priority.LOW)

    async def index_history(self, asset: str, start_unix: int, end_unix: int,
                            bucket: str = "ASSET_PRICE_BUCKET_1S") -> GatewayResponse:
        params = {"assets": f"crypto:{asset}", "bucket": bucket, "from": start_unix, "to": end_unix}
        return await self.get("/v1/asset-prices/history", params=params, priority=Priority.HIGH)
