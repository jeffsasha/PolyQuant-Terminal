import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_url: str
    data_dir: Path
    web_origin: str = "http://127.0.0.1:3000"
    mode: str = "PAPER"
    reference_validated: bool = False
    raw_quota: int = 10_000_000_000

    @classmethod
    def from_env(cls, environ=None):
        e = os.environ if environ is None else environ
        if e.get("LIVE_TRADING_ENABLED", "false").strip().lower() not in ("false", "0", "no", ""):
            raise ValueError("Live trading is prohibited in this build")
        if any(k.startswith("NEXT_PUBLIC_") and any(word in k for word in ("SECRET", "KEY_ID", "PASSWORD")) for k in e):
            raise ValueError("Credentials must never be configured as public frontend variables")
        return cls(e.get("DATABASE_URL", ""), Path(e.get("POLYQUANT_DATA_DIR", ".local")),
                   e.get("WEB_ORIGIN", "http://127.0.0.1:3000"))
