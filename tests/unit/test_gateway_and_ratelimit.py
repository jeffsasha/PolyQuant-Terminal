from __future__ import annotations

import asyncio
from decimal import Decimal

import httpx
import pytest
import respx

from polyquant.venue.gateway import ForbiddenRequest, GatewayClient, GatewayError
from polyquant.venue.ratelimit import Priority, RateLimiter

BASE = "https://gateway.polymarket.us"


async def _no_sleep(_s):
    return None


def client(**kw) -> GatewayClient:
    return GatewayClient(max_rps=1000, sleep=_no_sleep, **kw)


async def test_only_get_is_allowed():
    async with client() as gw:
        with respx.mock(assert_all_called=False) as router:
            route = router.post(f"{BASE}/v1/orders").respond(200, json={})
            for method in ("POST", "PUT", "PATCH", "DELETE"):
                with pytest.raises(ForbiddenRequest):
                    await gw.request(method, "/v1/orders")
            assert not route.called, "a forbidden request reached the network layer"


def test_host_allowlist():
    with pytest.raises(ForbiddenRequest):
        GatewayClient(base_url="https://api.polymarket.us")
    with pytest.raises(ForbiddenRequest):
        GatewayClient(base_url="https://clob.polymarket.com")


@respx.mock
async def test_html_429_backs_off_then_succeeds():
    html = "<!doctype html><html>rate limited</html>"
    route = respx.get(f"{BASE}/v1/markets/x/bbo").mock(side_effect=[
        httpx.Response(429, text=html, headers={"content-type": "text/html"}),
        httpx.Response(429, text=html, headers={"content-type": "text/html"}),
        httpx.Response(200, json={"marketData": {"marketSlug": "x"}}),
    ])
    limiter = RateLimiter(1000)
    async with client(limiter=limiter) as gw:
        resp = await gw.bbo("x")
    assert resp.ok and route.call_count == 3
    assert gw.stats.rate_limited == 2 and gw.stats.retries == 2
    assert limiter._next_at > 0  # budget was paused


@respx.mock
async def test_gives_up_after_max_attempts():
    respx.get(f"{BASE}/v1/markets/x/bbo").respond(503)
    async with client(max_attempts=3) as gw:
        with pytest.raises(GatewayError) as ei:
            await gw.bbo("x")
    assert ei.value.status == 503


@respx.mock
async def test_non_json_success_is_an_error():
    respx.get(f"{BASE}/v1/markets/x/bbo").respond(200, text="<html>maintenance</html>")
    async with client() as gw:
        with pytest.raises(GatewayError, match="non-JSON"):
            await gw.bbo("x")


@respx.mock
async def test_json_numbers_decoded_as_decimal_and_timestamps_recorded():
    respx.get(f"{BASE}/v1/market/slug/x").respond(200, content=b'{"market":{"feeCoefficient":0.0695}}')
    async with client() as gw:
        resp = await gw.market_by_slug("x")
    v = resp.data["market"]["feeCoefficient"]
    assert isinstance(v, Decimal) and v == Decimal("0.0695")
    assert resp.recv_at >= resp.sent_at


@respx.mock
async def test_404_is_returned_not_retried():
    route = respx.get(f"{BASE}/v1/markets/x/settlement").respond(404, json={"code": 5, "message": "not found"})
    async with client() as gw:
        resp = await gw.settlement("x")
    assert resp.status == 404 and route.call_count == 1


async def test_rate_limiter_priority_and_spacing():
    t = [0.0]

    async def fake_sleep(s):
        t[0] += s
        await asyncio.sleep(0)

    rl = RateLimiter(2.0, monotonic=lambda: t[0], sleep=fake_sleep)
    order: list[str] = []

    async def take(name, p):
        await rl.acquire(p)
        order.append(name)

    await take("first", Priority.LOW)  # consumes the slot at t=0
    await asyncio.gather(take("low", Priority.LOW), take("high", Priority.HIGH))
    assert order == ["first", "high", "low"]
    assert t[0] >= 1.0 - 1e-9  # two more requests at 2 rps → ≥1s of simulated time


async def test_rate_limiter_penalize_pauses_everyone():
    t = [0.0]

    async def fake_sleep(s):
        t[0] += s

    rl = RateLimiter(100.0, monotonic=lambda: t[0], sleep=fake_sleep)
    rl.penalize(5.0)
    await rl.acquire(Priority.HIGH)
    assert t[0] >= 5.0


async def test_rate_limiter_low_priority_is_not_starved():
    """Regression (live run): constant HIGH/NORMAL demand must not starve LOW (discovery) forever."""
    t = [0.0]

    async def fake_sleep(s):
        t[0] += s
        await asyncio.sleep(0)

    rl = RateLimiter(2.0, monotonic=lambda: t[0], sleep=fake_sleep, max_wait_s=3.0)
    stop = False
    served_low_at: list[float] = []

    async def hog(p):
        while not stop:
            await rl.acquire(p)

    async def low():
        await rl.acquire(Priority.LOW)
        served_low_at.append(t[0])

    hogs = [asyncio.create_task(hog(Priority.HIGH)), asyncio.create_task(hog(Priority.NORMAL))]
    await asyncio.sleep(0)
    await asyncio.wait_for(low(), timeout=5)
    stop = True
    for h in hogs:
        h.cancel()
    await asyncio.gather(*hogs, return_exceptions=True)
    assert served_low_at and served_low_at[0] <= 3.0 + 2.0  # promoted after max_wait, served within a couple slots
    assert rl.promotions >= 1


@respx.mock
async def test_cdn_cache_metadata_is_captured():
    """Live finding: /bbo is served from Cloudflare with max-age=30; the body can be ~30 s old."""
    respx.get(f"{BASE}/v1/markets/x/bbo").respond(200, json={"marketData": {"marketSlug": "x"}}, headers={
        "cf-cache-status": "HIT", "age": "7", "cache-control": "public, max-age=30",
        "last-modified": "Sat, 17 Oct 2026 08:07:49 GMT"})
    async with client() as gw:
        resp = await gw.bbo("x")
    c = resp.cache
    assert c.cached and c.age_s == 7 and c.status == "HIT"
    from datetime import UTC, datetime

    assert c.last_modified == datetime(2026, 10, 17, 8, 7, 49, tzinfo=UTC)
    assert c.data_as_of(resp.recv_at) == c.last_modified


@respx.mock
async def test_uncached_response_data_as_of_is_receive_time():
    respx.get(f"{BASE}/v1/market/slug/x").respond(200, json={}, headers={"cf-cache-status": "DYNAMIC"})
    async with client() as gw:
        resp = await gw.market_by_slug("x")
    assert not resp.cache.cached and resp.cache.data_as_of(resp.recv_at) == resp.recv_at
