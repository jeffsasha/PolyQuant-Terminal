> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.us/llms.txt
> Use this file to discover all available pages before exploring further.

# Asset Prices API Overview

> Reference index price history for crypto price markets

# Asset Prices API

The Asset Prices API returns the reference index prices that crypto price markets settle on, as OHLC candles. Use it to chart the index next to an Up/Down or ladder market, to seed a live price display, or to check a market's `priceToBeat` and `settlementPrice` against the index.

## Endpoints

| Method | Endpoint | Description |
| - | - | - |
| `GET` | `/v1/asset-prices/history` | Bucketed OHLC index price series for one or more assets |

No authentication is required.

## Query Parameters

| Parameter | Type | Description |
| - | - | - |
| `assets` | string\[] | Assets in canonical `<class>:<symbol>` form, e.g. `crypto:btc`. Repeat the parameter for several assets (`?assets=crypto:btc&assets=crypto:eth`), at most 10. This is the same value as `assetPriceTerms.asset` on a market. |
| `from` | integer (unix seconds) | Required. Start of the window. Aligned down to the bucket, and raised when the window would hold more than 3600 candles. |
| `to` | integer (unix seconds) | End of the window. `0` or a future value means now; the in-progress bucket is included. |
| `bucket` | enum | Required candle width: `ASSET_PRICE_BUCKET_1S`, `_5S`, `_15S`, `_1M`, `_5M`, `_15M`, `_1H`, `_1D`. |

The 3600-candle cap is the only size limit, so the widest window scales with the bucket: an hour at `1S`, 60 hours at `1M`, 150 days at `1H`. The effective `from` and `to` after alignment are echoed on each series.

## Example

```bash theme={null}
GET /v1/asset-prices/history?assets=crypto:btc&from=1789949700&to=1789950600&bucket=ASSET_PRICE_BUCKET_1M
```

```json theme={null}
{
  "series": [
    {
      "asset": { "assetClass": "ASSET_CLASS_CRYPTO", "symbol": "btc" },
      "currency": "USD",
      "bucket": "ASSET_PRICE_BUCKET_1M",
      "from": 1789949700,
      "to": 1789950600,
      "candles": [
        { "timestamp": 1789949700, "open": "81646.93", "high": "81690.04", "low": "81633.83", "close": "81653.35", "tickCount": 60 },
        { "timestamp": 1789949760, "open": "81659.13", "high": "81709.62", "low": "81536.86", "close": "81537.63", "tickCount": 60 }
      ]
    }
  ]
}
```

## Response Fields

| Field | Type | Description |
| - | - | - |
| `series[].asset` | object | The asset this series belongs to. Match series to your request by this field, never by position: REST returns series sorted by symbol. |
| `series[].currency` | string | ISO 4217 currency every candle price is quoted in |
| `series[].bucket` | enum | Candle width of the series |
| `series[].from` / `series[].to` | integer | Effective window bounds (unix seconds) after alignment and clamping |
| `series[].candles[].timestamp` | integer | Bucket start (unix seconds) |
| `series[].candles[].open` / `high` / `low` / `close` | string (decimal) | Index prices in the bucket, as decimal strings |
| `series[].candles[].tickCount` | integer | Number of index publications in the bucket. `0` marks a gap-filled bucket: `close` is carried forward from the previous bucket and `open`, `high` and `low` equal it. |

Candles are dense and ascending, one per bucket in the effective window. An unknown symbol in a known class returns an empty series rather than an error.

## Relationship to Markets

* `assetPriceTerms.asset` on a crypto market is the `assets` value to chart against.
* An Up/Down market's `priceToBeat` is the simple average of the 60 one-second prices in the sixty seconds before `windowStart`, from `T − 60 s` up to but not including `windowStart` itself (the interval `[T − 60 s, T)`); its `settlementPrice` is the same statistic at `windowEnd`. The reading 60 seconds before the boundary is part of the average and the reading exactly at the boundary is not. To reproduce it, query `bucket=ASSET_PRICE_BUCKET_1S` with `from = T − 60` and `to = T − 1` and average the 60 `close` values. For `cpc-btc-updown-15m-2026-10-06-1900z`, the candles from 18:59:00 to 18:59:59 inclusive average to the published `priceToBeat` of 85501.45; the minute 18:59:01 to 19:00:00 averages to 85501.37 and does not match.
* Poll the latest candle for a live price display. Prices are published about once per second.

<Note>
  Index price history is available in the preprod environment today and becomes available in production together with the automated crypto markets, as announced in the [changelog](/changelog).
</Note>


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.