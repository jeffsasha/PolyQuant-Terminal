-- External spot (Strategy A feature). One row per source-second: last/first/high/low trade price, count, volume.
-- Seconds without trades have no row (consumers forward-fill). Kraken is a BRTI constituent exchange.
CREATE TABLE external_spot (
    source     text NOT NULL,
    ts         timestamptz NOT NULL,     -- start of the trade second (trade timestamps, source time)
    last_px    numeric(20, 8) NOT NULL,
    first_px   numeric(20, 8) NOT NULL,
    high_px    numeric(20, 8) NOT NULL,
    low_px     numeric(20, 8) NOT NULL,
    n_trades   integer NOT NULL,
    volume     numeric(24, 10) NOT NULL,
    recv_at    timestamptz NOT NULL,     -- when we received the second's last trade (live) or fetched it (backfill)
    PRIMARY KEY (source, ts)
);
