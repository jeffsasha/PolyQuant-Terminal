# Production API Availability — Observed Results

Checked October 16, 2026, approximately 13:14–13:20 America/Chicago (18:14–18:20 UTC). Environment: official **production** `https://gateway.polymarket.us`. Scope: unauthenticated public GET requests only; no order calls, portfolio calls, private-key access, or SDK installation.

## Decision

**BTC 15m and 1h Up/Down contracts and their public order books were observed in production.** This resolves the earlier documentation-only availability uncertainty. It does not establish continuously fresh execution data, authenticated streaming access, or readiness for reference-dependent paper strategies.

The read-only availability investigation is complete for this snapshot. The full integration readiness gate is **NOT PASSED**: the reference reconstruction check failed, public REST responses showed caching beyond the approved freshness ceiling, and authenticated streaming remains NOT TESTED at the owner's request.

## Capability matrix

| Capability | Observed result | Evidence / consequence |
|---|---|---|
| Production gateway | PASS | TLS-verified HTTP 200 JSON from public listing, contract detail, books and index routes |
| Crypto discovery | PASS for snapshot | Completed `closed=false&categories=crypto&includeHidden=true` scan: 1,067 unique markets plus empty terminal page; 12 requests |
| BTC 15m contract | PASS availability | ID `1483123`, typed BTC/UP_DOWN/15m/BRTI, 18:15–18:30 UTC, published threshold $81,221.17, OPEN |
| BTC 1h contract | PASS availability | ID `1467903`, typed BTC/UP_DOWN/1h/BRTI, 18:00–19:00 UTC, published threshold $81,088.94, OPEN |
| 15m book | PASS availability; freshness FAIL in sampled reads | HTTP 200, OPEN, nonempty bids/offers; initial source age 24.45s; follow-up response also cached |
| 1h book | PASS availability; continuous freshness UNPROVEN | HTTP 200, OPEN, nonempty bids/offers; initial sample source age 0.72s; later response cached approximately 28s |
| 15m BBO | INTERMITTENT / cached error | Initial HTTP 404 with Age 282; subsequent GET requesting no-cache returned 200; a single 404 did not establish absence |
| 1h BBO | PASS availability; freshness limited | HTTP 200; cached responses observed; BBO payload lacks a book transactTime field |
| Official BTC index history | PASS endpoint availability | HTTP 200, BTC/USD series and requested second-level timestamps returned; coverage/quality validation remains separate |
| Reference threshold reconstruction | FAIL | Five sampled published thresholds did not match documented 60-second averages; both candidate boundary conventions failed for the two current contracts |
| Historical typed contracts | PASS examples only | Historical detail/listing responses include both cadences. Broad history scans were capped; not a complete inventory or historical L2 dataset |
| Automated rollover | NOT TESTED | One active market per cadence was observed; observing consecutive live boundaries remains required |
| Authenticated market stream | NOT TESTED | Owner will configure local backend `.env` later; no credentials were accessed |
| Paper/live order execution | NOT RUN | No application execution engine exists; zero real or simulated orders submitted by these probes |

## Actual production instruments

These routing slugs came from typed production discovery, not a clock-generated naming assumption:

| Cadence | Market ID | Discovered routing slug | Window in Chicago time |
|---|---|---|---|
| 15m | 1483123 | `cpc-btc-updown-15m-2026-10-16-1815z` | October 16, 13:15–13:30 CDT |
| 1h | 1467903 | `cpc-btc-updown-1h-2026-10-16-1800z` | October 16, 13:00–14:00 CDT |

Availability and status apply to the observation time. These contracts will expire; later runs must rediscover eligible instruments. Listing terms and details agreed on typed family, BTC asset, BRTI index, exact duration, window, and published threshold. Data availability alone is not order entitlement.

Initial book sample: 15m had 39 bid and 37 offer levels, with best bid/ask 0.6100/0.6200; 1h had 39/24 levels, with best bid/ask 0.7200/0.7300. These are historical observations, not current quotes or trade recommendations.

## Discovery and caching lessons

