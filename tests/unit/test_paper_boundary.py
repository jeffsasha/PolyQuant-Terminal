import unittest

try:
    from polyquant.config import Settings
    from polyquant.venue.transport import validate_read_route
except ImportError:
    Settings = None


class PaperBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(Settings, "Paper-only configuration has not been implemented")

    def test_live_flag_refuses_startup(self):
        for value in ["true", "1", "yes", "TRUE"]:
            with self.assertRaises(ValueError):
                Settings.from_env({"LIVE_TRADING_ENABLED": value})

    def test_only_exact_official_read_routes_are_allowed(self):
        self.assertEqual(validate_read_route("GET", "/v1/markets"), "/v1/markets")
        self.assertEqual(validate_read_route("GET", "/v1/markets/discovered-slug/book"), "/v1/markets/discovered-slug/book")
        for method,path in [("POST","/v1/orders"),("GET","/v1/portfolio/positions"),
                            ("GET","https://evil.test/v1/markets"),("DELETE","/v1/markets"),
                            ("GET","/v1/markets/../orders/book"),("GET","/v1/markets/%2e%2e/book")]:
            with self.subTest(method=method,path=path),self.assertRaises(ValueError):
                validate_read_route(method,path)

    def test_reference_gate_cannot_be_enabled_by_environment(self):
        settings=Settings.from_env({"REFERENCE_VALIDATED":"true","LIVE_TRADING_ENABLED":"false"})
        self.assertFalse(settings.reference_validated)
        self.assertEqual(settings.mode,"PAPER")


if __name__=="__main__": unittest.main()

def test_read_transport_honors_retry_after_and_bounds_polling():
    import asyncio,httpx
    from polyquant.venue.transport import ReadOnlyUSTransport
    async def run():
        transport=ReadOnlyUSTransport();await transport.client.aclose()
        transport.client=httpx.AsyncClient(base_url="https://gateway.polymarket.us",transport=httpx.MockTransport(lambda request:httpx.Response(429,headers={'Retry-After':'10'},request=request)))
        import time
        before=time.monotonic()
        try:await transport.request('GET','/v1/markets')
        except httpx.HTTPStatusError:pass
        assert transport.next_request>=before+10
        await transport.close()
    asyncio.run(run())
