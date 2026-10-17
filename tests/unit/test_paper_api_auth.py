from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from pydantic import SecretStr

from polyquant.api.app import create_app

ORDER = {"client_order_id": "c-api-0001", "slug": "x", "outcome": "UP", "side": "BUY", "qty": "1", "limit_px": "0.5"}


def app_with(token):
    eng = SimpleNamespace(settings=SimpleNamespace(api_token=SecretStr(token) if token else None))
    return create_app(eng, paper=None)


async def call(app, method, path, **kw):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        return await c.request(method, path, **kw)


@pytest.mark.parametrize("method,path,body", [
    ("POST", "/v1/paper/orders", ORDER),
    ("DELETE", "/v1/paper/orders/abc", None),
    ("POST", "/v1/paper/kill-switch", {"active": True, "reason": "test"}),
])
async def test_state_changing_endpoints_disabled_without_configured_token(method, path, body):
    r = await call(app_with(None), method, path, json=body)
    assert r.status_code == 403 and "API_TOKEN" in r.text


async def test_wrong_or_missing_token_is_rejected():
    app = app_with("s3cret-token-value")
    assert (await call(app, "POST", "/v1/paper/orders", json=ORDER)).status_code == 401
    r = await call(app, "POST", "/v1/paper/orders", json=ORDER, headers={"X-PolyQuant-Token": "nope"})
    assert r.status_code == 401


async def test_valid_token_reaches_paper_layer():
    app = app_with("s3cret-token-value")
    r = await call(app, "POST", "/v1/paper/orders", json=ORDER, headers={"X-PolyQuant-Token": "s3cret-token-value"})
    assert r.status_code == 503  # authenticated, but paper trading not enabled in this app instance


async def test_order_request_validation():
    app = app_with("s3cret-token-value")
    bad = {**ORDER, "limit_px": "1.5"}
    r = await call(app, "POST", "/v1/paper/orders", json=bad, headers={"X-PolyQuant-Token": "s3cret-token-value"})
    assert r.status_code == 422
