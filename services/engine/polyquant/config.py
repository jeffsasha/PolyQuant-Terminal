"""Runtime settings, read from the environment (and an optional git-ignored .env)."""

from __future__ import annotations

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
    bbo_stale_after_s: float = 10.0
    discovery_stale_after_s: float = 180.0

    horizons: tuple[str, ...] = ("15m", "1h")
    asset: str = "btc"

    api_host: str = "127.0.0.1"
    api_port: int = 8787

    @property
    def has_credentials(self) -> bool:
        return bool(self.polymarket_us_key_id and self.polymarket_us_secret_key)
