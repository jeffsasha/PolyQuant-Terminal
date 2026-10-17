> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.us/llms.txt
> Use this file to discover all available pages before exploring further.

# Crypto Schema

> Instrument fields for safely identifying crypto price markets

This page documents the strongly-typed fields on the instrument that identify a crypto price market (product code `cpc`, "Cryptocurrency Contracts"). **Do not parse the instrument symbol or slug** — symbol formats are not part of the public contract and may change. Identify markets using the fields below.

Every crypto price market settles against a published reference index, not a spot venue. Today that index is CF Benchmarks' Bitcoin Real-Time Index (`BRTI`). The Retail API exposes the same terms as the typed `assetPriceTerms` object; see [Crypto Price Market Fields](/api-reference/market/overview#crypto-price-market-fields).

<Note>
  The automated market families in Section 2 are listed in the preprod environment and roll out to production as announced in the [changelog](/changelog). Production currently carries the hand-listed Bitcoin markets described in Section 4.
</Note>

## Section 1: Common Identifying Fields

The following fields appear on every automated crypto instrument. Together they identify the asset, the reference index, the market type, the time window, and the threshold of a contract.

### Field Reference

| Field | Location | Type | Description |
| - | - | - | - |
| `event_category` | `metadata` | String | Always `CRY`. |
| `event_subcategory` | `metadata` | String | The asset symbol, e.g. `BTC`. |
| `instrument_product` | `metadata` | String | Always `cpc`. |
| `instrument_product_series` | `metadata` | String | Always `cpc-crypto`. Use `event_series` for the cadence. |
| `clearing_sym` | `metadata` | String | `CPC-<SYMBOL>`, e.g. `CPC-BTC`. |
| `event_series` | `metadata` | String | Series slug encoding asset, family and cadence. See the series table below. |
| `event_id` | `metadata` | String | Slug of the event that groups every leg of one ladder or one up/down window. No contract prefix. |
| `product_id` / `event_product_id` | `metadata` | String | `cpc-<event_id>`. Groups the legs of one ladder. |
| `event_start_time` | `metadata` | Timestamp (UTC) | Up/down: the window open. One-touch: the start of the measurement window. Above/below and price range: the listing time. |
| `crypto_asset_slug` | `metadata` | String | Asset slug used by the Retail asset-price endpoints, e.g. `btc`. |
| `crypto_index_symbol` | `metadata` | String | Reference index the market settles on, e.g. `BRTI`. |
| `crypto_market_type` | `metadata` | Enum | The market family. **Map on this field.** See the enum below. |
| `crypto_horizon` | `metadata` | Enum | The cadence or window length. See the enum below. |
| `outcome_strike` | `metadata` | String (numeric) | Above/below: the strike. One-touch: the target. Price range: the bucket's defining floor. Up/down: `"0.0"`. |
| `interval_start` | `metadata` | String (unix seconds) | Start of the measurement window. Present on up/down and one-touch only. |
| `interval_end` | `metadata` | String (unix seconds) | End of the measurement window, i.e. the settlement instant. Present on every family. |
| `price_to_beat` | `metadata` | String (decimal) | Up/down only. The open reference price. Absent until stamped a few seconds after the window opens. |
| `crypto_range_kind` | `metadata` | Enum | Price range only: `interior`, `below` (bottom tail) or `above` (top tail). |
| `crypto_range_lower` / `crypto_range_upper` | `metadata` | String (decimal) | Price range only. Inclusive bounds with two decimals. A tail omits its open side. |
| `crypto_hit_direction` | `metadata` | Enum | One-touch only: `high` (touch from below) or `low` (touch from above). |
| `crypto_hit_method` | `metadata` | String | One-touch only: `trimmed_mean_60s_20`, the settlement statistic. |
| `crypto_settlement_price` | `metadata` | String (decimal) | The reference price the market settled on. Absent until resolution, and stays absent on a One-Touch market that resolves No: no price was touched, so there is none to record. Read the instrument state for completion, not this field. |

