from __future__ import annotations

import copy
import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from polyquant.clock import FakeClock
from polyquant.domain.models import BBOSnapshot
from polyquant.domain.timeutil import parse_utc
from polyquant.marketdata.book import BookRejected, L2Book, parse_book_frame
from polyquant.marketdata.books import BookService, book_feed_name
from polyquant.marketdata.quality import ClockSkewMonitor, DataHealth
from tests.conftest import utc

WS = Path(__file__).resolve().parents[1] / "fixtures" / "ws"
SLUG_1H = "cpc-btc-updown-1h-2026-10-17-0700z"


def frames(name: str) -> list[tuple[dict, object]]:
    out = []
    for line in (WS / name).read_text().splitlines():
        r = json.loads(line, parse_float=Decimal)
        out.append((r["frame"], parse_utc(r["recv_at"])))
    return out


# ---- parsing and validation on real frames --------------------------------------------------------


def test_real_frame_parses_as_full_book():
    frame, recv = frames("book_1h_sequence.jsonl")[0]
    snap = parse_book_frame(frame, recv)
    assert snap.slug == SLUG_1H
    assert len(snap.bids) == 40 and len(snap.offers) == 10
    assert snap.best_bid == Decimal("0.8900") and snap.best_ask == Decimal("0.9000")
    assert all(isinstance(lv.px, Decimal) and isinstance(lv.qty, Decimal) for lv in snap.bids + snap.offers)
    assert snap.transact_time.tzinfo is not None


def test_down_ladder_is_mirror_of_up_book():
    frame, recv = frames("book_1h_sequence.jsonl")[0]
    snap = parse_book_frame(frame, recv)
    # buying Down consumes the Up bids: best Down ask = 1 - best Up bid, same quantity
    assert snap.down_asks()[0].px == Decimal(1) - snap.best_bid
    assert snap.down_asks()[0].qty == snap.bids[0].qty
    assert snap.down_bids()[0].px == Decimal(1) - snap.best_ask
    # Down ladder is also best-first: asks ascending
    pxs = [lv.px for lv in snap.down_asks()]
    assert pxs == sorted(pxs)


def test_microprice_and_imbalance_bounds():
    frame, recv = frames("book_1h_sequence.jsonl")[0]
    snap = parse_book_frame(frame, recv)
    mp = snap.microprice()
    assert snap.best_bid <= mp <= snap.best_ask
    assert Decimal(-1) <= snap.imbalance(5) <= Decimal(1)


def _frame():
    return copy.deepcopy(frames("book_1h_sequence.jsonl")[0][0])


@pytest.mark.parametrize("mutate,kind", [
    (lambda md: md["bids"].reverse(), "unsorted"),
    (lambda md: md["bids"].insert(1, copy.deepcopy(md["bids"][0])), "duplicate_level"),
    (lambda md: md["offers"][0].update(qty="0"), "non_positive_qty"),
    (lambda md: md["bids"].insert(0, {"px": {"value": "0.95", "currency": "USD"}, "qty": "1"}), "crossed"),
    (lambda md: md["offers"].append({"px": {"value": "1.00", "currency": "USD"}, "qty": "1"}), "price_out_of_range"),
    (lambda md: md["bids"][0].update(qty=1.5), "bad_level"),
    (lambda md: md.pop("transactTime"), "malformed"),
])
def test_invalid_frames_are_rejected(mutate, kind):
    f = _frame()
    mutate(f["marketData"])
    with pytest.raises(BookRejected) as ei:
        parse_book_frame(f, utc(2026, 10, 17, 7, 45))
    assert ei.value.kind == kind


def test_book_replaces_and_rejects_out_of_order():
    seq = [parse_book_frame(f, r) for f, r in frames("book_1h_sequence.jsonl")]
    book = L2Book(SLUG_1H)
    assert book.apply(seq[0])
    assert book.apply(seq[5]) in (True, False)
    with pytest.raises(BookRejected) as ei:
        book.apply(seq[3])  # older transactTime than the current book
    assert ei.value.kind == "out_of_order"
    assert book.snapshot is seq[5], "previous book must be kept after a rejected frame"
    # equal transactTime is allowed (observed twice in live data)
    assert book.apply(seq[5]) is False


