# Reference Reconstruction Discrepancy

Observed October 16, 2026. Status: **UNRESOLVED; reference-dependent paper trading disabled.** This is an integration finding, not an established diagnosis of an exchange defect.

## Method

Read a discovered contract's typed `assetPriceTerms`, including BRTI index, `windowStart`, and published USD `priceToBeat`. Query the official production asset-price history for BTC with `ASSET_PRICE_BUCKET_1S`, from `T−60` through `T−1`. Require 60 consecutive second timestamps and positive tickCount, then average the 60 Decimal close values and round to two decimals.

This is the reconstruction procedure in the current [official Asset Prices overview](https://docs.polymarket.us/api-reference/asset-prices/overview). An older [changelog entry](https://docs.polymarket.us/changelog) gives a one-second-shifted interval. Both interpretations were checked for the two current markets. Rounding to cents cannot account for differences of several USD.

## Five sampled starting thresholds

| Market ID | Cadence | Window start UTC | Published USD threshold | Reconstructed `[T−60,T)` | Difference: reconstructed minus published |
|---|---|---|---:|---:|---:|
| 1483123 | 15m | 2026-10-16 18:15 | 81221.17 | 81212.35 | -8.82 |
| 1000588 | 15m | 2026-09-22 15:15 | 86291.74 | 86268.28 | -23.46 |
| 1000678 | 15m | 2026-09-23 02:15 | 86354.14 | 86337.06 | -17.08 |
| 1467903 | 1h | 2026-10-16 18:00 | 81088.94 | 81081.86 | -7.08 |
| 1000736 | 1h | 2026-09-22 15:00 | 86222.37 | 86210.20 | -12.17 |

Each request returned 60 correctly bounded timestamps with positive tickCount. This verifies the returned structure, not that historical data exactly represents the exchange's original settlement input.

## Fresh metadata and alternate boundary

The current contracts were fetched again through their production detail routes, requesting no-cache. Published thresholds were unchanged. Neither documented boundary reconciled:

| Cadence | Published | `[T−60,T)` mean | `[T−59,T]` mean |
|---|---:|---:|---:|
| 15m | 81221.17 | 81212.35 | 81212.99 |
| 1h | 81088.94 | 81081.86 | 81082.00 |

The one-second documentation discrepancy therefore does not explain these sampled mismatches by itself. Query timestamps were derived from timezone-aware windowStart values, and the response timestamps matched the requested seconds. The root cause remains open: history revisions, aggregation/publication semantics, endpoint behavior, source differences, or documentation/version issues need evidence rather than a guessed correction.

## Required behavior and resolution gate

- Keep the published threshold labeled as the official market threshold; never silently overwrite it with the reconstructed average.
- Show index-history validation as failed, distinct from endpoint reachability and threshold availability.
- Reject reference-dependent automatic and manual strategy entries while the required reference relationship is unresolved. A recorder/diagnostic terminal may continue without trading.
- Preserve raw responses, hashes, retrieval times, exact query bounds, and contract terms. Do not alter fixture expectations to make production data appear reconciled.
- Before activation, establish the supported reconstruction semantics from official evidence and reproduce at least three resolved markets per cadence to the specified precision, or explicitly revise the design with owner review if the reference feed cannot meet that requirement.

Evidence: [original five checks](../verification/production/20261016T181849.863538Z-reference-checks/summary.json), [boundary and fresh-detail checks](../verification/production/20261016T181958.633453Z-boundary-recheck/summary.json). The relevant raw responses and request logs sit beside those summaries.