The instrument also carries display fields you can ignore for mapping: `market_title`, `market_subtitle`, `event_sort_type`, `market_sort_order`, `market_color`, `market_dark_color`, `event_image`, `event_image_display_type`, `event_tags`, and the CFTC reporting fields `cftc_instrument_id`, `cftc_product_desc`, `cftc_binary_option_strike_price_alias`. Operational fields (`requires_manual_settlement`, `manual_settlement_*`, `expected_settlement_side`, `settlement_*`) can appear while the exchange is settling an instrument and must be ignored.

### `crypto_market_type` Enum

| Value | Retail `assetPriceTerms.marketType` | Structure |
| - | - | - |
| `updown` | `ASSET_PRICE_MARKET_TYPE_UP_DOWN` | One binary instrument per window. Long side pays when the close is at or above the open. |
| `strike` | `ASSET_PRICE_MARKET_TYPE_ABOVE_BELOW` | Ladder of independent binary instruments, one per strike. Long side pays when the settlement value is at or above the strike. |
| `range` | `ASSET_PRICE_MARKET_TYPE_RANGE` | Ladder of mutually exclusive buckets that tile the price line. Exactly one leg pays. |
| `hit` | `ASSET_PRICE_MARKET_TYPE_ONE_TOUCH` | Ladder of independent binary instruments, one per target. Long side pays if the target is touched at any point in the window. |

Treat an unknown value as a newer family: render the fields that are present and watch the changelog.

### `crypto_horizon` Enum

| Value | Family | Meaning |
| - | - | - |
| `5m`, `15m`, `1h`, `4h` | `updown` | Window length. `15m` and `1h` are listed; `5m` and `4h` follow the same pattern and can appear in preprod ahead of listing. |
| `hourly` | `strike`, `range` | Expires at the top of an hour. |
| `daily` | `strike`, `range` | Expires at 5:00 PM ET. |
| `weekly` | `strike`, `range` | Expires Friday 5:00 PM ET. |
| `monthly` | `hit` | Window runs from the first of the month to midnight ET at month end. |

### Series

`event_series` combines asset, family and cadence. Current values:

| Series | Family |
| - | - |
| `btc-updown-15m`, `btc-updown-1h` | Up/down. Further cadences follow the pattern `btc-updown-<horizon>` |
| `btc-strike-hourly`, `btc-strike-daily`, `btc-strike-weekly` | Above/below |
| `btc-range-hourly`, `btc-range-daily`, `btc-range-weekly` | Price range |
| `btc-hit-monthly` | One-touch |
| `btc` | Hand-listed markets (Section 4) |

### Event Attributes

`event_attributes` records the strike for the exchange's DCM record. `strike_unit` is `USD` and `strike_description` is the index symbol on every family except up/down, which uses `strike_value: "Up"` with `strike_unit: "string"`. Price range interior buckets record the exact bounds as `strike_value: "<lower>-<upper>"` with `evaluation_type: "=="`. Settlement never depends on these fields; the `crypto_*` metadata above is authoritative.

Every family resolves each instrument independently (`EVENT_OUTCOME_INDEPENDENT`) except price range, whose event is mutually exclusive (`EVENT_OUTCOME_MUTUALLY_EXCLUSIVE`) so that exactly one bucket settles Yes. See [Mutually Exclusive Collateral Return](/market-structure/mutually-exclusive-collateral-return) for the margin treatment.

***

## Section 2: Market Families

All families share the same contract attributes: tick size `0.01`, valid prices `0.01` to `0.99`, minimum order 0.01 contract, payout \$1.00 per contract, position accountability level 25,000 contracts, and a daily trade-day roll at 5:00 PM ET. Last trade is the settlement instant (`interval_end`); the instrument expires 30 minutes later, which leaves time for the exchange to resolve it. Source agency is CF Benchmarks.

### Up/Down

*Will the price close the window at or above its open?*

