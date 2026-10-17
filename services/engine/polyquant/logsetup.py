"""Logging with secret redaction applied to every record before it is emitted."""

from __future__ import annotations

import logging
import re

REDACTED = "<redacted>"
# A base64 Ed25519 secret key is 44 chars (32 bytes) or 88 chars (64 bytes, seed+public).
_KEY_SHAPE = re.compile(r"(?<![A-Za-z0-9+/])(?:[A-Za-z0-9+/]{43}=|[A-Za-z0-9+/]{86}==)(?![A-Za-z0-9+/=])")


class RedactingFilter(logging.Filter):
    def __init__(self, secrets: list[str] | None = None) -> None:
        super().__init__()
        self._secrets = sorted({s for s in (secrets or []) if s and len(s) >= 8}, key=len, reverse=True)

    def redact(self, text: str) -> str:
        for s in self._secrets:
            text = text.replace(s, REDACTED)
        return _KEY_SHAPE.sub(REDACTED, text)

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        red = self.redact(msg)
        if record.exc_info:
            formatted = logging.Formatter().formatException(record.exc_info)
            record.exc_text = self.redact(formatted)
        if red != msg or record.args:
            record.msg, record.args = red, None
        return True


def setup_logging(level: str = "INFO", secrets: list[str] | None = None) -> RedactingFilter:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    filt = RedactingFilter(secrets)
    handler.addFilter(filt)
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    return filt
