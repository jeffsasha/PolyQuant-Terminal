from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
import time


def risk_day_id(at):
    local=at.astimezone(ZoneInfo('America/New_York'))
    return (local.date() if local.hour>=17 else (local-timedelta(days=1)).date()).isoformat()


class Clock:
    def now(self): return datetime.now(timezone.utc)
    def monotonic_ns(self): return time.monotonic_ns()


class ReplayClock(Clock):
    def __init__(self,at): self.at=at
    def now(self): return self.at
    def advance(self,at):
        if at<self.at: raise ValueError('Replay availability time cannot move backward')
        self.at=at