| Aspect | Detail |
| - | - |
| Open and close values | For each of the two instants `T`, the 60 per-second BRTI prices published in the sixty seconds before `T`, from `T − 60 s` up to but not including `T` (the interval `[T − 60 s, T)`), are collected and averaged, rounded to two decimals. |
| Settlement | Long side (Yes) pays when the close value is greater than or equal to the open value. A flat print settles Up. Otherwise the short side (No) pays. |
| Cadence | `15m` windows are listed about 12 hours ahead (roughly 48 open per asset). `1h` windows are listed about 24 hours ahead on the UTC hour grid. Windows that overlap a scheduled exchange maintenance are not listed. |
| Lifecycle | Created `PENDING`, opened for trading about 90 seconds before the window starts, last trade at the window close. `price_to_beat` is stamped a few seconds after the open; `crypto_settlement_price` at resolution. |
| Structure | One instrument per event. `outcome_strike` is `"0.0"`; both `interval_start` and `interval_end` are set. |

### Above/Below

*Will the price be at or above \$X at expiry?*

| Aspect | Detail |
| - | - |
| Settlement value | The 60 per-second BRTI prices published in the sixty seconds before expiry, from `T − 60 s` up to but not including the expiry instant (`[T − 60 s, T)`), averaged and rounded to two decimals. |
| Settlement | Long side pays when the settlement value is greater than or equal to the strike. A value exactly equal to the strike settles Yes. |
| Cadence | `hourly` ladders (\$100 steps) are listed about four hours ahead; no hourly ladder expires at 5:00 PM ET. `daily` ladders (\$500 steps) expire at 5:00 PM ET and are listed about 25 hours ahead; there is no daily ladder on Fridays. `weekly` ladders (\$500 steps) expire Friday 5:00 PM ET and are listed on Monday at midnight ET. |
| Lifecycle | Tradeable from listing. Last trade at expiry. |
| Structure | One event per expiry with one instrument per strike; ladder depth scales with implied volatility (typically 30 to 100 legs). `outcome_strike` is the strike; only `interval_end` is set. |

### Price Range

*Will the price be between \$A and \$B at expiry?*

| Aspect | Detail |
| - | - |
| Settlement value | Same as above/below: the last-minute average before expiry, rounded to two decimals. |
| Settlement | Buckets are inclusive on both bounds and tile the price line: each interior bucket spans `[floor, next floor − $0.01]`, the bottom tail is "or below", the top tail is "or above". Exactly one bucket settles Yes. |
| Cadence | Same expiries and listing times as the above/below ladder of the same horizon; the bucket width is that ladder's strike spacing. |
| Lifecycle | Tradeable from listing. Last trade at expiry. |
| Structure | One mutually exclusive event per expiry. `crypto_range_kind` says which side is open-ended; `crypto_range_lower` and `crypto_range_upper` carry the bounds. `outcome_strike` holds the bucket's defining floor for sorting only. |

### One-Touch

*Will the price reach (or dip to) \$X before the end of the month?*

| Aspect | Detail |
| - | - |
| Settlement statistic | A rolling 60-second 20% trimmed mean of BRTI: at each evaluation instant the 60 prices published in the sixty seconds ending at and including it are collected, the highest 20% and lowest 20% are removed, and the rest are averaged, rounded to two decimals. Evaluated continuously. |
| Settlement | Long side pays if the trimmed mean is at or above the target (`crypto_hit_direction: "high"`) or at or below it (`"low"`) at any point in the window. The market may settle early at that moment. Otherwise it settles No after the window closes, once the index data for the window is complete. |
| Cadence | `monthly`. The window opens when the ladder is listed at the start of the month and closes at midnight ET on the last day. "Reaches" and "Dips to" targets are separate events. |
| Lifecycle | Tradeable from listing. Last trade at the window close unless the market settles early. |
| Structure | One event per direction per month, one instrument per target (\$2,500 steps, up to 16 targets). `outcome_strike` is the target; `interval_start` and `interval_end` are set. |

***

## Section 3: Identifying Markets

Use this table to identify a market from instrument metadata. **Match on `crypto_market_type`**, then read the window from `interval_start` / `interval_end` and the threshold from `outcome_strike` or the range bounds.

