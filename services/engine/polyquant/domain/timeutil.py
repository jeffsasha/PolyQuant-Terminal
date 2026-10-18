"""UTC / US-Eastern helpers. All internal times are aware UTC datetimes."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")


def parse_utc(value: str) -> datetime:
    """Parse an RFC 3339 timestamp from the venue (e.g. '2026-10-17T05:41:54.667293388Z') to aware UTC.

    Python only keeps microseconds, so nanosecond digits are truncated (never rounded up).
    """
    s = value.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    if "." in s:
        head, rest = s.split(".", 1)
        # split fractional part from the offset
        for i, ch in enumerate(rest):
            if ch in "+-":
                frac, offset = rest[:i], rest[i:]
                break
        else:
            frac, offset = rest, ""
        s = f"{head}.{frac[:6].ljust(6, '0')}{offset}"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        raise ValueError(f"timestamp without timezone: {value!r}")
    return dt.astimezone(UTC)


def from_unix(ts: int | float) -> datetime:
    return datetime.fromtimestamp(ts, UTC)


def to_unix(dt: datetime) -> int:
    if dt.tzinfo is None:
        raise ValueError("naive datetime")
    return int(dt.timestamp())


def to_et(dt: datetime) -> datetime:
    return dt.astimezone(ET)


def format_et(dt: datetime) -> str:
    """e.g. '1:30AM ET' in the style of the venue's market descriptions (handles EDT/EST)."""
    local = to_et(dt)
    hour = local.hour % 12 or 12
    return f"{hour}:{local.minute:02d}{'AM' if local.hour < 12 else 'PM'} ET"
