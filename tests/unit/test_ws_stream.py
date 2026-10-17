from __future__ import annotations

import asyncio
import base64
import json
from decimal import Decimal

import pytest
import websockets
from nacl.signing import SigningKey

from polyquant.venue.ws_markets import WS_PATH, ForbiddenMessage, MarketsStream


class FakeWS:
    def __init__(self) -> None:
        self.incoming: asyncio.Queue = asyncio.Queue()
        self.sent: list[dict] = []

    async def send(self, raw: str) -> None:
        self.sent.append(json.loads(raw))

    async def recv(self):
        item = await self.incoming.get()
        if isinstance(item, Exception):
            raise item
        return item

    def drop(self) -> None:
        self.incoming.put_nowait(websockets.ConnectionClosedError(None, None))


class FakeConnect:
    """Stands in for websockets.connect: each call yields a new FakeWS and records the call."""

    def __init__(self, fail_first: int = 0) -> None:
        self.calls: list[dict] = []
        self.sockets: list[FakeWS] = []
        self.fail_first = fail_first
        self.ready = asyncio.Event()

    def __call__(self, url, **kw):
        self.calls.append({"url": url, **kw})
        parent = self

        class _CM:
            async def __aenter__(self_inner):
                if len(parent.calls) <= parent.fail_first:
                    raise websockets.InvalidStatus(type("R", (), {"status_code": 401, "headers": {}})())
                ws = FakeWS()
                parent.sockets.append(ws)
                parent.ready.set()
                return ws

            async def __aexit__(self_inner, *exc):
                return False

        return _CM()


SECRET = SigningKey.generate()
SECRET_B64 = base64.b64encode(bytes(SECRET)).decode()
KEY_ID = "00000000-0000-4000-8000-000000000000"


def make(fake: FakeConnect, **kw):
    frames, events = [], []
    stream = MarketsStream(KEY_ID, SECRET_B64, on_frame=lambda f, r: frames.append(f),
                           on_event=lambda k, d: events.append((k, d)), connect=fake, initial_backoff_s=0.01,
                           max_backoff_s=0.02, **kw)
    return stream, frames, events


async def until(cond, timeout=2.0):
    async def _w():
        while not cond():
            await asyncio.sleep(0.005)
    await asyncio.wait_for(_w(), timeout)


async def test_connects_with_valid_signature_and_subscribes_market_data_only():
    fake = FakeConnect()
    stream, frames, events = make(fake)
    stream.set_slugs(["b-slug", "a-slug"])
    stop = asyncio.Event()
    task = asyncio.create_task(stream.run(stop))
    await until(lambda: fake.sockets and len(fake.sockets[0].sent) == 2)
    call = fake.calls[0]
    assert call["url"] == "wss://api.polymarket.us" + WS_PATH
    h = call["additional_headers"]
    assert h["X-PM-Access-Key"] == KEY_ID
    # signature is Ed25519 over "<ts>GET/v1/ws/markets" with our key
    SECRET.verify_key.verify(f"{h['X-PM-Timestamp']}GET{WS_PATH}".encode(), base64.b64decode(h["X-PM-Signature"]))
    assert call["ssl"] is not None
    subs = fake.sockets[0].sent
    assert {m["subscribe"]["subscriptionType"] for m in subs} == {"SUBSCRIPTION_TYPE_MARKET_DATA",
                                                                  "SUBSCRIPTION_TYPE_TRADE"}
    assert all(m["subscribe"]["marketSlugs"] == ["a-slug", "b-slug"] for m in subs)
    fake.sockets[0].incoming.put_nowait('{"marketData":{"marketSlug":"a-slug","x":0.5}}')
    await until(lambda: frames)
    assert frames[0]["marketData"]["x"] == Decimal("0.5")
    stop.set()
    await task