The first general `closed=false` listing scan reached its 2,000-record cap without a typed target. That scan was explicitly incomplete and did not justify an absence conclusion. A focused crypto scan with hidden listings enabled found both targets and reached an empty terminal page. Category filtering was checked against returned categories; identities were checked for duplicates. Offset pagination is not a transactional exchange snapshot, so this is an observed inventory, not a completeness guarantee across concurrent listing changes.

Use typed terms, correct routing identifiers, and explicit listing options in the adapter. Public event URLs are not necessarily market routing slugs: the two previously published example event slugs returned 404 as market-detail identifiers, while their actual `cpc-` market identifiers returned 200. This is historical routing evidence only; production code must use discovered identifiers.

REST book/BBO responses included `Cache-Control: public, max-age=30` and nonzero Age headers. Requesting `Cache-Control: no-cache` did not establish uncached responses. The first 15m BBO response was a cached 404 and later succeeded. Record HTTP cache age, source time, and receipt time independently. Do not treat HTTP 200 or an OPEN flag as a fresh executable book. The approved two-second book ceiling remains unchanged; these samples cannot authorize automation.

## Reference investigation

See [Reference discrepancy](REFERENCE_DATA_DISCREPANCY.md) for five exact comparisons, fresh metadata rechecks, and both averaging boundaries. Keep `REFERENCE_RECONCILIATION_FAILED` visible and reference-dependent strategy admission disabled. Do not replace the published threshold with a computed value, adjust the index by an unexplained offset, or substitute external spot.

## Network environment and reproducibility

The initial sandbox request failed DNS resolution. The first approved network retry reached TLS validation but Python's default CA file was absent. Using the existing `/etc/ssl/cert.pem` system bundle allowed verified TLS. No certificate verification was disabled and no machine trust settings were modified.

From the design-package root, on this Mac:

```bash
python3 -m unittest discover -s tools -p 'test_verify_production.py' -v
SSL_CERT_FILE=/etc/ssl/cert.pem python3 tools/verify_production.py --output verification/production
```

The second command requires ordinary public network access. Other machines should use their valid system CA configuration, not blindly assume this Mac path exists. The script uses a production host/path allowlist, GET-only requests, redirect rejection, bounded pages/time/response sizes, and no credential configuration. It saves raw response bodies, selected safe headers, SHA-256 hashes, request timing, and summaries. A page cap, schema error, or transport failure returns a nonzero diagnostic exit status, not an unavailable-market verdict.

Eleven deterministic diagnostic checks passed after observed red→green runs. They cover route restrictions, typed classification, missing thresholds, time boundaries, future/stale timestamps, malformed responses, pagination limits/duplicates, redirects, and focused listing parameters. These are probe tests, not trading application tests.

## Saved evidence

Paths below are relative to this document:

- [Initial sandbox DNS failure](../verification/production/20261016T181327.884297Z/summary.json)
- [Initial TLS trust-store failure](../verification/production/20261016T181339.699540Z/summary.json)
- [Capped general listing scan](../verification/production/20261016T181407.921407Z/summary.json)
- [Focused crypto inventory and static historical example checks](../verification/production/20261016T181526.469321Z-crypto-focus/summary.json)
- [Reproducible focused probe: contracts, BBO, books, and index](../verification/production/20261016T181707.484046Z/summary.json)
- [Five reference comparisons and BBO/book follow-up](../verification/production/20261016T181849.863538Z-reference-checks/summary.json)
- [Fresh details and alternate averaging-boundary checks](../verification/production/20261016T181958.633453Z-boundary-recheck/summary.json)

Each run also contains `requests.json` and numbered raw `.body` files. Do not interpret capped history coverage as a full archive. The complete focused scan and subsequent candidate reads are the evidence for availability, not the earlier public-page examples or stale schema rollout statement.

## Next integration work

After detailed-plan review, build the read-only adapter and recorder while preserving the failed reference gate. When the owner configures the local backend `.env`, test the authenticated market-data stream, its refresh semantics and freshness, reconnect/reconciliation, actual rollovers, and final settlement. Investigate index-history versus published-threshold semantics through official source/schema/version evidence and further reproducible comparisons. Only a resolved discrepancy and valid required inputs may enable the probability baseline.
