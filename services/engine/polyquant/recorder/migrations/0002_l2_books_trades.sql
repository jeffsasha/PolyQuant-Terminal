-- Phase 2b: authenticated markets WebSocket. Append-only.
-- book_snapshots stores every validated full-book frame whose levels or state changed (unchanged frames are not
-- stored; their arrival still feeds freshness metrics). Levels are JSON arrays of [px, qty] strings, best first,
-- optionally capped at BOOK_RECORD_LEVELS per side (n_bids/n_offers always hold the full counts).

CREATE TABLE book_snapshots (
    id             bigserial PRIMARY KEY,
    slug           text NOT NULL REFERENCES instruments (slug),
    transact_time  timestamptz NOT NULL,      -- venue time of the book state (source time)
    recv_at        timestamptz NOT NULL,      -- local receive time
    state          text,
    best_bid       numeric(12, 6),
    best_ask       numeric(12, 6),
    n_bids         integer NOT NULL,
    n_offers       integer NOT NULL,
    bids           jsonb NOT NULL,
    offers         jsonb NOT NULL,
    source         text NOT NULL
);
CREATE INDEX book_snapshots_slug_time_idx ON book_snapshots (slug, transact_time);

CREATE TABLE trades (
    id             bigserial PRIMARY KEY,
    trade_id       text UNIQUE,               -- venue trade id; re-sent trades are ignored
    slug           text NOT NULL REFERENCES instruments (slug),
    trade_time     timestamptz NOT NULL,
    recv_at        timestamptz NOT NULL,
    price          numeric(12, 6) NOT NULL,
    quantity       numeric(24, 6) NOT NULL,
    quantity_unit  text,                      -- as labelled by the venue; semantics unverified
    maker_side     text,
    taker_side     text,
    source         text NOT NULL,
    raw            jsonb NOT NULL
);
CREATE INDEX trades_slug_time_idx ON trades (slug, trade_time);