# ---- BookService over real sequences ---------------------------------------------------------------


def svc(sink, clock=None):
    clock = clock or FakeClock(utc(2026, 10, 17, 7, 45))
    health = DataHealth(sink)
    return BookService(sink, clock, health, stale_after_s=30, skew=ClockSkewMonitor(sink)), health


def test_service_processes_real_sequence_without_rejections(sink):
    s, health = svc(sink)
    s.track([SLUG_1H])
    s.watch_open([SLUG_1H])
    for f, r in frames("book_1h_sequence.jsonl"):
        s.on_frame(f, r)
    assert s.rejected == {}
    assert s.books[SLUG_1H].frames == 40
    assert 0 < len(sink.books) <= 40  # only changed books are emitted for recording
    assert health.feeds[book_feed_name(SLUG_1H)].last_recv_at is not None
    assert s.skew.local_lag_lower_bound_ms > 0  # this capture was taken with the local clock ~120 ms slow


def test_untracked_market_frames_are_ignored(sink):
    s, _ = svc(sink)
    s.track([])
    for f, r in frames("book_1h_sequence.jsonl")[:3]:
        s.on_frame(f, r)
    assert sink.books == [] and s.rejected == {}


def test_boundary_close_expire_and_open(sink):
    s, _ = svc(sink)
    old, new = "cpc-btc-updown-15m-2026-10-17-0730z", "cpc-btc-updown-15m-2026-10-17-0745z"
    s.track([old, new])
    for f, r in frames("boundary_0745z.jsonl"):
        s.on_frame(f, r)
    assert s.rejected == {}
    assert s.latest(old).state == "MARKET_STATE_EXPIRED" and s.latest(old).bids == ()
    assert s.latest(new).state == "MARKET_STATE_OPEN" and s.latest(new).best_bid is not None
    # the new window's book arrived within ~1.3 s of the 07:45:00 open
    assert (s.latest(new).recv_at - utc(2026, 10, 17, 7, 45)).total_seconds() < 5


def test_trades_parsed_with_id_and_unit(sink):
    s, _ = svc(sink)
    for f, r in frames("trades.jsonl"):
        s.on_frame(f, r)
    assert s.trades == 8 and len(sink.trades) == 8
    t = sink.trades[0]
    assert t.trade_id and t.quantity_unit == "USD" and isinstance(t.price, Decimal)
    assert t.taker_side in ("ORDER_SIDE_BUY", "ORDER_SIDE_SELL")


def test_server_error_and_unknown_frames_are_reported(sink):
    s, _ = svc(sink)
    s.on_frame({"requestId": "md-1", "error": "invalid market slug"}, utc(2026, 10, 17, 7, 45))
    s.on_frame({"somethingNew": {}}, utc(2026, 10, 17, 7, 45))
    s.on_frame({"heartbeat": {}}, utc(2026, 10, 17, 7, 45))
    s.on_frame({"requestId": "md-1", "unsubscribed": {}}, utc(2026, 10, 17, 7, 45))  # seen live at rollover
    kinds = [k for _, k, _, _ in sink.quality]
    assert kinds == ["server_error", "unknown_frame"] and s.heartbeats == 1 and s.control_frames == 1


# ---- reconciliation with REST BBO -----------------------------------------------------------------


def _rest(slug, bid, ask, at, nb=None, na=None):
    return BBOSnapshot(slug=slug, best_bid=Decimal(bid), best_ask=Decimal(ask), bid_depth=nb, ask_depth=na,
                       bid_shares=None, ask_shares=None, last_trade_px=None, current_px=None, shares_traded=None,
                       open_interest=None, state=None, last_trade_ts=None, sent_at=at, recv_at=at)


