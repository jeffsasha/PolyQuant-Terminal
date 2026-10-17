"""Live execution boundary. Intentionally unimplemented in this release (docs/SECURITY.md §3).

Every method raises. Enabling live trading requires a reviewed PR that replaces this module, separate deployment
approval and explicit owner confirmation; no flag, environment variable or UI toggle can reach a venue order
endpoint from this codebase.
"""

from __future__ import annotations

from typing import Any, NoReturn

from polyquant.config import LIVE_TRADING_ENABLED


class LiveTradingDisabled(RuntimeError):
    pass


class LiveExecutionEngine:
    """Conforms to the ExecutionEngine protocol; refuses every call."""

    def __init__(self, *_: Any, **__: Any) -> None:
        if LIVE_TRADING_ENABLED:  # pragma: no cover - constant False; guard against future edits
            raise LiveTradingDisabled("live engine is a stub; LIVE_TRADING_ENABLED must not be changed here")

    async def submit(self, order: Any) -> NoReturn:
        raise LiveTradingDisabled("live order submission is disabled in this release")

    async def cancel(self, order_id: str) -> NoReturn:
        raise LiveTradingDisabled("live order cancellation is disabled in this release")