async def test_resubscribe_on_slug_change():
    fake = FakeConnect()
    stream, _, _ = make(fake)
    stream.set_slugs(["a"])
    stop = asyncio.Event()
    task = asyncio.create_task(stream.run(stop))
    await until(lambda: fake.sockets and len(fake.sockets[0].sent) == 2)
    stream.set_slugs(["a", "c"])
    await until(lambda: len(fake.sockets[0].sent) == 6)
    sent = fake.sockets[0].sent
    assert sent[2] == {"unsubscribe": {"requestId": "md-1"}} and sent[3] == {"unsubscribe": {"requestId": "tr-1"}}
    assert sent[4]["subscribe"]["requestId"] == "md-2" and sent[4]["subscribe"]["marketSlugs"] == ["a", "c"]
    stop.set()
    await task


async def test_reconnects_and_resubscribes_after_drop():
    fake = FakeConnect()
    stream, _, events = make(fake)
    stream.set_slugs(["a"])
    stop = asyncio.Event()
    task = asyncio.create_task(stream.run(stop))
    await until(lambda: fake.sockets and len(fake.sockets[0].sent) == 2)
    fake.sockets[0].drop()
    await until(lambda: len(fake.sockets) == 2 and len(fake.sockets[1].sent) == 2)
    assert stream.connects == 2 and stream.disconnects == 1
    kinds = [k for k, _ in events]
    assert kinds.count("connected") == 2 and "disconnected" in kinds
    stop.set()
    await task


async def test_idle_connection_is_recycled():
    fake = FakeConnect()
    stream, _, events = make(fake, idle_timeout_s=0.05)
    stream.set_slugs(["a"])
    stop = asyncio.Event()
    task = asyncio.create_task(stream.run(stop))
    await until(lambda: len(fake.sockets) >= 2)
    assert any(k == "idle_reconnect" for k, _ in events)
    stop.set()
    await task


async def test_auth_failure_retries_with_backoff():
    fake = FakeConnect(fail_first=2)
    stream, _, events = make(fake)
    stream.set_slugs(["a"])
    stop = asyncio.Event()
    task = asyncio.create_task(stream.run(stop))
    await until(lambda: fake.sockets)
    assert len(fake.calls) == 3
    assert [k for k, _ in events][:2] == ["error", "error"]
    stop.set()
    await task


async def test_only_market_data_messages_can_be_sent():
    stream, _, _ = make(FakeConnect())
    stream._ws = FakeWS()
    with pytest.raises(ForbiddenMessage):
        await stream._send({"subscribe": {"requestId": "x", "subscriptionType": "SUBSCRIPTION_TYPE_ORDER"}})
    with pytest.raises(ForbiddenMessage):
        await stream._send({"createOrder": {}})
    assert stream._ws.sent == []


def test_ws_module_never_references_order_or_private_channels():
    from pathlib import Path

    src = (Path(__file__).resolve().parents[2] / "services/engine/polyquant/venue/ws_markets.py").read_text()
    for banned in ("ws/private", "orders", "SUBSCRIPTION_TYPE_ORDER", "SUBSCRIPTION_TYPE_POSITION"):
        assert banned not in src


async def test_resubscribe_never_starts_a_concurrent_recv():
    """Regression (found live): a resubscribe while recv() was pending started a second recv → 1011 disconnect."""
    class StrictWS(FakeWS):
        def __init__(self):
            super().__init__()
            self.pending = 0
            self.max_pending = 0

        async def recv(self):
            self.pending += 1
            self.max_pending = max(self.max_pending, self.pending)
            try:
                return await super().recv()
            finally:
                self.pending -= 1

    ws = StrictWS()
    frames = []
    stream = MarketsStream(KEY_ID, SECRET_B64, on_frame=lambda f, r: frames.append(f), on_event=lambda k, d: None,
                           connect=FakeConnect())
    stream._ws = ws
    stream.set_slugs(["a"])
    stop = asyncio.Event()
    task = asyncio.create_task(stream._read(ws, stop))
    await asyncio.sleep(0.02)
    for i in range(3):
        stream.set_slugs(["a", f"b{i}"])
        await asyncio.sleep(0.02)
    ws.incoming.put_nowait('{"marketData":{"marketSlug":"a"}}')
    await until(lambda: frames)
    stop.set()
    await asyncio.wait_for(task, 2)
    assert ws.max_pending == 1
