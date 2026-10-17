# Strategy A (external spot) vs B — pre-registered evaluation

Generated 2026-10-17T20:45:09.127192+00:00. Markets with Kraken spot coverage: 2959 (2026-09-21T21:00:00+00:00 → 2026-10-17T20:44:49+00:00); 931,215 Kraken 1 s bars. Split {'dev': 1767, 'val': 595, 'test': 593, 'embargoed': 4}, cuts ['2026-10-07T18:18:00+00:00', '2026-10-12T19:24:00+00:00'].

## H1 (primary): A1 vs B1 on the untouched test split

| model | n | log loss | Brier | ECE |
|---|---|---|---|---|
| A1 L7200_k120_t4_drift1_spot | 2961 | 0.3066 | 0.0972 | 0.0117 |
| B1 L7200_k120_t4_drift1 | 2965 | 0.3196 | 0.1021 | 0.0200 |

Paired log loss(B1) − log loss(A1) = **0.0132** on 2961 points / 593 markets; 90 % CI 0.0077 … 0.0188. **H1 SUPPORTED** (criterion: CI above 0).

## Secondary: A variant selected on development data

Selected: L7200_k120_t4_drift1_spot; test log loss 0.3066, Brier 0.0972.

| variant | dev log loss | val log loss |
|---|---|---|
| L7200_k120_gauss_drift0.5_spot | 0.3095 | 0.3034 |
| L7200_k120_gauss_drift1_spot | 0.3053 | 0.2969 |
| L7200_k120_t4_drift0.5_spot | 0.3075 | 0.3014 |
| L7200_k120_t4_drift1_spot | 0.3031 | 0.2943 |
| B1 (reference) | — | 0.3113 |

## Walk-forward (A variants re-selected on prior data)

| fold | start | selected | n | log loss |
|---|---|---|---|---|
| 1 | 2026-09-29 | L7200_k120_t4_drift1_spot | 4059 | 0.3161 |
| 2 | 2026-10-06 | L7200_k120_t4_drift1_spot | 4160 | 0.2906 |
| 3 | 2026-10-13 | L7200_k120_t4_drift1_spot | 2476 | 0.3206 |

## H2 (secondary): vs market mid on recorded books (30 s grid)

306 decision points across **15 markets** (NOT conclusive: < 30 markets). Points within a market are highly correlated.

| | log loss | Brier |
|---|---|---|
| market mid | 0.5690 | 0.1989 |
| A1 | 0.6158 | 0.2185 |
| B1 | 0.6422 | 0.2283 |

Paired log loss(market) − log loss(A1) = -0.0468 (90 % CI -0.0878 … -0.0148); positive would favour A1.
