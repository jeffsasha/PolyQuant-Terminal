"""Backfill public history: resolved BTC up/down instruments (metadata-based discovery) and the official 1s index.

Both are idempotent: instruments upsert without erasing official values, and index points never overwrite (conflicts
are logged). Requests go through the shared rate-limited gateway client.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from polyquant.domain.timeutil import to_unix
from polyquant.recorder.store import RecorderSink
from polyquant.venue.gateway import GatewayClient, GatewayError
from polyquant.venue.parsing import (
    ParseError,
    is_target_market,
    iter_event_markets,
    parse_index_points,
    parse_instrument,
)

log = logging.getLogger(__name__)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


async def backfill_instruments(gw: GatewayClient, rec: RecorderSink, *, since: datetime, until: datetime,
                               asset: str, horizons: tuple[str, ...], step: timedelta = timedelta(hours=3)) -> int:
    seen: set[str] = set()
    t = since
    while t < until:
        t2 = min(until, t + step)
        for closed in (True, False):
            offset = 0
            while True:
                try:
                    resp = await gw.events(closed=closed, end_min=_iso(t), end_max=_iso(t2), offset=offset)
                except GatewayError as exc:
                    log.warning("events %s..%s failed: %s", t, t2, exc)
                    break
                if not resp.ok:
                    break
                events = resp.data.get("events") or []
                for ev, m in iter_event_markets(resp.data):
                    if not is_target_market(m, asset, horizons):
                        continue
                    try:
                        inst = parse_instrument(m, event_slug=ev)
                    except ParseError as exc:
                        rec.quality_event("backfill", "parse_rejected", {"slug": m.get("slug"), "error": str(exc)},
                                          resp.recv_at)
                        continue
                    if inst.slug not in seen:
                        seen.add(inst.slug)
                        rec.instrument_changed(inst, {"_backfill": True}, resp.recv_at)
                if len(events) < 100:
                    break
                offset += len(events)
        await rec.flush()
        log.info("instruments %s..%s: %d total", t.date(), t2.strftime("%H:%M"), len(seen))
        t = t2
    return len(seen)


async def backfill_index(gw: GatewayClient, rec: RecorderSink, *, since: datetime, until: datetime,
                         asset: str, chunk_s: int = 3600) -> int:
    total = 0
    start = to_unix(since)
    end = to_unix(until)
    while start <= end:
        stop = min(end, start + chunk_s - 1)
        try:
            resp = await gw.index_history(asset, start, stop)
            pts = parse_index_points(resp.data, asset=asset, recv_at=resp.recv_at) if resp.ok else []
        except (GatewayError, ParseError) as exc:
            log.warning("index %s..%s failed: %s", start, stop, exc)
            pts = []
        if pts:
            rec.index_points(pts)
            total += len(pts)
            got = {to_unix(p.ts) for p in pts}
            missing = (stop - start + 1) - len(got)
            if missing:
                rec.quality_event("backfill", "index_gap", {"from": start, "to": stop, "missing": missing},
                                  resp.recv_at)
        if total and total % (chunk_s * 24) < chunk_s:
            await rec.flush()
            log.info("index backfilled through %s (%d points)", datetime.fromtimestamp(stop, UTC).isoformat(), total)
        start = stop + 1
    await rec.flush()
    return total
