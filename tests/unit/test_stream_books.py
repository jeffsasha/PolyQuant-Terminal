"""Authenticated stream integration: deterministic tests on real recorded frames (fixtures, not live data)."""
import asyncio
import copy
import json
from collections import deque
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from pathlib import Path
from types import SimpleNamespace

import pytest

import polyquant.runtime as rt
from polyquant.runtime import Runtime
from polyquant.types import MarketTerms
from polyquant.venue.stream import ForbiddenStreamMessage, MarketStream

FRAMES = [json.loads(line, parse_float=D)['frame']
          for line in (Path(__file__).parent / 'fixtures' / 'ws_book_frames.jsonl').read_text().splitlines()]
SLUG = FRAMES[0]['marketData']['marketSlug']
T0 = datetime(2026, 10, 17, 7, 45, 0, tzinfo=timezone.utc)


def frame(i, at):
    f = copy.deepcopy(FRAMES[i])
    f['marketData']['transactTime'] = at.isoformat().replace('+00:00', 'Z')
    return f


class Clock:
    def __init__(self, now): self.now = now
    def __call__(self): return self.now


def runtime(monkeypatch, clock):
    monkeypatch.setattr(rt, 'utcnow', clock)
    r = object.__new__(Runtime)
    r.collection = True; r.errors = {}; r.events = deque(); r.sequence = 0; r.last_update = None; r.gaps = 0
    r.recorded = []
    r.event = lambda kind, payload, market_id=None, source_at=None, received_at=None: r.recorded.append(
        (kind, market_id, source_at, received_at))
    r.markets = {'m1': MarketTerms('m1', SLUG, '1h', T0 - timedelta(minutes=10), T0 + timedelta(minutes=50), None)}
    r.books = {}; r.book_origin = {}; r.stream_raw = {}; r.recorded_versions = {}
    r.stream_rejected = 0; r.stream_frames = 0; r.last_stream = None; r.book_locks = {}; r.latency_ms = None
    r.stream = SimpleNamespace(connected=True, last_frame_at=clock.now, active=(SLUG,), connects=1)
    r.rest_calls = 0

    async def rest_book(market, fresh=False):
        r.rest_calls += 1
        from polyquant.market_data import normalize_book
        raw = frame(1, clock.now)
        return normalize_book(market.id, raw, {}, clock.now), raw
    r.venue = SimpleNamespace(book=rest_book)
    return r


def push(r, clock, i, source_at=None):
    clock.now = clock.now
    r.stream.last_frame_at = clock.now
    r.on_stream_frame(frame(i, source_at or clock.now), clock.now)


def test_valid_frame_becomes_stream_book(monkeypatch):
    c = Clock(T0); r = runtime(monkeypatch, c)
    push(r, c, 0)
    assert r.book_origin['m1'] == 'stream' and r.books['m1'].bids and r.stream_frames == 1


def test_malformed_and_out_of_order_frames_never_replace_a_valid_book(monkeypatch):
    c = Clock(T0); r = runtime(monkeypatch, c)
    push(r, c, 0)
    good = r.books['m1']
    bad = frame(1, c.now); bad['marketData']['bids'].reverse()  # unsorted → BookSnapshot validation fails
    r.on_stream_frame(bad, c.now)
    assert r.books['m1'] is good and r.stream_rejected == 1
    r.on_stream_frame(frame(2, T0 - timedelta(seconds=5)), c.now)  # older transactTime
    assert r.books['m1'] is good and r.errors['stream_frame'] == 'OUT_OF_ORDER'


def test_fresh_stream_book_avoids_rest_and_is_recorded_once(monkeypatch):
    c = Clock(T0); r = runtime(monkeypatch, c)
    push(r, c, 0)
    c.now = T0 + timedelta(seconds=1)
    b1 = asyncio.run(r.capture_book('m1'))
    b2 = asyncio.run(r.capture_book('m1'))
    assert b1 is b2 and r.rest_calls == 0
    assert [k for k, *_ in r.recorded] == ['book']  # one recording per distinct book version


def test_freshness_rule_unchanged_old_stream_book_falls_back_to_rest(monkeypatch):
    c = Clock(T0); r = runtime(monkeypatch, c)
    push(r, c, 0)
    c.now = T0 + timedelta(seconds=3)  # source and receive age > 2 s
    r.stream.last_frame_at = c.now  # connection alive (other markets), this book is quiet
    asyncio.run(r.capture_book('m1'))
    assert r.rest_calls == 1 and r.book_origin['m1'] == 'rest'


