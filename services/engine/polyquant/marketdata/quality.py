"""Per-feed freshness, latency and error tracking. Stale/fresh transitions are emitted as quality events."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from statistics import median

from polyquant.interfaces import EventSink


def _p95(xs: list[float]) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    return s[min(len(s) - 1, int(round(0.95 * (len(s) - 1))))]


@dataclass
class FeedHealth:
    name: str
    stale_after_s: float
    last_source_ts: datetime | None = None
    last_recv_at: datetime | None = None
    errors: int = 0
    last_error: str | None = None
    stale: bool = True  # stale until the first update arrives
    latencies_ms: deque = field(default_factory=lambda: deque(maxlen=300))

    def mark(self, recv_at: datetime, source_ts: datetime | None = None, latency_ms: float | None = None) -> None:
        self.last_recv_at = recv_at
        if source_ts is not None:
            self.last_source_ts = source_ts
        if latency_ms is not None:
            self.latencies_ms.append(latency_ms)

    def error(self, message: str) -> None:
        self.errors += 1
        self.last_error = message

    def age_s(self, now: datetime) -> float | None:
        return None if self.last_recv_at is None else (now - self.last_recv_at).total_seconds()

    def evaluate(self, now: datetime) -> bool:
        age = self.age_s(now)
        return age is None or age > self.stale_after_s

    def snapshot(self, now: datetime) -> dict:
        lat = list(self.latencies_ms)
        return {
            "feed": self.name,
            "stale": self.stale,
            "age_s": self.age_s(now),
            "stale_after_s": self.stale_after_s,
            "last_source_ts": self.last_source_ts.isoformat() if self.last_source_ts else None,
            "last_recv_at": self.last_recv_at.isoformat() if self.last_recv_at else None,
            "latency_ms_p50": median(lat) if lat else None,
            "latency_ms_p95": _p95(lat),
            "errors": self.errors,
            "last_error": self.last_error,
        }


class DataHealth:
    def __init__(self, sink: EventSink) -> None:
        self._sink = sink
        self.feeds: dict[str, FeedHealth] = {}

    def register(self, name: str, stale_after_s: float) -> FeedHealth:
        fh = self.feeds.get(name)
        if fh is None:
            fh = self.feeds[name] = FeedHealth(name, stale_after_s)
        return fh

    def unregister(self, name: str) -> None:
        self.feeds.pop(name, None)

    def evaluate(self, now: datetime) -> None:
        for fh in self.feeds.values():
            stale = fh.evaluate(now)
            if stale != fh.stale:
                fh.stale = stale
                self._sink.quality_event(fh.name, "stale" if stale else "fresh",
                                         {"age_s": fh.age_s(now), "threshold_s": fh.stale_after_s}, now)

    def is_stale(self, name: str) -> bool:
        fh = self.feeds.get(name)
        return True if fh is None else fh.stale

    def snapshot(self, now: datetime) -> list[dict]:
        return [fh.snapshot(now) for fh in self.feeds.values()]
