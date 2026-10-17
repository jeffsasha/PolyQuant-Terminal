# Phase 4 — Fair-probability calibration report

Generated 2026-10-17T16:58:30.356053+00:00. Data: 2944 labelled BTC up/down markets (2026-09-22T15:00:00+00:00 → 2026-10-17T16:30:00+00:00), 2,177,151 official 1 s index points (0 gaps). Excluded: no reference 9, unresolved 3, label conflicts 0.

Split (chronological, embargoed): {'dev': 1756, 'val': 591, 'test': 593, 'embargoed': 4}. Cuts: ['2026-10-07T16:03:00+00:00', '2026-10-12T16:24:00+00:00'].

## Variant selection (development set only; validation shown for transparency)

| variant | dev log loss | dev Brier | val log loss | val Brier | val ECE |
|---|---|---|---|---|---|
| L7200_k120_t4_drift1 **(selected)** | 0.3150 | 0.1014 | 0.3087 | 0.0989 | 0.0122 |
| L7200_k120_gauss_drift1 | 0.3159 | 0.1016 | 0.3105 | 0.0991 | 0.0177 |
| L3600_k120_t4_drift1 | 0.3172 | 0.1019 | 0.3105 | 0.0990 | 0.0159 |
| L3600_k120_gauss_drift1 | 0.3177 | 0.1017 | 0.3121 | 0.0989 | 0.0150 |
| L1800_k120_gauss_drift1 | 0.3207 | 0.1019 | 0.3156 | 0.0991 | 0.0147 |
| L1800_k120_t4_drift1 | 0.3207 | 0.1024 | 0.3142 | 0.0996 | 0.0224 |
| L7200_k120_t4_drift0 | 0.3219 | 0.1039 | 0.3178 | 0.1020 | 0.0156 |
| L7200_k120_gauss_drift0 | 0.3229 | 0.1042 | 0.3201 | 0.1022 | 0.0158 |
| L3600_k120_t4_drift0 | 0.3243 | 0.1044 | 0.3197 | 0.1021 | 0.0187 |
| L3600_k120_gauss_drift0 | 0.3245 | 0.1044 | 0.3223 | 0.1021 | 0.0188 |
| L1800_k120_t4_drift0 | 0.3277 | 0.1049 | 0.3225 | 0.1027 | 0.0227 |
| L1800_k120_gauss_drift0 | 0.3284 | 0.1045 | 0.3245 | 0.1022 | 0.0129 |

## Untouched test set (selected variant, evaluated once)

- Predictions: 2965 across 593 markets (skipped: 0)
- Base rate Up: 0.491
- **Log loss 0.3159** vs coin-flip 0.6931; improvement 0.3772 (90 % market-block bootstrap CI 0.3470 … 0.4016)
- **Brier 0.1004** vs coin-flip 0.2500; ECE 0.0185

### Reliability (test)

| p bin | n | mean p | observed Up freq |
|---|---|---|---|
| 0.0-0.1 | 846 | 0.022 | 0.031 |
| 0.1-0.2 | 229 | 0.144 | 0.157 |
| 0.2-0.3 | 151 | 0.250 | 0.291 |
| 0.3-0.4 | 132 | 0.349 | 0.295 |
| 0.4-0.5 | 137 | 0.448 | 0.474 |
| 0.5-0.6 | 129 | 0.553 | 0.535 |
| 0.6-0.7 | 148 | 0.650 | 0.541 |
| 0.7-0.8 | 175 | 0.749 | 0.760 |
| 0.8-0.9 | 212 | 0.853 | 0.840 |
| 0.9-1.0 | 806 | 0.979 | 0.974 |

### Test breakdown

| slice | n | log loss | Brier | ECE |
|---|---|---|---|---|
| by_horizon: 15m | 2370 | 0.3078 | 0.0974 | 0.0205 |
| by_horizon: 1h | 595 | 0.3483 | 0.1125 | 0.0315 |
| by_seconds_left: 15m:600 | 474 | 0.5545 | 0.1868 | 0.0578 |
| by_seconds_left: 15m:300 | 474 | 0.4231 | 0.1328 | 0.0351 |
| by_seconds_left: 15m:120 | 474 | 0.2774 | 0.0836 | 0.0282 |
| by_seconds_left: 15m:60 | 474 | 0.1742 | 0.0519 | 0.0226 |
| by_seconds_left: 15m:30 | 474 | 0.1100 | 0.0318 | 0.0210 |
| by_seconds_left: 1h:3000 | 119 | 0.6122 | 0.2053 | 0.1072 |
| by_seconds_left: 1h:1800 | 119 | 0.5017 | 0.1621 | 0.1170 |
| by_seconds_left: 1h:900 | 119 | 0.3477 | 0.1107 | 0.0460 |
| by_seconds_left: 1h:300 | 119 | 0.1762 | 0.0532 | 0.0530 |
| by_seconds_left: 1h:60 | 119 | 0.1036 | 0.0313 | 0.0558 |
| by_vol_regime: low | 685 | 0.4063 | 0.1251 | 0.0496 |
| by_vol_regime: mid | 1121 | 0.3209 | 0.1040 | 0.0341 |
| by_vol_regime: high | 1159 | 0.2578 | 0.0824 | 0.0337 |

## Walk-forward (weekly folds; variant re-selected on prior data only)

| fold | start | selected | train markets | n | log loss | coin-flip | Brier |
|---|---|---|---|---|---|---|---|
| 1 | 2026-09-29 | L7200_k120_t4_drift1 | 819 | 4060 | 0.3289 | 0.6931 | 0.1052 |
| 2 | 2026-10-06 | L7200_k120_t4_drift1 | 1631 | 4160 | 0.3062 | 0.6931 | 0.0985 |
| 3 | 2026-10-13 | L7200_k120_t4_drift1 | 2463 | 2405 | 0.3317 | 0.6931 | 0.1056 |

## Model vs market mid (recorded books only)

21 decision points across 6 markets — sample far too small for conclusions; recorded books exist only since 2026-10-17.

| | log loss | Brier |
|---|---|---|
| model | 0.6656 | 0.2204 |
| market mid | 0.4555 | 0.1520 |

## Interpretation limits

- Calibration says how well the model predicts the *official index rule*; it says nothing about profitability until compared with executable prices after costs (see backtest report).
- Checkpoints within a market are correlated; CIs resample whole markets.
- About 3.5 weeks of history; one volatility environment. Results may not transfer.
