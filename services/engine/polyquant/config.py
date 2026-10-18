"""Runtime settings, read from the environment (and an optional git-ignored .env)."""

from __future__ import annotations

from decimal import Decimal
from typing import Final

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Live trading is disabled at the code boundary. This is deliberately a constant, not a setting:
# no environment variable, config file or UI toggle can change it. See docs/SECURITY.md §3.
LIVE_TRADING_ENABLED: Final[bool] = False

GATEWAY_BASE_URL: Final[str] = "https://gateway.polymarket.us"
API_BASE_URL: Final[str] = "https://api.polymarket.us"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql://polyquant@127.0.0.1:54329/polyquant"

    polymarket_us_key_id: SecretStr | None = None
    polymarket_us_secret_key: SecretStr | None = None

    gateway_max_rps: float = Field(default=2.0, gt=0, le=20)
    http_timeout_s: float = Field(default=10.0, gt=0)

    discovery_interval_s: float = 60.0
    discovery_lookahead_s: int = 3 * 3600
    discovery_lookback_s: int = 2 * 3600
    index_poll_interval_s: float = 1.0
    bbo_poll_interval_s: float = 1.0  # per request, round-robin over OPEN instruments
    instrument_refresh_interval_s: float = 5.0

    index_stale_after_s: float = 5.0
    # REST /bbo is CDN-cached for up to 30 s (RESEARCH_AUDIT §1.4), so its data is routinely 0-30 s old.
    bbo_stale_after_s: float = 40.0
    # The WS sends only on change (no heartbeats observed), so a quiet book is not by itself a fault.
    book_stale_after_s: float = 30.0
    clock_skew_alert_ms: float = 250.0
    book_record_levels: int = 0  # 0 = full depth (measured ~1.4 GB/day of level data for 3 active markets)

    # External spot (Strategy A feature): Kraken BTC/USD public trades, 1 s bars. Public data, no key.
    spot_enabled: bool = True
    spot_stale_after_s: float = 60.0  # Kraken BTC trades are sparse (~1 active second in 4)

    # Authenticated markets WebSocket (read-only market data). Used only when credentials are present.
    ws_enabled: bool = True
    ws_idle_timeout_s: float = 30.0
    # With the WebSocket active, REST BBO is polled only to reconcile against the WS book.
    bbo_reconcile_interval_s: float = 5.0
    discovery_stale_after_s: float = 180.0

    horizons: tuple[str, ...] = ("15m", "1h")
    asset: str = "btc"

    api_host: str = "127.0.0.1"
    api_port: int = 8787
    # Required for state-changing paper endpoints (orders, cancel, kill switch). Unset = those endpoints are disabled.
    api_token: SecretStr | None = None

    # Paper trading (Phase 3). There is no live mode; see LIVE_TRADING_ENABLED above.
    paper_enabled: bool = True
    paper_account: str = "paper-main"
    paper_profile: str = "conservative"  # base | conservative | stress (optimistic is diagnostic only)
    paper_starting_capital: Decimal = Decimal("1000")
    paper_step_interval_s: float = 0.25
    paper_day_tz: str = "America/New_York"
    maker_fee_tier: int = 1

    @property
    def has_credentials(self) -> bool:
        return bool(self.polymarket_us_key_id and self.polymarket_us_secret_key)