| To identify... | Fields |
| - | - |
| **Any crypto price market** | `event_category = "CRY"` and `instrument_product = "cpc"` |
| **Automated market with typed terms** | `crypto_market_type` present |
| **15-minute up/down window** | `crypto_market_type = "updown"`, `crypto_horizon = "15m"`; window = `interval_start` to `interval_end` |
| **Hourly up/down window** | `crypto_market_type = "updown"`, `crypto_horizon = "1h"` |
| **Daily above/below strike** | `crypto_market_type = "strike"`, `crypto_horizon = "daily"`; strike = `outcome_strike`; expiry = `interval_end` |
| **All legs of one ladder** | Same `event_id` (or `product_id`) |
| **Price range bucket bounds** | `crypto_market_type = "range"`; `crypto_range_kind` plus `crypto_range_lower` / `crypto_range_upper` |
| **One-touch target and direction** | `crypto_market_type = "hit"`; `outcome_strike` and `crypto_hit_direction` |
| **The open price of an up/down window** | `price_to_beat` (absent until stamped shortly after `interval_start`) |
| **The value a market settled on** | `crypto_settlement_price` (absent until resolution, and permanently absent on a One-Touch that resolved No) |

### Worked Example: 15-Minute Up/Down

A settled 15-minute Bitcoin window that opened at 00:15 UTC on September 21, 2026:

```json theme={null}
{
  "symbol": "cpc-btc-updown-15m-2026-09-21-0015z",
  "metadata": {
    "event_category": "CRY",
    "event_subcategory": "BTC",
    "instrument_product": "cpc",
    "clearing_sym": "CPC-BTC",
    "event_series": "btc-updown-15m",
    "event_id": "btc-updown-15m-2026-09-21-0015z",
    "product_id": "cpc-btc-updown-15m-2026-09-21-0015z",
    "event_start_time": "2026-09-21 00:15:00+00",
    "crypto_asset_slug": "btc",
    "crypto_index_symbol": "BRTI",
    "crypto_market_type": "updown",
    "crypto_horizon": "15m",
    "outcome_strike": "0.0",
    "interval_start": "1789949700",
    "interval_end": "1789950600",
    "price_to_beat": "81650.14",
    "crypto_settlement_price": "81730.83",
    "market_title": "BTC Up or Down: 15 min",
    "market_subtitle": "Sep 20, 8:15PM - 8:30PM"
  }
}
```

To interpret this contract:

1. `crypto_market_type = "updown"` → an up/down window; `crypto_horizon = "15m"` → 15 minutes long.
2. `interval_start` / `interval_end` → the window ran from 00:15:00 to 00:30:00 UTC.
3. `price_to_beat = "81650.14"` → the open value; `crypto_settlement_price = "81730.83"` → the close value.
4. Close ≥ open, so the long side (Yes, "Up") paid \$1.00.

### Worked Example: Daily Above/Below Strike

One leg of the daily ladder expiring at 5:00 PM ET on September 21, 2026:

```json theme={null}
{
  "symbol": "cpc-btc-above-day-2026-09-21-74000",
  "metadata": {
    "event_category": "CRY",
    "event_subcategory": "BTC",
    "instrument_product": "cpc",
    "event_series": "btc-strike-daily",
    "event_id": "btc-above-day-2026-09-21",
    "product_id": "cpc-btc-above-day-2026-09-21",
    "crypto_asset_slug": "btc",
    "crypto_index_symbol": "BRTI",
    "crypto_market_type": "strike",
    "crypto_horizon": "daily",
    "outcome_strike": "74000",
    "interval_end": "1790024400",
    "market_title": "$74,000 or above",
    "event_sort_type": "price",
    "market_sort_order": "1"
  }
}
```

To interpret this contract:

1. `crypto_market_type = "strike"` → an above/below leg.
2. `outcome_strike = "74000"` → pays if the settlement value is at or above \$74,000.
3. `interval_end = "1790024400"` → settles on the last-minute average before 21:00 UTC (5:00 PM ET).
4. Every other strike of the same ladder shares `event_id = "btc-above-day-2026-09-21"`.

### Worked Example: Daily Price Range Bucket

An interior bucket of the price range ladder with the same expiry:

