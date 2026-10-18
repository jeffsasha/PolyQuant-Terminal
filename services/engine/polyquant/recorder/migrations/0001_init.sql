-- Phase 2a: market-data recording. Event tables are append-only (no UPDATE/DELETE in application code).

CREATE TABLE instruments (
    slug              text PRIMARY KEY,
    market_id         text NOT NULL,
    event_slug        text,
    asset             text NOT NULL,
    horizon           text NOT NULL CHECK (horizon IN ('15m', '1h')),
    index_symbol      text NOT NULL,
    window_start      timestamptz NOT NULL,
    window_end        timestamptz NOT NULL CHECK (window_end > window_start),
    status            text NOT NULL,
    price_to_beat     numeric(20, 8),
    settlement_price  numeric(20, 8),
    settlement_flag   smallint CHECK (settlement_flag IN (0, 1)),
    fee_coefficient   numeric(12, 8),
    tick_size         numeric(12, 8),
    min_qty           numeric(20, 8),
    up_side_label     text NOT NULL,
    down_side_label   text NOT NULL,
    description       text NOT NULL,
    source            text NOT NULL,
    first_seen_at     timestamptz NOT NULL,
    updated_at        timestamptz NOT NULL
);
CREATE INDEX instruments_window_idx ON instruments (horizon, window_start);

CREATE TABLE instrument_events (
    id           bigserial PRIMARY KEY,
    slug         text NOT NULL REFERENCES instruments (slug),
    observed_at  timestamptz NOT NULL,
    changes      jsonb NOT NULL
);
CREATE INDEX instrument_events_slug_idx ON instrument_events (slug, observed_at);

CREATE TABLE index_points (
    asset       text NOT NULL,
    ts          timestamptz NOT NULL,      -- venue candle timestamp (source time)
    value       numeric(20, 8) NOT NULL,
    tick_count  integer NOT NULL,
    recv_at     timestamptz NOT NULL,      -- local receive time
    source      text NOT NULL,
    PRIMARY KEY (asset, ts)
);

CREATE TABLE bbo_snapshots (
    id              bigserial PRIMARY KEY,
    slug            text NOT NULL REFERENCES instruments (slug),
    sent_at         timestamptz NOT NULL,
    recv_at         timestamptz NOT NULL,
    best_bid        numeric(12, 6),
    best_ask        numeric(12, 6),
    bid_depth       integer,
    ask_depth       integer,
    bid_shares      numeric(20, 6),
    ask_shares      numeric(20, 6),
    last_trade_px   numeric(12, 6),
    current_px      numeric(12, 6),
    shares_traded   numeric(24, 6),
    open_interest   numeric(24, 6),
    state           text,
    last_trade_ts   timestamptz,           -- venue trade time; NOT a quote timestamp
    source          text NOT NULL,
    raw             jsonb NOT NULL
);
CREATE INDEX bbo_snapshots_slug_idx ON bbo_snapshots (slug, recv_at);

CREATE TABLE data_quality_events (
    id      bigserial PRIMARY KEY,
    at      timestamptz NOT NULL,
    feed    text NOT NULL,
    kind    text NOT NULL,
    detail  jsonb NOT NULL
);
CREATE INDEX data_quality_events_at_idx ON data_quality_events (at);