def test_dead_stream_falls_back_to_rest(monkeypatch):
    c = Clock(T0); r = runtime(monkeypatch, c)
    push(r, c, 0)
    r.stream.connected = False
    asyncio.run(r.capture_book('m1'))
    assert r.rest_calls == 1


def test_arrival_requires_book_received_after_modeled_arrival(monkeypatch):
    c = Clock(T0); r = runtime(monkeypatch, c)
    push(r, c, 0)  # received at T0
    arrival = T0 + timedelta(milliseconds=500)
    c.now = arrival

    async def scenario():
        async def later_frame():
            await asyncio.sleep(0.2)
            c.now = arrival + timedelta(milliseconds=200)
            push(r, c, 1)
        task = asyncio.create_task(later_frame())
        book = await r.capture_book('m1', after=arrival)
        await task
        return book
    book = asyncio.run(scenario())
    assert book.received_at >= arrival and r.rest_calls == 0


def test_arrival_without_new_stream_frame_uses_fresh_rest_read(monkeypatch):
    c = Clock(T0); r = runtime(monkeypatch, c)
    push(r, c, 0)
    arrival = T0 + timedelta(milliseconds=500)
    c.now = arrival
    book = asyncio.run(r.capture_book('m1', after=arrival))  # waits up to 1 s, then REST
    assert r.rest_calls == 1 and book.received_at >= arrival


# ---- stream client ---------------------------------------------------------------------------------------------


class FakeWS:
    def __init__(self): self.sent = []; self.incoming = asyncio.Queue()
    async def send(self, raw): self.sent.append(json.loads(raw))
    async def recv(self):
        item = await self.incoming.get()
        if isinstance(item, Exception): raise item
        return item


def test_stream_only_sends_market_data_subscriptions():
    s = MarketStream('k', 's', lambda *a: None, lambda *a: None, lambda: T0)
    s.ws = FakeWS()
    with pytest.raises(ForbiddenStreamMessage):
        asyncio.run(s.send({'subscribe': {'subscriptionType': 'SUBSCRIPTION_TYPE_ORDER'}}))
    with pytest.raises(ForbiddenStreamMessage):
        asyncio.run(s.send({'createOrder': {}}))
    assert s.ws.sent == []


def test_stream_connects_with_certifi_tls_signed_headers_and_reconnects():
    import base64

    from nacl.signing import SigningKey
    key = SigningKey.generate(); secret = base64.b64encode(bytes(key)).decode()
    calls, sockets, statuses, frames = [], [], [], []

    def connect(url, **kw):
        calls.append({'url': url, **kw})

        class CM:
            async def __aenter__(self):
                ws = FakeWS(); sockets.append(ws); return ws
            async def __aexit__(self, *exc): return False
        return CM()

    async def scenario():
        running = {'on': True}
        s = MarketStream('key-id', secret, lambda f, at: frames.append(f), lambda st, d: statuses.append(st),
                         lambda: T0, connect=connect)
        s.set_slugs([SLUG])
        task = asyncio.create_task(s.run(lambda: running['on']))
        while not sockets or not sockets[0].sent: await asyncio.sleep(0.01)
        sockets[0].incoming.put_nowait(json.dumps(frame(0, T0), default=str))
        while not frames: await asyncio.sleep(0.01)
        import websockets
        sockets[0].incoming.put_nowait(websockets.ConnectionClosedError(None, None))
        while len(sockets) < 2 or not sockets[1].sent: await asyncio.sleep(0.05)
        running['on'] = False
        sockets[1].incoming.put_nowait(websockets.ConnectionClosedError(None, None))
        await asyncio.wait_for(task, 5)
    asyncio.run(scenario())
    h = calls[0]['additional_headers']
    key.verify_key.verify(f"{h['X-PM-Timestamp']}GET/v1/ws/markets".encode(), base64.b64decode(h['X-PM-Signature']))
    assert calls[0]['ssl'] is not None and sockets[0].sent[0]['subscribe']['marketSlugs'] == [SLUG]
    assert statuses.count('CONNECTED') == 2 and 'DISCONNECTED' in statuses
    assert isinstance(frames[0]['marketData']['bids'][0]['qty'], str)


