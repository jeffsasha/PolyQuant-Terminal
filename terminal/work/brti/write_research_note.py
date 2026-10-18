import json
from pathlib import Path
root=Path('.')
r1=Path('work/brti/20261016T211143Z-followup')
r2=Path('work/brti/20261016T211320Z-followup')
markets={}
for run in (r1,r2):
    for m in json.loads((run/'summary.json').read_text())['markets']:
        if 'terms' in m:markets[m['id']]=(m,run)
order=['1483123','1000588','1000678','1244140','1466843','1467903','1471756','1000736']

def table(boundary):
    lines=['| Cadence / ID | Boundary UTC | Published USD | Mean `[T−60,T)` | Mean `[T−59,T]` | 1S close `T−1` | 1S close `T` |','|---|---|---:|---:|---:|---:|---:|']
    for ident in order:
        m,_=markets[ident];t=m['terms'];c=m[boundary+'_check'];b=t['windowStart' if boundary=='open' else 'windowEnd'];v=t['priceToBeat' if boundary=='open' else 'settlementPrice']['value']
        lines.append(f"| {t['horizon']} / {ident} | {b.replace('T',' ').replace(':00Z','Z')} | {v} | {c['mean_pre']} | {c['mean_inclusive']} | {c['last_pre']} | {c['at_boundary']} |")
    return '\n'.join(lines)

