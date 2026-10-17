"""Read-only HTTP API over the engine's in-memory state (Phase 2a). Binds to localhost by default.

Every payload carries `source` and `mode` so the UI can never present fixture or replay data as live.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import FastAPI, HTTPException

from polyquant import __version__
from polyquant.config import LIVE_TRADING_ENABLED
from polyquant.domain.models import Horizon, Instrument, phase_of
from polyquant.domain.timeutil import format_et
from polyquant.engine import Engine
from polyquant.marketdata.book import BookSnapshot
from polyquant.marketdata.books import book_feed_name


def _s(v: Decimal | None) -> str | None:
    return None if v is None else str(v)


def _t(v: datetime | None) -> str | None:
    return None if v is None else v.isoformat()


def book_view(engine: Engine, snap: BookSnapshot | None, now: datetime) -> dict | None:
    if snap is None:
        return None
    stale = engine.health.is_stale(book_feed_name(snap.slug)) if book_feed_name(snap.slug) in engine.health.feeds \
        else None
    return {
        "up_bid": _s(snap.best_bid), "up_ask": _s(snap.best_ask),
        "down_bid": _s(snap.down_bids()[0].px) if snap.offers else None,
        "down_ask": _s(snap.down_asks()[0].px) if snap.bids else None,
        "up_bid_qty": _s(snap.bids[0].qty) if snap.bids else None,
        "up_ask_qty": _s(snap.offers[0].qty) if snap.offers else None,
        "spread": _s(snap.spread), "mid": _s(snap.mid), "microprice": _s(snap.microprice()),
        "imbalance_top1": _s(snap.imbalance(1)), "imbalance_top5": _s(snap.imbalance(5)),
        "bid_depth_top5": _s(snap.depth("bid", 5)), "ask_depth_top5": _s(snap.depth("ask", 5)),
        "bid_levels": len(snap.bids), "ask_levels": len(snap.offers), "state": snap.state,
        "transact_time": _t(snap.transact_time), "recv_at": _t(snap.recv_at),
        "age_s": (now - snap.recv_at).total_seconds(), "stale": stale, "source": snap.source.value,
    }


def instrument_view(engine: Engine, inst: Instrument, now: datetime) -> dict:
    bbo = engine.bbo.latest(inst.slug)
    book = engine.books.latest(inst.slug)
    ref = engine.reference.latest()
    distance = (ref.value - inst.price_to_beat) if (ref and inst.price_to_beat is not None) else None
    return {
        "slug": inst.slug,
        "horizon": inst.horizon.value,
        "phase": phase_of(inst, now).value,
        "status": inst.status,
        "window_start": _t(inst.window_start),
        "window_end": _t(inst.window_end),
        "window_label_et": f"{format_et(inst.window_start)} – {format_et(inst.window_end)}",
        "seconds_to_close": inst.seconds_to_close(now),
        "index_symbol": inst.index_symbol,
        "price_to_beat": _s(inst.price_to_beat),
        "price_to_beat_status": "official" if inst.price_to_beat is not None else "unavailable",
        "settlement_price": _s(inst.settlement_price),
        "settlement_flag": engine.registry.settlement_flags.get(inst.slug),
        "reference_distance": _s(distance),
        "fee_coefficient": _s(inst.fee_coefficient),
        "source": inst.source.value,
        # Preferred executable view: the authenticated WS L2 book when present and fresh, else REST BBO.
        "quote_source": "ws" if book is not None and not engine.health.is_stale(book_feed_name(inst.slug))
        else ("rest" if bbo is not None else "none"),
        "book": book_view(engine, book, now),
        "bbo": None if bbo is None else {
            "up_bid": _s(bbo.up_bid), "up_ask": _s(bbo.up_ask),
            "down_bid": _s(bbo.down_bid), "down_ask": _s(bbo.down_ask),
            "spread": _s(bbo.spread), "mid": _s(bbo.mid),
            "bid_levels": bbo.bid_depth, "ask_levels": bbo.ask_depth,
            "bid_shares": _s(bbo.bid_shares), "ask_shares": _s(bbo.ask_shares),
            "last_trade_px": _s(bbo.last_trade_px), "last_trade_ts": _t(bbo.last_trade_ts),
            "recv_at": _t(bbo.recv_at), "rtt_ms": bbo.rtt_ms,
            # age of the DATA (CDN-cached up to 30 s), not of our request
            "data_as_of": _t(bbo.data_as_of), "age_s": (now - (bbo.data_as_of or bbo.recv_at)).total_seconds(),
            "cache_status": bbo.cache_status,
            "source": bbo.source.value,
        },
    }


def create_app(engine: Engine) -> FastAPI:
    app = FastAPI(title="PolyQuant Terminal API", version=__version__, docs_url="/docs", redoc_url=None)

    @app.get("/health")
    def health() -> dict:
        now = engine.clock.now()
        feeds = engine.health.snapshot(now)
        return {"ok": not any(f["stale"] for f in feeds if f["feed"] in ("index", "discovery")),
                "mode": "PAPER", "live_trading_enabled": LIVE_TRADING_ENABLED, "now": now.isoformat(),
                "feeds": feeds, "gateway": {k: v for k, v in vars(engine.gateway.stats).items() if k != "rtt_ms"},
                "ws": None if engine.stream is None else {
                    "connected": engine.stream.connected, "connects": engine.stream.connects,
                    "disconnects": engine.stream.disconnects, "frames": engine.stream.frames,
                    "subscribed": list(engine.stream.subscribed), "trades": engine.books.trades,
                    "heartbeats": engine.books.heartbeats, "rejected_frames": engine.books.rejected},
                "reconcile": engine.books.reconcile.as_dict(),
                "clock": engine.skew.snapshot()}

    @app.get("/v1/markets")
    def markets() -> dict:
        now = engine.clock.now()
        out = {}
        for h in Horizon:
            cur, nxt = engine.registry.current(h, now), engine.registry.next(h, now)
            out[h.value] = {"current": instrument_view(engine, cur, now) if cur else None,
                            "next": instrument_view(engine, nxt, now) if nxt else None}
        return {"mode": "PAPER", "now": now.isoformat(), "markets": out}

    @app.get("/v1/markets/{slug}")
    def market(slug: str) -> dict:
        inst = engine.registry.get(slug)
        if inst is None:
            raise HTTPException(404, "unknown instrument")
        return instrument_view(engine, inst, engine.clock.now())

    @app.get("/v1/markets/{slug}/book")
    def market_book(slug: str, levels: int = 20) -> dict:
        snap = engine.books.latest(slug)
        if snap is None:
            raise HTTPException(404, "no WebSocket book for this instrument (unsubscribed, not open, or no key)")
        n = max(1, min(levels, 200))
        lv = lambda xs: [[str(x.px), str(x.qty)] for x in xs[:n]]  # noqa: E731
        return {"slug": slug, "source": snap.source.value, "summary": book_view(engine, snap, engine.clock.now()),
                "up": {"bids": lv(snap.bids), "asks": lv(snap.offers)},
                # Down is the opposite side of the same book: Down asks come from Up bids (1 - px).
                "down": {"bids": lv(snap.down_bids()), "asks": lv(snap.down_asks())}}

    @app.get("/v1/reference")
    def reference(seconds: int = 300) -> dict:
        now = engine.clock.now()
        seconds = max(1, min(seconds, 3600))
        latest = engine.reference.latest()
        pts = [] if latest is None else engine.reference.buffer.window(
            latest.ts - timedelta(seconds=seconds), latest.ts)
        return {
            "asset": engine.reference.asset, "index": "BRTI (venue 60s trailing average, 1s points)",
            "status": "unavailable" if latest is None else ("stale" if engine.health.is_stale("index") else "ok"),
            "latest": None if latest is None else {"ts": _t(latest.ts), "value": _s(latest.value),
                                                    "age_s": (now - latest.ts).total_seconds()},
            "points": [[_t(p.ts), _s(p.value)] for p in pts],
            "source": "gateway",
        }

    @app.get("/v1/alerts")
    def alerts(limit: int = 50) -> dict:
        q = engine.alerts.quality[-max(1, min(limit, 200)):]
        return {"alerts": [{"feed": f, "kind": k, "detail": d, "at": _t(a)} for f, k, d, a in reversed(q)]}

    return app
