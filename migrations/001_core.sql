CREATE TABLE IF NOT EXISTS accounts (
 id text PRIMARY KEY, cash numeric(24,8) NOT NULL DEFAULT 1000 CHECK(cash>=0),
 reserved numeric(24,8) NOT NULL DEFAULT 0 CHECK(reserved>=0 AND reserved<=cash),
 day_start numeric(24,8) NOT NULL DEFAULT 1000, day_id text NOT NULL,
 halts jsonb NOT NULL DEFAULT '[]', consecutive_losses integer NOT NULL DEFAULT 0,
 cooldown_until timestamptz, config jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS orders (
 id text PRIMARY KEY, account_id text NOT NULL REFERENCES accounts(id), market_id text NOT NULL,
 side text NOT NULL, qty numeric(24,8) NOT NULL CHECK(qty>0), limit_price numeric(24,8) NOT NULL CHECK(limit_price>0 AND limit_price<1),
 reserved numeric(24,8) NOT NULL DEFAULT 0, status text NOT NULL, reason text NOT NULL DEFAULT '',
 strategy text NOT NULL, scenario text NOT NULL, probability numeric(24,8),
 created_at timestamptz NOT NULL DEFAULT now(), arrival_at timestamptz NOT NULL DEFAULT now(),
 book_version text NOT NULL DEFAULT '', UNIQUE(account_id,market_id,strategy)
);
CREATE TABLE IF NOT EXISTS fills (
 id text PRIMARY KEY, order_id text NOT NULL REFERENCES orders(id), price numeric(24,8) NOT NULL,
 qty numeric(24,8) NOT NULL, fee numeric(24,8) NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS positions (
 id bigserial PRIMARY KEY, account_id text NOT NULL REFERENCES accounts(id), market_id text NOT NULL,
 direction text NOT NULL, qty numeric(24,8) NOT NULL, cost numeric(24,8) NOT NULL, fees numeric(24,8) NOT NULL DEFAULT 0,
 status text NOT NULL DEFAULT 'OPEN', payout numeric(24,8) NOT NULL DEFAULT 0,
 UNIQUE(account_id,market_id,direction)
);
CREATE TABLE IF NOT EXISTS postings (
 id bigserial PRIMARY KEY, group_id text NOT NULL, account_id text NOT NULL,
 bucket text NOT NULL, amount numeric(24,8) NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS decisions (
 id text PRIMARY KEY, account_id text NOT NULL, market_id text, strategy text NOT NULL,
 payload jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS audit (
 id bigserial PRIMARY KEY, action text NOT NULL, account_id text, payload jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS sessions (hash text PRIMARY KEY, csrf text NOT NULL, expires_at timestamptz NOT NULL);
CREATE TABLE IF NOT EXISTS datasets (
 id text PRIMARY KEY, filename text NOT NULL, sha256 text NOT NULL, bytes bigint NOT NULL,
 events bigint NOT NULL, first_at timestamptz NOT NULL, last_at timestamptz NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS settlements (id text PRIMARY KEY, market_id text NOT NULL, outcome text NOT NULL, payload jsonb NOT NULL, created_at timestamptz DEFAULT now());
CREATE TABLE IF NOT EXISTS equity_snapshots (id bigserial PRIMARY KEY,account_id text NOT NULL,equity numeric(24,8) NOT NULL,created_at timestamptz NOT NULL DEFAULT now());
ALTER TABLE orders ADD COLUMN IF NOT EXISTS horizon text;
ALTER TABLE positions ADD COLUMN IF NOT EXISTS horizon text;
ALTER TABLE positions ADD COLUMN IF NOT EXISTS settled_at timestamptz;
CREATE TABLE IF NOT EXISTS instrument_versions(id text NOT NULL,version text NOT NULL,raw jsonb NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),PRIMARY KEY(id,version));
CREATE INDEX IF NOT EXISTS decisions_recent ON decisions(created_at DESC);
CREATE INDEX IF NOT EXISTS audit_recent ON audit(created_at DESC);
CREATE OR REPLACE FUNCTION forbid_audit_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Append-only financial audit'; END $$;
DROP TRIGGER IF EXISTS audit_immutable ON audit;
CREATE TRIGGER audit_immutable BEFORE UPDATE OR DELETE ON audit FOR EACH ROW EXECUTE FUNCTION forbid_audit_mutation();
DROP TRIGGER IF EXISTS postings_immutable ON postings;
CREATE TRIGGER postings_immutable BEFORE UPDATE OR DELETE ON postings FOR EACH ROW EXECUTE FUNCTION forbid_audit_mutation();
