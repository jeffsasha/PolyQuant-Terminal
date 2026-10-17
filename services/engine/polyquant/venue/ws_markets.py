"""Authenticated, read-only markets WebSocket with reconnect, resubscribe and an idle watchdog.

Uses the official SDK only for request signing (`polymarket_us.auth.create_auth_headers`). The SDK's own socket
class has no reconnect and relies on the system CA store (absent on python.org builds), so the connection is
managed here. Only market-data subscription messages are ever sent.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import ssl
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal

import certifi
import websockets
from polymarket_us.auth import create_auth_headers

from polyquant.clock import Clock, SystemClock
from polyquant.config import API_BASE_URL

log = logging.getLogger(__name__)

WS_PATH = "/v1/ws/markets"
ALLOWED_SUBSCRIPTIONS = frozenset({"SUBSCRIPTION_TYPE_MARKET_DATA", "SUBSCRIPTION_TYPE_TRADE"})
MAX_SLUGS_PER_SUBSCRIPTION = 100  # documented limit


class ForbiddenMessage(RuntimeError):
    pass


def tls_context() -> ssl.SSLContext:
    return ssl.create_default_context(cafile=certifi.where())


class MarketsStream:
    """Maintains one connection and the desired set of market-data subscriptions.

    Callbacks receive (frame_dict, recv_at). Connection-level events go to `on_event(kind, detail)`.
    """

    def __init__(self, key_id: str, secret_key: str, *, on_frame: Callable[[dict, datetime], None],
                 on_event: Callable[[str, dict], None], clock: Clock | None = None,
                 idle_timeout_s: float = 30.0, initial_backoff_s: float = 1.0, max_backoff_s: float = 30.0,
                 connect=websockets.connect, base_url: str = API_BASE_URL) -> None:
        self._key_id = key_id
        self._secret = secret_key
        self._on_frame = on_frame
        self._on_event = on_event
        self._clock = clock or SystemClock()
        self._idle_timeout = idle_timeout_s
        self._initial_backoff = initial_backoff_s
        self._max_backoff = max_backoff_s
        self._connect = connect
        self._url = base_url.replace("https://", "wss://") + WS_PATH
        self._desired: tuple[str, ...] = ()
        self._active: tuple[str, ...] = ()
        self._generation = 0
        self._ws = None
        self._resubscribe = asyncio.Event()
        self.connected = False
        self.connects = 0
        self.disconnects = 0
        self.frames = 0
        self.last_frame_at: datetime | None = None

    # ---- subscriptions -----------------------------------------------------------------------------

    def set_slugs(self, slugs: list[str]) -> None:
        want = tuple(sorted(set(slugs)))[:MAX_SLUGS_PER_SUBSCRIPTION]
        if want != self._desired:
            self._desired = want
            self._resubscribe.set()

    @property
    def subscribed(self) -> tuple[str, ...]:
        return self._active

    async def _send(self, msg: dict) -> None:
        if "subscribe" in msg:
            if msg["subscribe"].get("subscriptionType") not in ALLOWED_SUBSCRIPTIONS:
                raise ForbiddenMessage(f"subscription {msg['subscribe'].get('subscriptionType')!r} not allowed")
        elif "unsubscribe" not in msg:
            raise ForbiddenMessage("only subscribe/unsubscribe messages may be sent")
        await self._ws.send(json.dumps(msg))

    async def _apply_subscriptions(self) -> None:
        self._resubscribe.clear()
        if self._active:
            for kind in ("md", "tr"):
                await self._send({"unsubscribe": {"requestId": f"{kind}-{self._generation}"}})
        self._generation += 1
        self._active = self._desired
        if self._active:
            for kind, sub in (("md", "SUBSCRIPTION_TYPE_MARKET_DATA"), ("tr", "SUBSCRIPTION_TYPE_TRADE")):
                await self._send({"subscribe": {"requestId": f"{kind}-{self._generation}",
                                                "subscriptionType": sub, "marketSlugs": list(self._active)}})
        self._on_event("subscribed", {"slugs": list(self._active), "generation": self._generation})

    # ---- connection loop ---------------------------------------------------------------------------

    async def run(self, stop: asyncio.Event) -> None:
        backoff = self._initial_backoff
        while not stop.is_set():
            try:
                headers = create_auth_headers(self._key_id, self._secret, "GET", WS_PATH)
                async with self._connect(self._url, additional_headers=headers, ssl=tls_context(),
                                         ping_interval=20, ping_timeout=20, open_timeout=15,
                                         max_size=8 * 1024 * 1024) as ws:
                    self._ws = ws
                    self.connected = True
                    self.connects += 1
                    self._active = ()
                    self._on_event("connected", {"connects": self.connects})
                    backoff = self._initial_backoff
                    await self._apply_subscriptions()
                    await self._read(ws, stop)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # network, auth, protocol: always reconnect with back-off
                self._on_event("error", {"error": f"{type(exc).__name__}: {exc}"})
            finally:
                if self.connected:
                    self.disconnects += 1
                    self._on_event("disconnected", {"disconnects": self.disconnects})
                self.connected = False
                self._ws = None
                self._active = ()
            if stop.is_set():
                break
            delay = backoff + random.uniform(0, backoff / 2)  # noqa: S311 - jitter
            try:
                await asyncio.wait_for(stop.wait(), timeout=delay)
            except TimeoutError:
                pass
            backoff = min(backoff * 2, self._max_backoff)

    async def _read(self, ws, stop: asyncio.Event) -> None:
        # Exactly one recv() may be pending: a resubscribe must not start a second one (concurrent recv fails inside
        # websockets and drops the connection with 1011 — found live).
        stop_task = asyncio.ensure_future(stop.wait())
        recv = None
        resub = None
        try:
            while not stop.is_set():
                if self._resubscribe.is_set():
                    await self._apply_subscriptions()
                if recv is None:
                    recv = asyncio.ensure_future(ws.recv())
                resub = asyncio.ensure_future(self._resubscribe.wait())
                done, _ = await asyncio.wait({recv, resub, stop_task}, timeout=self._idle_timeout,
                                             return_when=asyncio.FIRST_COMPLETED)
                if resub not in done:
                    resub.cancel()
                if recv not in done:
                    if stop_task in done:
                        return
                    if resub in done:
                        continue  # keep the same pending recv
                    if self._active:
                        self._on_event("idle_reconnect", {"idle_s": self._idle_timeout})
                        return
                    continue
                raw = recv.result()  # raises ConnectionClosed → reconnect path in run()
                recv = None
                recv_at = self._clock.now()
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")
                try:
                    frame = json.loads(raw, parse_float=Decimal)  # money never passes through float
                except ValueError:
                    self._on_event("bad_frame", {"sample": raw[:200]})
                    continue
                self.frames += 1
                self.last_frame_at = recv_at
                self._on_frame(frame, recv_at)
        finally:
            for f in (recv, resub, stop_task):
                if f is None:
                    continue
                f.cancel()
                if f.done() and not f.cancelled():
                    f.exception()  # retrieve, so a close during shutdown is never logged as unhandled