def test_subscription_change_never_starts_a_concurrent_recv():
    """Regression (live): a resubscribe while recv() was pending started a second recv → 1011 disconnect."""
    class StrictWS(FakeWS):
        def __init__(self):
            super().__init__(); self.pending = 0; self.max_pending = 0
        async def recv(self):
            self.pending += 1; self.max_pending = max(self.max_pending, self.pending)
            try:
                return await super().recv()
            finally:
                self.pending -= 1

    async def scenario():
        ws = StrictWS(); frames = []
        s = MarketStream('k', 's', lambda f, at: frames.append(f), lambda *a: None, lambda: T0, idle_timeout=5)
        s.ws = ws; s.set_slugs([SLUG])
        running = {'on': True}
        task = asyncio.create_task(s.read(ws, lambda: running['on']))
        await asyncio.sleep(0.05)
        for i in range(3):  # three subscription changes while a recv is pending
            s.set_slugs([SLUG, f'other-{i}']); await asyncio.sleep(0.05)
        ws.incoming.put_nowait(json.dumps(frame(0, T0), default=str))

        async def got_frame():
            while not frames: await asyncio.sleep(0.01)
        try:
            await asyncio.wait_for(got_frame(), 2)  # an orphaned concurrent recv would swallow the frame
        finally:
            running['on'] = False
        ws.incoming.put_nowait(json.dumps(frame(1, T0), default=str))
        task.cancel()
        with __import__('contextlib').suppress(asyncio.CancelledError, Exception):
            await asyncio.wait_for(task, 2)
        return ws, frames
    ws, frames = asyncio.run(scenario())
    assert ws.max_pending == 1 and frames
    subs = [m for m in ws.sent if 'subscribe' in m]
    assert len(subs) == 4  # initial + three changes, all on the same connection



# ---- regressions from the independent review ---------------------------------------------------------------------


def test_frame_without_source_time_never_replaces_a_valid_book(monkeypatch):
    c = Clock(T0); r = runtime(monkeypatch, c)
    push(r, c, 0)
    good = r.books['m1']
    f = frame(1, c.now); del f['marketData']['transactTime']
    r.on_stream_frame(f, c.now)
    assert r.books['m1'] is good and r.errors['stream_frame'] == 'MISSING_SOURCE_TIME'


def test_recorded_stream_book_keeps_its_true_receive_time(monkeypatch):
    c = Clock(T0); r = runtime(monkeypatch, c)
    push(r, c, 0)
    c.now = T0 + timedelta(milliseconds=1500)
    asyncio.run(r.capture_book('m1'))
    assert r.recorded[-1][3] == T0  # frame arrival time, not the later time of use


def test_arrival_stream_book_needs_source_time_after_arrival(monkeypatch):
    c = Clock(T0); r = runtime(monkeypatch, c)
    arrival = T0 + timedelta(milliseconds=500)
    c.now = arrival + timedelta(milliseconds=100)
    push(r, c, 0, source_at=T0)  # received after arrival, but the book state is from before it
    assert r.stream_book('m1', after=arrival) is None


def test_bad_frames_are_counted_and_never_drop_the_connection():
    statuses, frames = [], []

    async def scenario():
        ws = FakeWS()
        s = MarketStream('k', 's', lambda f, at: frames.append(f), lambda st, d: statuses.append(st), lambda: T0,
                         idle_timeout=5)
        s.ws = ws
        running = {'on': True}
        task = asyncio.create_task(s.read(ws, lambda: running['on']))
        for bad in ('[]', 'null', '"x"', '7', b'\xff\xfe', '{not json'):
            ws.incoming.put_nowait(bad)
        ws.incoming.put_nowait(json.dumps(frame(0, T0), default=str))

        async def got():
            while not frames: await asyncio.sleep(0.01)
        await asyncio.wait_for(got(), 2)
        running['on'] = False
        task.cancel()
        with __import__('contextlib').suppress(asyncio.CancelledError):
            await task
    asyncio.run(scenario())
    assert statuses.count('BAD_FRAME') == 6 and len(frames) == 1


def test_consumer_exception_does_not_drop_the_connection():
    statuses = []

    def broken(f, at): raise KeyError('consumer bug')

    async def scenario():
        ws = FakeWS()
        s = MarketStream('k', 's', broken, lambda st, d: statuses.append(st), lambda: T0, idle_timeout=5)
        running = {'on': True}
        task = asyncio.create_task(s.read(ws, lambda: running['on']))
        ws.incoming.put_nowait(json.dumps(frame(0, T0), default=str))
        await asyncio.sleep(0.1)
        running['on'] = False; task.cancel()
        with __import__('contextlib').suppress(asyncio.CancelledError):
            await task
        return task
    asyncio.run(scenario())
    assert statuses == ['BAD_FRAME']


def test_status_bad_frame_counts_and_one_disconnect_is_one_gap(monkeypatch):
    c = Clock(T0); r = runtime(monkeypatch, c)
    r.stream_status = 'CONNECTED'
    r.on_stream_status('BAD_FRAME', {})
    r.on_stream_status('ERROR', {'error': 'ConnectionClosedError'})
    r.on_stream_status('DISCONNECTED', {})
    assert r.stream_rejected == 1 and r.gaps == 1