def test_reconcile_match_mismatch_and_no_data(sink):
    s, _ = svc(sink)
    s._min_history = timedelta(0)
    s.track([SLUG_1H])
    seq = frames("book_1h_sequence.jsonl")
    for f, r in seq:
        s.on_frame(f, r)
    first = parse_book_frame(*seq[0])
    at = first.recv_at
    assert s.reconcile_bbo(_rest(SLUG_1H, str(first.best_bid), str(first.best_ask), at, 40, 10)) is True
    assert s.reconcile_bbo(_rest(SLUG_1H, "0.10", "0.20", at)) is False
    assert any(k == "bbo_uncorroborated" for _, k, _, _ in sink.quality)
    far = at.replace(hour=12)
    assert s.reconcile_bbo(_rest(SLUG_1H, "0.10", "0.20", far)) is None
    st = s.reconcile.as_dict()
    assert st["samples"] == 3 and st["compared"] == 2 and st["matches"] == 1 and st["corroborated"] == 1
    assert st["level_count_match_rate"] == 1.0


# ---- clock skew -------------------------------------------------------------------------------------


def test_clock_skew_lower_bound_and_alert(sink):
    m = ClockSkewMonitor(sink, threshold_ms=100)
    t0 = utc(2026, 10, 17, 8)
    from datetime import timedelta

    m.observe(t0, t0 + timedelta(milliseconds=40))   # recv "before" source → local clock behind ≥ 40 ms
    m.observe(t0, t0 - timedelta(milliseconds=30))   # normal positive delay
    assert m.local_lag_lower_bound_ms == pytest.approx(40)
    m.evaluate(t0)
    assert not m.alerting
    m.observe(t0, t0 + timedelta(milliseconds=150))
    m.evaluate(t0)
    assert m.alerting and sink.quality[-1][1] == "skew_high"


def test_reconcile_aligns_on_cached_rest_data_time(sink):
    """A REST body produced 20 s ago (CDN cache) must be compared with the WS book of 20 s ago, not of now."""
    from dataclasses import replace
    from datetime import timedelta

    s, _ = svc(sink)
    s._min_history = timedelta(0)
    s.track([SLUG_1H])
    seq = [parse_book_frame(f, r) for f, r in frames("book_1h_sequence.jsonl")]
    t0 = seq[0].recv_at
    old = replace(seq[0], recv_at=t0)
    new = replace(seq[-1], recv_at=t0 + timedelta(seconds=20), transact_time=t0 + timedelta(seconds=20),
                  bids=seq[0].bids[1:], offers=seq[0].offers)  # best bid has moved
    s._on_book({"marketData": {}}, t0)  # malformed frames are ignored safely
    for snap in (old, new):
        s.books[SLUG_1H].apply(snap)
        s._tops[SLUG_1H].append((snap.recv_at, snap.best_bid, snap.best_ask, len(snap.bids), len(snap.offers)))
    received = t0 + timedelta(seconds=20, milliseconds=300)
    rest = replace(_rest(SLUG_1H, str(old.best_bid), str(old.best_ask), received),
                   data_as_of=t0.replace(microsecond=0) + timedelta(seconds=1), cache_status="HIT", cache_age_s=20)
    assert s.reconcile_bbo(rest) is True
    # without the data-time alignment the same sample is compared to the moved book: not a strict match, but the
    # value is in the WS history, so it is reported as delayed (corroborated), not as an integrity failure
    rest_no_meta = replace(rest, data_as_of=None)
    assert s.reconcile_bbo(rest_no_meta) is False
    assert sink.quality[-1][1] == "bbo_delayed" and s.reconcile.corroborated == 2


def test_reconcile_without_enough_ws_history_is_not_a_failure(sink):
    """Regression (live run): right after start-up a REST body older than our WS history was flagged
    'uncorroborated'. It must count as insufficient history instead."""
    s, _ = svc(sink)
    s.track([SLUG_1H])
    seq = frames("book_1h_sequence.jsonl")
    for f, r in seq:
        s.on_frame(f, r)
    first = parse_book_frame(*seq[0])
    from dataclasses import replace
    from datetime import timedelta

    rest = replace(_rest(SLUG_1H, "0.10", "0.20", first.recv_at + timedelta(seconds=1)),
                   data_as_of=first.recv_at.replace(microsecond=0))
    assert s.reconcile_bbo(rest) is None
    assert s.reconcile.no_ws_data == 1
    assert not any(k.startswith("bbo_") for _, k, _, _ in sink.quality)
