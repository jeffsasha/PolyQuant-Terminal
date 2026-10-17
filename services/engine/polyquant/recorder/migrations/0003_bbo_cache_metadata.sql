-- Live finding: REST /bbo is CDN-cached (max-age=30). Record when the body was produced and the cache state so
-- recorded REST quotes can be aligned in time and never mistaken for fresh data.
ALTER TABLE bbo_snapshots
    ADD COLUMN data_as_of   timestamptz,
    ADD COLUMN cache_status text,
    ADD COLUMN cache_age_s  integer;
