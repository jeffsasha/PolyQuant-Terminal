import re

PRODUCTION_HOST = "https://gateway.polymarket.us"


def validate_read_route(method: str, path: str) -> str:
    routes = (r"/v1/markets", r"/v1/market/slug/[A-Za-z0-9_-]+",
              r"/v1/markets/[A-Za-z0-9_-]+/(?:book|bbo|settlement)",
              r"/v1/asset-prices/history")
    if method != "GET" or not any(re.fullmatch(route, path) for route in routes):
        raise ValueError("Exchange mutation and unapproved routes are prohibited")
    return path


class ReadOnlyUSTransport:
    def __init__(self):
        import httpx
        import ssl
        ca = "/etc/ssl/cert.pem"
        from pathlib import Path
        context = ssl.create_default_context(cafile=ca if Path(ca).exists() else None)
        self.client = httpx.AsyncClient(base_url=PRODUCTION_HOST, verify=context,
            timeout=15, follow_redirects=False, headers={"Accept":"application/json"})

    async def request(self, method: str, path: str, params=None):
        validate_read_route(method, path)
        response = await self.client.request(method, path, params=params)
        response.raise_for_status()
        if len(response.content) > 8_000_000 or "json" not in response.headers.get("content-type", ""):
            raise ValueError("Invalid or oversized venue response")
        from decimal import Decimal
        return response.json(parse_float=Decimal), dict(response.headers)

    async def close(self):
        await self.client.aclose()
