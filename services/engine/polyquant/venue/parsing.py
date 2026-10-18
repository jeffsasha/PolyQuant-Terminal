"""Strict parsing of gateway JSON into domain types. Anything ambiguous raises ParseError rather than guessing."""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from polyquant.domain.models import BBOSnapshot, Horizon, IndexPoint, Instrument, Outcome, Source
from polyquant.domain.timeutil import from_unix, parse_utc

UP_DOWN = "ASSET_PRICE_MARKET_TYPE_UP_DOWN"
HORIZON_LENGTH = {Horizon.M15: timedelta(minutes=15), Horizon.H1: timedelta(hours=1)}


class ParseError(ValueError):
    pass


def _dec(value: Any, what: str) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, dict):  # {"value": "0.49", "currency": "USD"}
        if value.get("currency") not in (None, "USD"):
            raise ParseError(f"{what}: unexpected currency {value.get('currency')!r}")
        value = value.get("value")
        if value is None:
            return None
    if isinstance(value, float):
        raise ParseError(f"{what}: refusing binary float {value!r}")
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise ParseError(f"{what}: not a decimal: {value!r}") from exc


def is_target_market(market: dict, asset: str, horizons: Iterable[str]) -> bool:
    """Metadata filter (not slug-based): crypto up/down on the given asset and horizons, settled on BRTI."""
    terms = market.get("assetPriceTerms") or {}
    return (
        terms.get("marketType") == UP_DOWN
        and (terms.get("asset") or {}).get("symbol") == asset
        and terms.get("horizon") in set(horizons)
        and terms.get("indexSymbol") == "BRTI"
    )


