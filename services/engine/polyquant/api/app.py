"""Read-only HTTP API over the engine's in-memory state (Phase 2a). Binds to localhost by default.

Every payload carries `source` and `mode` so the UI can never present fixture or replay data as live.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from decimal import Decimal
from decimal import Decimal as _D

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

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


class PaperOrderRequest(BaseModel):
    client_order_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_.:-]+$")
    slug: str = Field(max_length=128)
    outcome: str = Field(pattern="^(UP|DOWN)$")
    side: str = Field(pattern="^(BUY|SELL)$")
    qty: _D = Field(gt=0, le=_D("100000"))
    limit_px: _D = Field(gt=0, lt=1)
    tif: str = Field(default="IOC", pattern="^(IOC|GTC)$")
    post_only: bool = False
    model_prob: _D | None = Field(default=None, ge=0, le=1)
    requires_reference: bool = True


class KillSwitchRequest(BaseModel):
    active: bool
    reason: str = Field(min_length=3, max_length=200)


def create_app(engine: Engine, paper=None) -> FastAPI:
    app = FastAPI(title="PolyQuant Terminal API", version=__version__, docs_url="/docs", redoc_url=None)
    token = engine.settings.api_token.get_secret_value() if engine.settings.api_token else None

    def require_token(x_polyquant_token: str | None) -> None:
        if token is None:
            raise HTTPException(403, "state-changing paper endpoints are disabled: set API_TOKEN in .env")
        if not x_polyquant_token or not secrets.compare_digest(x_polyquant_token, token):
            raise HTTPException(401, "missing or invalid X-PolyQuant-Token")

    def require_paper():
        if paper is None:
            raise HTTPException(503, "paper trading is not enabled")
        return paper

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

    # ---- paper trading (PAPER ONLY; no live order path exists) ---------------------------------------

    @app.get("/v1/paper/account")
    def paper_account() -> dict:
        return require_paper().account_view()

    @app.get("/v1/paper/orders")
    async def paper_orders(limit: int = 100) -> dict:
        return {"orders": await require_paper().ledger.recent_orders(max(1, min(limit, 500)))}

    @app.get("/v1/paper/fills")
    async def paper_fills(limit: int = 200) -> dict:
        return {"fills": await require_paper().ledger.fills(max(1, min(limit, 1000)))}

    @app.get("/v1/paper/risk-decisions")
    async def paper_risk(limit: int = 100, rejected_only: bool = False) -> dict:
        return {"decisions": await require_paper().ledger.risk_decisions(max(1, min(limit, 500)), rejected_only)}

    @app.get("/v1/paper/pnl")
    async def paper_pnl() -> dict:
        p = require_paper()
        b = await p.ledger.pnl_breakdown()
        open_keys = {(slug, o.value) for (slug, o) in p.st.positions}
        closed = [g for g in await p.ledger.closed_groups() if (g["slug"], g["outcome"]) not in open_keys]
        gross = sum((g["sold"] + g["payout"] - g["bought"] for g in closed), _D(0))
        fees_closed = sum((g["fees"] for g in closed), _D(0))
        acct = p.account_view()
        return {
            "closed_positions": len(closed),
            "closed_gross_pnl": str(gross),
            "closed_fees": str(fees_closed),
            "closed_net_pnl": str(gross - fees_closed),
            "equity_pnl": str(_D(acct["equity"]) - _D(acct["starting_capital"])),
            "fees_total": str(b["fees"]),
            "spread_cost_total": str(b["spread_cost"]),
            "slippage_total": str(b["slippage"]),
            "fills": b["fills"], "maker_fills": b["maker_fills"],
            "settled_positions": b["settled_positions"], "winning_positions": b["winning_positions"],
            "note": "closed_* covers positions fully exited or settled; equity_pnl includes open positions marked at "
                    "best bid (cost basis if no book). Spread cost and slippage are already inside fill prices; they "
                    "explain gross PnL and must not be subtracted again. Taker rebates (weekly) are not included.",
        }

    @app.get("/v1/paper/profiles")
    def paper_profiles() -> dict:
        from polyquant.paper.execution import PROFILES

        return {"active": require_paper().profile.name,
                "profiles": {k: {f: str(getattr(v, f)) for f in v.__dataclass_fields__} for k, v in PROFILES.items()}}

    @app.get("/v1/paper/preview")
    def paper_preview(slug: str, outcome: str, side: str, qty: _D, limit_px: _D) -> dict:
        from polyquant.domain.models import Outcome as _O
        from polyquant.paper.execution import PROFILES, instrument_px, sweep
        from polyquant.paper.models import Side as _S

        p = require_paper()
        snap = engine.books.latest(slug)
        inst = engine.registry.get(slug)
        if snap is None or inst is None:
            raise HTTPException(404, "no WebSocket book for this instrument")
        o, sd = _O(outcome), _S(side)
        now = engine.clock.now()
        out = {}
        for name, prof in PROFILES.items():
            r = sweep(snap, o, sd, qty, limit_px, prof, tick=inst.tick_size or _D("0.01"),
                      min_qty=inst.min_qty or _D("0.01"))
            fees = p.fees.order_fills([(f.qty, instrument_px(o, f.px)) for f in r.fills], now, liquidity="taker",
                                      theta_override=p._theta(inst, now)) if r.fills else []
            fee = sum((f.charged for f in fees), _D(0))
            out[name] = {"filled": str(r.filled), "vwap": _s(r.vwap), "notional": str(r.notional), "fee": str(fee),
                         "all_in_per_contract": _s((r.notional + fee) / r.filled) if r.filled else None,
                         "best": _s(r.best_px), "mid": _s(r.mid), "latency_ms": prof.latency_ms,
                         "diagnostic_only": prof.diagnostic_only}
        return {"slug": slug, "outcome": outcome, "side": side, "qty": str(qty), "limit_px": str(limit_px),
                "book_transact_time": _t(snap.transact_time), "profiles": out,
                "note": "estimates against the current book; latency means the real fill sees a later book"}

    @app.post("/v1/paper/orders")
    async def paper_submit(req: PaperOrderRequest, x_polyquant_token: str | None = Header(default=None)) -> dict:
        require_token(x_polyquant_token)
        from polyquant.domain.models import Outcome as _O
        from polyquant.paper.models import TIF as _TIF
        from polyquant.paper.models import OrderIntent
        from polyquant.paper.models import Side as _S

        intent = OrderIntent(client_order_id=req.client_order_id, slug=req.slug, outcome=_O(req.outcome),
                             side=_S(req.side), qty=req.qty, limit_px=req.limit_px, tif=_TIF(req.tif),
                             post_only=req.post_only, strategy="manual", model_prob=req.model_prob,
                             requires_reference=req.requires_reference)
        order, decision = await require_paper().submit(intent)
        return {"approved": decision.approved, "reasons": decision.reasons, "details": decision.details,
                "order": None if order is None else {"id": order.id, "status": order.status.value,
                                                     "reason": order.reason, "arrive_at": _t(order.arrive_at)}}

    @app.delete("/v1/paper/orders/{order_id}")
    async def paper_cancel(order_id: str, x_polyquant_token: str | None = Header(default=None)) -> dict:
        require_token(x_polyquant_token)
        o = await require_paper().cancel(order_id)
        if o is None:
            raise HTTPException(404, "no working order with that id")
        return {"id": o.id, "status": o.status.value}

    @app.post("/v1/paper/kill-switch")
    async def paper_kill(req: KillSwitchRequest, x_polyquant_token: str | None = Header(default=None)) -> dict:
        require_token(x_polyquant_token)
        await require_paper().set_kill_switch(req.active, req.reason)
        return {"kill_switch": req.active}

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
