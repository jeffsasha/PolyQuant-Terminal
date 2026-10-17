-- Phase 3: paper trading ledger. Cash and event tables are append-only; paper_orders holds the current state of
-- each order and every transition is also appended to paper_order_events. All writes for one engine event happen in
-- one transaction.

CREATE TABLE paper_accounts (
    id                text PRIMARY KEY,
    starting_capital  numeric(20, 8) NOT NULL CHECK (starting_capital > 0),
    created_at        timestamptz NOT NULL
);

-- cash_delta changes total cash; reserved_delta changes cash reserved for working orders. available = cash - reserved.
CREATE TABLE paper_ledger (
    id              bigserial PRIMARY KEY,
    account_id      text NOT NULL REFERENCES paper_accounts (id),
    ts              timestamptz NOT NULL,
    kind            text NOT NULL CHECK (kind IN ('DEPOSIT', 'RESERVE', 'RELEASE', 'BUY', 'SELL', 'FEE', 'REBATE',
                                                  'SETTLEMENT')),
    cash_delta      numeric(20, 8) NOT NULL DEFAULT 0,
    reserved_delta  numeric(20, 8) NOT NULL DEFAULT 0,
    order_id        text,
    fill_id         text,
    slug            text,
    detail          jsonb NOT NULL DEFAULT '{}'
);
CREATE INDEX paper_ledger_account_idx ON paper_ledger (account_id, ts);

CREATE TABLE paper_orders (
    id                   text PRIMARY KEY,
    account_id           text NOT NULL REFERENCES paper_accounts (id),
    client_order_id      text NOT NULL,
    slug                 text NOT NULL,
    outcome              text NOT NULL CHECK (outcome IN ('UP', 'DOWN')),
    side                 text NOT NULL CHECK (side IN ('BUY', 'SELL')),
    qty                  numeric(20, 8) NOT NULL CHECK (qty > 0),
    limit_px             numeric(12, 6) NOT NULL CHECK (limit_px > 0 AND limit_px < 1),
    tif                  text NOT NULL,
    post_only            boolean NOT NULL,
    strategy             text NOT NULL,
    model_prob           numeric(12, 8),
    requires_reference   boolean NOT NULL,
    profile              text NOT NULL,
    created_at           timestamptz NOT NULL,
    arrive_at            timestamptz NOT NULL,
    status               text NOT NULL,
    filled_qty           numeric(20, 8) NOT NULL DEFAULT 0,
    notional             numeric(20, 8) NOT NULL DEFAULT 0,
    fees                 numeric(20, 8) NOT NULL DEFAULT 0,
    reserved             numeric(20, 8) NOT NULL DEFAULT 0,
    reason               text,
    queue_ahead          numeric(20, 8),
    last_level_qty       numeric(20, 8),
    decision_best        numeric(12, 6),
    decision_mid         numeric(12, 6),
    taker_fee_exact_cum  numeric(24, 12) NOT NULL DEFAULT 0,
    taker_fee_collected  numeric(20, 8) NOT NULL DEFAULT 0,
    updated_at           timestamptz NOT NULL,
    UNIQUE (account_id, client_order_id)       -- idempotency: one order per client id
);
CREATE INDEX paper_orders_status_idx ON paper_orders (account_id, status);

CREATE TABLE paper_order_events (
    id        bigserial PRIMARY KEY,
    order_id  text NOT NULL REFERENCES paper_orders (id),
    ts        timestamptz NOT NULL,
    status    text NOT NULL,
    detail    jsonb NOT NULL DEFAULT '{}'
);

CREATE TABLE paper_fills (
    id                  text PRIMARY KEY,
    order_id            text NOT NULL REFERENCES paper_orders (id),
    account_id          text NOT NULL REFERENCES paper_accounts (id),
    slug                text NOT NULL,
    outcome             text NOT NULL,
    side                text NOT NULL,
    qty                 numeric(20, 8) NOT NULL CHECK (qty > 0),
    px                  numeric(12, 6) NOT NULL,
    instrument_px       numeric(12, 6) NOT NULL,
    liquidity           text NOT NULL CHECK (liquidity IN ('taker', 'maker')),
    fee                 numeric(20, 8) NOT NULL,
    fee_exact           numeric(24, 12) NOT NULL,
    fee_version         text NOT NULL,
    ts                  timestamptz NOT NULL,
    book_transact_time  timestamptz,
    spread_cost         numeric(20, 8) NOT NULL,
    slippage            numeric(20, 8) NOT NULL,
    profile             text NOT NULL
);
CREATE INDEX paper_fills_account_idx ON paper_fills (account_id, ts);

CREATE TABLE paper_settlements (
    id            bigserial PRIMARY KEY,
    account_id    text NOT NULL REFERENCES paper_accounts (id),
    slug          text NOT NULL,
    outcome       text NOT NULL,
    winning       boolean NOT NULL,
    qty           numeric(20, 8) NOT NULL,
    cost          numeric(20, 8) NOT NULL,
    payout        numeric(20, 8) NOT NULL,
    settled_at    timestamptz NOT NULL,
    detail        jsonb NOT NULL DEFAULT '{}',
    UNIQUE (account_id, slug, outcome)          -- a position settles once
);

CREATE TABLE risk_decisions (
    id               bigserial PRIMARY KEY,
    account_id       text NOT NULL REFERENCES paper_accounts (id),
    ts               timestamptz NOT NULL,
    client_order_id  text NOT NULL,
    slug             text NOT NULL,
    approved         boolean NOT NULL,
    reasons          jsonb NOT NULL,
    details          jsonb NOT NULL,
    intent           jsonb NOT NULL
);
CREATE INDEX risk_decisions_ts_idx ON risk_decisions (account_id, ts);

-- Persistent trading halts. Current state = latest row per (account, kind).
CREATE TABLE trading_halts (
    id          bigserial PRIMARY KEY,
    account_id  text NOT NULL REFERENCES paper_accounts (id),
    ts          timestamptz NOT NULL,
    kind        text NOT NULL CHECK (kind IN ('KILL_SWITCH', 'DAILY_LOSS', 'COOLDOWN')),
    active      boolean NOT NULL,
    until_ts    timestamptz,
    reason      text NOT NULL,
    trading_day date
);

CREATE TABLE paper_equity_days (
    account_id    text NOT NULL REFERENCES paper_accounts (id),
    trading_day   date NOT NULL,
    start_equity  numeric(20, 8) NOT NULL,
    recorded_at   timestamptz NOT NULL,
    PRIMARY KEY (account_id, trading_day)
);