def parse_instrument(market: dict, *, event_slug: str | None = None,
                     source: Source = Source.GATEWAY) -> Instrument:
    if "market" in market and isinstance(market["market"], dict):
        market = market["market"]
    slug = market.get("slug")
    if not slug:
        raise ParseError("market without slug")
    terms = market.get("assetPriceTerms")
    if not terms or terms.get("marketType") != UP_DOWN:
        raise ParseError(f"{slug}: not an up/down asset-price market")
    try:
        horizon = Horizon(terms.get("horizon"))
    except ValueError as exc:
        raise ParseError(f"{slug}: unsupported horizon {terms.get('horizon')!r}") from exc
    try:
        ws = parse_utc(terms["windowStart"])
        we = parse_utc(terms["windowEnd"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ParseError(f"{slug}: bad window times") from exc
    if we - ws != HORIZON_LENGTH[horizon]:
        raise ParseError(f"{slug}: window {ws}..{we} does not match horizon {horizon}")

    sides = market.get("marketSides") or []
    longs = [s for s in sides if s.get("long") is True]
    shorts = [s for s in sides if s.get("long") is False]
    if len(longs) != 1 or len(shorts) != 1:
        raise ParseError(f"{slug}: expected exactly one long and one short side, got {len(longs)}/{len(shorts)}")

    venue_outcome = None
    if market.get("status") == "MARKET_STATUS_RESOLVED":
        venue_outcome = _resolved_outcome(market.get("outcomePrices"), longs[0].get("description"), slug)

    return Instrument(
        slug=slug,
        market_id=str(market.get("id")),
        event_slug=event_slug,
        asset=(terms.get("asset") or {}).get("symbol") or "",
        horizon=horizon,
        index_symbol=terms.get("indexSymbol") or "",
        window_start=ws,
        window_end=we,
        status=market.get("status") or "",
        price_to_beat=_dec(terms.get("priceToBeat"), f"{slug}.priceToBeat"),
        settlement_price=_dec(terms.get("settlementPrice"), f"{slug}.settlementPrice"),
        fee_coefficient=_dec(market.get("feeCoefficient"), f"{slug}.feeCoefficient"),
        tick_size=_dec(market.get("orderPriceMinTickSize"), f"{slug}.tick"),
        min_qty=_dec(market.get("minimumTradeQty"), f"{slug}.minQty"),
        up_side_label=longs[0].get("description") or "Yes",
        down_side_label=shorts[0].get("description") or "No",
        description=market.get("description") or "",
        source=source,
        venue_outcome=venue_outcome,
    )


def _resolved_outcome(outcome_prices, long_label: str | None, slug: str) -> Outcome | None:
    """["1","0"] → long (Up) paid; ["0","1"] → short (Down) paid. Anything else → None (not definitive)."""
    try:
        prices = json.loads(outcome_prices) if isinstance(outcome_prices, str) else outcome_prices
        a, b = (str(x) for x in prices)
    except (TypeError, ValueError):
        return None
    norm = {("1", "0"): Outcome.UP, ("0", "1"): Outcome.DOWN}
    key = (a.rstrip("0").rstrip(".") or "0", b.rstrip("0").rstrip(".") or "0")
    out = norm.get(key)
    if out is not None and long_label not in (None, "Yes"):
        raise ParseError(f"{slug}: unexpected long-side label {long_label!r}; refusing to map outcomePrices")
    return out


def iter_event_markets(payload: dict) -> Iterator[tuple[str | None, dict]]:
    for event in payload.get("events") or []:
        for market in event.get("markets") or []:
            yield event.get("slug"), market


def parse_bbo(payload: dict, *, sent_at: datetime, recv_at: datetime, source: Source = Source.GATEWAY,
              data_as_of: datetime | None = None, cache_status: str | None = None,
              cache_age_s: int | None = None) -> BBOSnapshot:
    md = payload.get("marketData")
    if not isinstance(md, dict) or not md.get("marketSlug"):
        raise ParseError("bbo payload without marketData.marketSlug")
    slug = md["marketSlug"]
    sample = md.get("lastPriceSample") or {}
    last_ts = parse_utc(sample["ts"]) if sample.get("ts") else None

    def _int(v: Any) -> int | None:
        return None if v is None else int(v)

    return BBOSnapshot(
        slug=slug,
        best_bid=_dec(md.get("bestBid"), f"{slug}.bestBid"),
        best_ask=_dec(md.get("bestAsk"), f"{slug}.bestAsk"),
        bid_depth=_int(md.get("bidDepth")),
        ask_depth=_int(md.get("askDepth")),
        bid_shares=_dec(md.get("bidShares"), f"{slug}.bidShares"),
        ask_shares=_dec(md.get("askShares"), f"{slug}.askShares"),
        last_trade_px=_dec(md.get("lastTradePx"), f"{slug}.lastTradePx"),
        current_px=_dec(md.get("currentPx"), f"{slug}.currentPx"),
        shares_traded=_dec(md.get("sharesTraded"), f"{slug}.sharesTraded"),
        open_interest=_dec(md.get("openInterest"), f"{slug}.openInterest"),
        state=md.get("state"),
        last_trade_ts=last_ts,
        sent_at=sent_at,
        recv_at=recv_at,
        source=source,
        raw=md,
        data_as_of=data_as_of,
        cache_status=cache_status,
        cache_age_s=cache_age_s,
    )


def parse_index_points(payload: dict, *, asset: str, recv_at: datetime,
                       source: Source = Source.GATEWAY) -> list[IndexPoint]:
    out: list[IndexPoint] = []
    for series in payload.get("series") or []:
        if (series.get("asset") or {}).get("symbol") != asset:
            continue
        if series.get("currency") not in (None, "USD"):
            raise ParseError(f"index series in {series.get('currency')!r}")
        for c in series.get("candles") or []:
            value = _dec(c.get("close"), "index.close")
            if value is None or c.get("timestamp") is None:
                raise ParseError("index candle without close/timestamp")
            out.append(IndexPoint(asset=asset, ts=from_unix(int(c["timestamp"])), value=value,
                                  tick_count=int(c.get("tickCount") or 0), recv_at=recv_at, source=source))
    out.sort(key=lambda p: p.ts)
    return out
