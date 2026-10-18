from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
import time


def risk_day_id(at):
    local=at.astimezone(ZoneInfo('America/New_York'))
    return (local.date() if local.hour>=17 else (local-timedelta(days=1)).date()).isoformat()


def next_risk_day_start(at):
    """When the current risk day ends: the next 5:00 PM America/New_York (DST-aware)."""
    zone=ZoneInfo('America/New_York'); local=at.astimezone(zone)
    boundary=local.replace(hour=17,minute=0,second=0,microsecond=0)
    if local>=boundary: boundary=(local+timedelta(days=1)).replace(hour=17,minute=0,second=0,microsecond=0)
    return boundary.replace(tzinfo=zone).astimezone(timezone.utc)


class Clock:
    def now(self): return datetime.now(timezone.utc)
    def monotonic_ns(self): return time.monotonic_ns()


class ReplayClock(Clock):
    def __init__(self,at): self.at=at
    def now(self): return self.at
    def advance(self,at):
        if at<self.at: raise ValueError('Replay availability time cannot move backward')
        self.at=at