```json theme={null}
{
  "symbol": "cpc-btc-range-day-2026-09-21-74000",
  "metadata": {
    "event_category": "CRY",
    "event_subcategory": "BTC",
    "instrument_product": "cpc",
    "event_series": "btc-range-daily",
    "event_id": "btc-range-day-2026-09-21",
    "product_id": "cpc-btc-range-day-2026-09-21",
    "crypto_asset_slug": "btc",
    "crypto_index_symbol": "BRTI",
    "crypto_market_type": "range",
    "crypto_horizon": "daily",
    "crypto_range_kind": "interior",
    "crypto_range_lower": "74000.00",
    "crypto_range_upper": "74499.99",
    "outcome_strike": "74000",
    "interval_end": "1790024400",
    "market_title": "$74,000 to $74,499.99",
    "event_sort_type": "manual",
    "market_sort_order": "2"
  }
}
```

To interpret this contract:

1. `crypto_market_type = "range"` → a price range bucket in a mutually exclusive event.
2. `crypto_range_lower` / `crypto_range_upper` → pays if the settlement value is between \$74,000.00 and \$74,499.99 inclusive.
3. The neighbouring buckets are `$73,999.99 or below` (`crypto_range_kind = "below"`, no lower bound) and `$74,500 to $74,999.99`.

### Worked Example: Monthly One-Touch

A "Dips to" leg of a monthly one-touch ladder has this shape:

```json theme={null}
{
  "symbol": "cpc-btc-hit-l-m-2026-10-57500",
  "metadata": {
    "event_category": "CRY",
    "event_subcategory": "BTC",
    "instrument_product": "cpc",
    "event_series": "btc-hit-monthly",
    "event_id": "btc-hit-l-m-2026-10",
    "product_id": "cpc-btc-hit-l-m-2026-10",
    "crypto_asset_slug": "btc",
    "crypto_index_symbol": "BRTI",
    "crypto_market_type": "hit",
    "crypto_horizon": "monthly",
    "crypto_hit_direction": "low",
    "crypto_hit_method": "trimmed_mean_60s_20",
    "outcome_strike": "57500",
    "interval_start": "1790827200",
    "interval_end": "1793505600",
    "market_title": "Dips to $57,500"
  }
}
```

To interpret this contract:

1. `crypto_market_type = "hit"` with `crypto_hit_direction = "low"` → pays if the rolling trimmed mean is at or below the target at any point in the window.
2. `outcome_strike = "57500"` → the target.
3. `interval_start` / `interval_end` → the window runs from midnight ET on October 1 to midnight ET on November 1, 2026. The market can settle Yes early; a No is decided after `interval_end`.

***

## Section 4: Hand-Listed Markets

The exchange also lists crypto markets by hand, for example the year-end Bitcoin ladders (`btc-pricerange-yr-12-31-2026`, `btc-hitprice-high-yr-12-31-2026`, `btc-hitprice-low-yr-12-31-2026`, `btc-above-yr-12-31-2026`) and the "When will Bitcoin hit \$150k?" date ladder (`btc-150k`). These carry `event_category = "CRY"` and a `cpc-` symbol but **none of the `crypto_*` fields**, and on the Retail API they show `marketType: "futures"` with `assetPriceTerms: null`.

For these markets the contract terms are only in `instrument_rules` (Retail `description`). Read that text for the index, the statistic and the settlement instant: the year-end markets settle on a 60-second 20% trimmed mean of BRTI, for example, whereas the automated above/below and price range ladders settle on a simple last-minute average.

***

## Best Practices

* **Never parse the symbol or slug** to determine the market type, window, or strike. Symbol formats are not part of the public contract.
* **Map on `crypto_market_type`.** Treat an unknown value as a newer family: render the terms that are present and watch the [changelog](/changelog).
* **Read windows from `interval_start` and `interval_end`**, not from the instrument's expiration date, which is 30 minutes after settlement.
* **Treat every price as a decimal string** (`outcome_strike`, `price_to_beat`, `crypto_range_*`, `crypto_settlement_price`) and convert it yourself. Compare in cents; bounds end in `.99`.
* **Expect `price_to_beat` to appear a few seconds after an up/down window opens.** Re-read the instrument metadata after `interval_start` rather than assuming the value at listing.
* **Ladders are wide.** An hourly above/below or price range ladder has 30 to 100 legs; subscribe to instrument updates via the [streaming APIs](/trader-guide/streaming-apis) to catch each new ladder as it lists.
* **Follow each market's own rules text.** Hand-listed markets and automated markets can use different statistics for the same asset.


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.