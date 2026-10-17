"""Authenticated, read-only Polymarket US markets WebSocket (market data only).

Why not the SDK's MarketsWebSocket: it has no reconnect and relies on the system CA store, which this Mac's
python.org build lacks (CERTIFICATE_VERIFY_FAILED). The SDK is still used for request signing only
(polymarket_us.auth.create_auth_headers). Only MARKET_DATA subscribe/unsubscribe messages can be sent; order and
private channels are refused before anything reaches the socket.

Observed venue behaviour (2026-10-17): every MARKET_DATA frame is a complete book, sent only on change; no sequence
numbers; transactTime increases per market. Frames are therefore applied by replacement with an ordering guard.
"""

import asyncio
import json
import random
import ssl
from decimal import Decimal

import certifi
import websockets

WS_URL = 'wss://api.polymarket.us/v1/ws/markets'
WS_PATH = '/v1/ws/markets'
ALLOWED_SUBSCRIPTIONS = frozenset({'SUBSCRIPTION_TYPE_MARKET_DATA'})


class ForbiddenStreamMessage(RuntimeError):
    pass


def tls_context():
    return ssl.create_default_context(cafile=certifi.where())


class MarketStream:
    """One connection, desired slug set, reconnect with jittered back-off and an idle watchdog.

    on_frame(frame_dict, received_at) runs on the event loop for every decoded frame; on_status(status, detail)
    reports CONNECTED / DISCONNECTED / SUBSCRIBED / IDLE_RECONNECT / ERROR.
    """

    def __init__(self, key_id, secret_key, on_frame, on_status, clock, *, idle_timeout=30.0,
                 connect=websockets.connect, url=WS_URL):
        self.key_id = key_id
        self.secret_key = secret_key
        self.on_frame = on_frame
        self.on_status = on_status
        self.clock = clock
        self.idle_timeout = idle_timeout
        self.connect = connect
        self.url = url
        self.desired = ()
        self.active = ()
        self.generation = 0
        self.ws = None
        self.resubscribe = asyncio.Event()
        self.connected = False
        self.last_frame_at = None
        self.frames = 0
        self.connects = 0

    def set_slugs(self, slugs):
        wanted = tuple(sorted(set(slugs)))[:100]
        if wanted != self.desired:
            self.desired = wanted
            self.resubscribe.set()

    async def send(self, message):
        if 'subscribe' in message:
            if message['subscribe'].get('subscriptionType') not in ALLOWED_SUBSCRIPTIONS:
                raise ForbiddenStreamMessage('Only market-data subscriptions are permitted')
        elif 'unsubscribe' not in message:
            raise ForbiddenStreamMessage('Only subscribe/unsubscribe messages are permitted')
        await self.ws.send(json.dumps(message))

    async def apply_subscriptions(self):
        self.resubscribe.clear()
        if self.active:
            await self.send({'unsubscribe': {'requestId': f'pq-books-{self.generation}'}})
        self.generation += 1
        self.active = self.desired
        if self.active:
            await self.send({'subscribe': {'requestId': f'pq-books-{self.generation}',
                                           'subscriptionType': 'SUBSCRIPTION_TYPE_MARKET_DATA',
                                           'marketSlugs': list(self.active)}})
        self.on_status('SUBSCRIBED', {'slugs': list(self.active)})

    async def run(self, running):
        from polymarket_us.auth import create_auth_headers
        backoff = 1.0
        while running():
            try:
                headers = create_auth_headers(self.key_id, self.secret_key, 'GET', WS_PATH)
                async with self.connect(self.url, additional_headers=headers, ssl=tls_context(), ping_interval=20,
                                        ping_timeout=20, open_timeout=15, max_size=8 * 1024 * 1024) as ws:
                    self.ws = ws
                    self.connected = True
                    self.connects += 1
                    self.active = ()
                    self.on_status('CONNECTED', {'connects': self.connects})
                    backoff = 1.0
                    await self.apply_subscriptions()
                    await self.read(ws, running)
            except asyncio.CancelledError:
                raise
            except Exception as error:  # network, auth, protocol: always reconnect
                self.on_status('ERROR', {'error': type(error).__name__})
            finally:
                if self.connected:
                    self.on_status('DISCONNECTED', {})
                self.connected = False
                self.ws = None
                self.active = ()
            if not running():
                break
            await asyncio.sleep(backoff + random.uniform(0, backoff / 2))  # noqa: S311 - jitter
            backoff = min(backoff * 2, 30.0)

    async def read(self, ws, running):
        # Exactly one recv() may be pending at a time: a subscription change must not start a second one
        # (concurrent recv fails inside websockets and drops the connection with 1011).
        receive = None
        resub = None
        try:
            while running():
                if self.resubscribe.is_set():
                    await self.apply_subscriptions()
                if receive is None:
                    receive = asyncio.ensure_future(ws.recv())
                resub = asyncio.ensure_future(self.resubscribe.wait())
                done, _ = await asyncio.wait({receive, resub}, timeout=self.idle_timeout,
                                             return_when=asyncio.FIRST_COMPLETED)
                if resub not in done:
                    resub.cancel()
                if receive not in done:
                    if resub in done:
                        continue  # keep the same pending recv
                    if self.active:
                        # Subscribed but silent: never trust a possibly dead connection.
                        self.on_status('IDLE_RECONNECT', {'idle_seconds': self.idle_timeout})
                        return
                    continue
                raw = receive.result()
                receive = None
                received_at = self.clock()
                if isinstance(raw, bytes):
                    raw = raw.decode('utf-8')
                try:
                    frame = json.loads(raw, parse_float=Decimal)
                except ValueError:
                    self.on_status('BAD_FRAME', {})
                    continue
                self.frames += 1
                self.last_frame_at = received_at
                self.on_frame(frame, received_at)
        finally:
            for future in (receive, resub):
                if future is None:
                    continue
                future.cancel()
                if future.done() and not future.cancelled():
                    future.exception()