s='''# BRTI follow-up research

Observed October 16, 2026, 21:11–21:15 UTC. **Reference reconstruction remains unresolved; do not enable reference-dependent strategies.** The strongest new evidence is an inconsistency between the `1S` and coarser history buckets. The `1S` route appears to return an already aggregated statistic. That is a supported hypothesis, not an established replacement specification.

## Scope and reproducibility

Only official public documentation and unauthenticated production GET requests were used. No `.env`, `.local`, credentials, private endpoints, runtime modules, or account state were accessed; no real or paper orders were submitted. Files changed by this investigation are this note and diagnostic/evidence files under `work/brti/`.

[First run](../work/brti/20261016T211143Z-followup/summary.json) rechecks the five earlier identities, the official October 6 worked example, their resolved values, and five exact earlier history windows. [Hourly follow-up](../work/brti/20261016T211320Z-followup/summary.json) adds three resolved BTC hourly markets through bounded public discovery. Its scan stopped after four pages when three targets were found; it is not a complete exchange inventory. [Bucket comparison](../work/brti/20261016T211451Z-followup/summary.json) compares the same three minutes at 1S, 5S, and 1M. Each directory holds raw `.body` responses and `requests.json` with exact URLs, UTC request/receipt times, selected safe headers, byte counts, and SHA-256 hashes. The [source snapshots](../work/brti/20261016T211414Z-sources/requests.json) preserve the official documentation, OpenAPI schema, CF methodology, and rulebook used here.

The diagnostic scripts are bounded GET collectors, separate from application code. Earlier trailing-slash discovery requests rejected redirects; the retained empty runs are transport/discovery evidence, not negative availability findings. The corrected canonical `/v1/markets` route succeeded.

## What official sources say

**Fact — contract statistic.** The current [Crypto Schema](https://docs.polymarket.us/trader-guide/crypto-schema) and [Crypto FAQs](https://docs.polymarket.us/faqs/crypto-faqs) specify an arithmetic mean of 60 per-second BRTI values in `[T−60s,T)`, rounded to two decimals, computed at both window open and close. Both 15m and 1h use that rule. A tie settles Up. The actual detail descriptions returned for sampled contracts also say a simple average of 60 prices in the last minute before each boundary. No reviewed official source authorizes replacing that contract statistic with an instantaneous index or a duration-weighted statistic. One-Touch's trimmed mean is a different family.

**Fact — anchor lifecycle.** [Retail market fields](https://docs.polymarket.us/api-reference/market/overview) define `windowStart` as the opening boundary and `windowEnd` as the settlement boundary. `priceToBeat` is stamped shortly after opening; `settlementPrice` is the reference BTC/USD value stamped at resolution. These are decimal USD Amount objects. `endDate` is not the settlement boundary.

**Fact — advertised reconstruction.** The [Asset Prices overview](https://docs.polymarket.us/api-reference/asset-prices/overview) explicitly tells clients to average 60 `1S.close` values from `T−60` through `T−1`. Its October 6 example claims 85501.45 for that mean and 85501.37 for the one-second-shifted mean. This procedure was followed exactly; the new experiment tests the example itself below.

**Fact — bucket semantics.** The [official OpenAPI schema](https://docs.polymarket.us/api-reference/oapi-schemas/asset-prices-schema.json), successfully saved as source `006.body`, says `timestamp` is bucket start, `close` is the final price in a bucket, and `tickCount` counts index ticks in that bucket. Zero marks carry-forward gap filling. It does not describe the 1S field as a rolling mean, expose a raw-versus-smoothed selector, or provide amendment/version metadata. It describes alignment of historical `to` bounds; clients must inspect actual effective bounds and timestamps rather than assume a convention. The inspected 1S responses for `to=T−1` actually end at that second, and `[T−60,T]` requests return 61 distinct seconds.

**Fact — remaining documentation conflict.** The September 21 [changelog](https://docs.polymarket.us/changelog) still describes `[T−59,T]`. Current schema/FAQ/overview instead say `[T−60,T)`. Testing both 60-close means does not reconcile any of the eight markets in this note.

**Fact — BRTI itself.** CF Benchmarks' [Real Time Indices methodology v17.0, September 21, 2026](https://docs.cfbenchmarks.com/CME%20CF%20Real%20Time%20Indices%20Methodology.pdf), §6.2/§7, describes BRTI as an instantaneous order-book-derived index, standard top-of-second publication, optional 200ms publication, and $0.01 dissemination precision. This describes the input benchmark, not Polymarket's additional 60-sample settlement statistic. It does not explain 60 index ticks inside each returned one-second candle.

## Numeric observations

All eight detailed markets were `MARKET_STATUS_RESOLVED` when checked. Every examined 1S opening/closing series had 61 consecutive positive-price timestamps over the requested `[T−60,T]` range. Every one-second candle had `tickCount=60` and `open=high=low=close`; none was a zero-tick carry-forward bucket. Means below use Decimal and cent rounding. All differences are larger than a rounding-mode ambiguity.

### Opening anchors

''' + table('open') + '''

### Closing anchors

''' + table('close') + '''

**Observed:** October anchors equal the final pre-boundary 1S close at `T−1`; September anchors equal the 1S close at `T`. That pattern applies to both open and close. Neither a global one-second shift nor a universal last-candle substitution is justified across these examples. The date association is not a proven rollout/version boundary.

The official October 6 example is especially useful: the published threshold is indeed 85501.45, but the actual 60-close arithmetic mean is **85501.73**, and its shifted mean is **85501.74**. The page's claimed mean values, 85501.45 and 85501.37, are instead exactly the returned 1S closes at `T−1` and `T`. This is a reproducible contradiction between the worked reconstruction example and the current production response, not evidence that the contract rule itself changed.

### Coarser buckets expose a different input series

For identical `from=T−60`, `to=T−1` queries:

| Opening boundary | 1S first / last close | 5S first open / last close | 1M open / close | Counts |
|---|---|---|---|---|
| Oct 6 19:00 UTC | 85500.56 / 85501.45 | 85501.26 / 85497.21 | 85501.26 / 85497.21 | 1S: 60 per candle; 5S: 5 per candle; 1M: 60 |
| Oct 16 18:00 UTC | 81081.15 / 81088.94 | 81055.86 / 81089.14 | 81055.86 / 81089.14 | same |
| Oct 16 18:15 UTC | 81182.88 / 81221.17 | 81228.64 / 81208.96 | 81228.64 / 81208.96 | same |

5S and 1M have nonflat OHLC. Their first/last prices agree with each other, and their tick counts fit aggregation of one publication per second. They disagree with the 1S prices. The 5S and 1M series' effective `to` is `T`, while their final bucket starts before `T`; the actual minute represented remains the preceding minute. The comparison uses actual bucket timestamps and widths, not merely the echoed `to` value.

**Inference — leading hypothesis:** the 1S path supplies an already computed rolling 60-observation statistic, while coarser buckets use individual BRTI observations. Averaging the 1S path again would then smooth twice, producing the mismatch. The unusual 60 tick count, flat OHLC, exact anchor matches, and failed official example support this hypothesis. Alternative explanations include a different feed or endpoint implementation defect. OHLC bars do not expose all 60 raw prices, so the hypothesis cannot be proven by averaging 5S closes; that would select only 12 observations.

### Revisions and caching

Re-fetching the exact five earlier 60-second history URLs at 21:11:47–21:11:48 UTC returned **identical parsed JSON** to the 18:18:49–18:18:51 UTC evidence. Two raw hashes matched and three differed despite equal parsed content, consistent with JSON serialization ordering. There is no observed numeric revision across that interval. This does not prove that values were never revised before the original capture, or that later responses are immutable.

History responses showed `cf-cache-status: DYNAMIC` and no recorded Age header. That is not proof that upstream history computation is uncached. Binary settlement responses showed `Cache-Control: public, max-age=30`; requesting no-cache does not guarantee bypassing all caches. CF's [latest-values API](https://docs.cfbenchmarks.com/api/rest/latest-values/) exposes an optional `amendTime`, demonstrating an amendment concept in its data model; Polymarket's inspected history does not pass that metadata through. CF's [historical-values API](https://docs.cfbenchmarks.com/api/rest/historical-values/) requires index/history authorization and may delay recent values up to 15 minutes. No authenticated CF access was attempted. No source establishes that amendments caused these mismatches.

## Authoritative binary outcome is independently available

The [Markets overview's Settlement section](https://docs.polymarket.us/api-reference/market/overview#settlement) documents `/v1/markets/{slug}/settlement` as the contract payoff, typically 0.00 or 1.00. That is distinct from the BTC reference price in `assetPriceTerms.settlementPrice`.

Successful production response shape:

```json
{"slug":"cpc-btc-updown-15m-2026-10-16-1815z","settlement":1}
```

`settlement` is a JSON number and there is **no currency field** in that response. Dollar payoff semantics come from the contract/documentation. The matching detail is nested under `market`, with `market.status="MARKET_STATUS_RESOLVED"`, `market.ep3Status="EXPIRED"`, `market.closed=true`, and typed Amount fields under `market.assetPriceTerms`. Some resolved samples still have `market.active=true`; `active` alone cannot establish finality or order eligibility. Outcome display prices are not an authoritative substitute for the settlement endpoint.

| Cadence / ID | Official binary payoff | Detail body | Settlement body |
|---|---:|---|---|
| 15m / 1483123 | 1 | first run `001.body` | first run `004.body` |
| 15m / 1000588 | 0 | first run `005.body` | first run `008.body` |
| 15m / 1000678 | 1 | first run `009.body` | first run `012.body` |
| 1h / 1466843 | 0 | hourly run `005.body` | hourly run `008.body` |
| 1h / 1467903 | 0 | hourly run `009.body` | hourly run `012.body` |
| 1h / 1471756 | 1 | hourly run `013.body` | hourly run `016.body` |

Thus three resolved contracts per cadence have direct, matching-slug official binary payoff responses, independently of any reconstruction model. Each agrees with the comparison of its stamped open/close values, although that comparison is not a replacement for the endpoint.

An important counterexample is hourly `1000736`: detail says RESOLVED and publishes a reference close, but the binary settlement route returned HTTP 404 with `{"code":5,"message":"Settlement not found for market ...","details":[]}` (first run `020.body`). Keep outcome reconciliation pending on this response; do not infer zero, absence of a contract, or final payout from the error.

**Recommended ingestion rule:** require a matching detail identity with resolved status plus HTTP 200, matching-slug, explicitly parsed valid binary payout before normal binary paper settlement. Preserve the raw outcome evidence and recheck corrections. Invalid, missing, fractional, or contradictory responses require a separate unresolved/exception path. Never use the reference model or unresolved history mean to manufacture a payout.

The official [Market Resolution](https://docs.polymarket.us/learn/markets/market-resolution) and [Market Settlement](https://docs.polymarket.us/learn/markets/contract-settlement) pages describe finality subject to the rulebook. The [September 30 rulebook](https://polymarketexchange.com/files/legal/latest/rulebook), Rule 10.4, permits outcome review and reversal for obvious error prior to settlement. Public responses inspected here contain no explicit correction version or independent clearing-finality timestamp. Treat captured payout as an authoritative observed exchange result, retain subsequent corrections, and do not claim a stronger API immutability guarantee. A raw-body hash is provenance, not a semantic revision number: equal normalized payout/status must not create a second cash adjustment merely because JSON key order changed.

## Resolution assessment and exact remaining proof

**What is resolved:** the earlier procedure was implemented as documented; the difference is not cent rounding, missing seconds, timezone conversion, zero-tick filling, or solely the old one-second boundary convention in these samples. Public resolved-market binary payout is available for at least three markets per cadence and can anchor discretionary paper settlement independently.

**What remains unresolved:** the authoritative meaning and provenance of `ASSET_PRICE_BUCKET_1S` values, whether they are a rolling statistic, and why September and October anchors use different history timestamps. The evidence narrows the discrepancy to documented reconstruction versus endpoint semantics, with double averaging the leading explanation. It does not establish an exchange defect or authorize changing contract rules.

To pass the reference gate for **each cadence**, retain at least three resolved 15m and three resolved 1h examples and obtain all of the following:

1. Official clarification or implementation/version evidence identifying the 1S statistic, source, tickCount meaning, exact window, timestamp label, and effective-date behavior. Include the documented October 6 counterexample and the cross-bucket responses in the question/evidence packet.
2. The actual 60 independent standard per-second BRTI observations at both start and end, or a documented authoritative equivalent with provable computation lineage. Reproduce both stamped USD anchors to cents. A coincidental endpoint close match is insufficient; the current six-plus examples establish endpoint relationships, not this raw-input proof.
3. Explanation of the September `T` versus October `T−1` mapping, including compute-for time versus publication/receipt time. Confirm the applicable rounding tie rule and how missing/amended observations are handled.
4. Official expectations for historical restatement and cache/version behavior; capture before/after boundary and later rechecks with hashes and normalized values. Explain whether exchange anchors remain fixed after reference-history amendments.
5. Keep final binary outcome checks separate: matching resolved status and payoff must remain available; preserve and handle delayed/404/corrected results without deriving them from a model.

Until those points are established, keep model/reference readiness false and the published threshold visibly labeled as the exchange's official stamped value. Do not silently replace it, average already smoothed values, invent an offset, or mark the reference gate passed based on these anchor matches.
'''
(root/'docs/BRTI_FOLLOWUP_RESEARCH.md').write_text(s)
print('WROTE docs/BRTI_FOLLOWUP_RESEARCH.md',len(s.split()),'words')
