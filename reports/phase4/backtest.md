# Phase 4 — Execution replay (recorded WS books)

Generated 2026-10-17T17:09:05.929128+00:00. Strategy fair_prob[L7200_k120_t4_drift1], IOC entries held to settlement, min edge 0.02 after conservative costs. Resolved markets with recorded books: 11.

**Sample warning:** recorded books exist only since 2026-10-17. Results below are a pipeline check, not evidence of edge (gate: ≥ 300 independent markets out of sample).

| profile | markets | signals | trades | net PnL | gross | fees | slippage | win rate | EV/trade (90 % CI) | max DD | fill rate |
|---|---|---|---|---|---|---|---|---|---|---|---|
| optimistic (diagnostic) | 11 | 7 | 7 | -1.59 | -0.62 | 0.97 | 0.00 | 0.43 | -0.227 (-3.149 … 2.698) | 10.02 | 1.00 |
| base | 11 | 7 | 7 | -1.37 | -0.41 | 0.96 | -0.21 | 0.43 | -0.196 (-3.149 … 2.759) | 9.94 | 1.00 |
| conservative | 11 | 7 | 6 | 2.14 | 3.02 | 0.88 | 0.30 | 0.50 | 0.356 (-2.811 … 3.782) | 10.24 | 1.00 |
| stress | 11 | 7 | 3 | 8.07 | 8.50 | 0.43 | 0.27 | 0.67 | 2.690 (-1.447 … 6.827) | 4.10 | 1.00 |

Risk rejections / arrival rejections per profile:

- optimistic: risk {}, arrival {}, unfilled 0
- base: risk {}, arrival {}, unfilled 0
- conservative: risk {}, arrival {}, unfilled 1
- stress: risk {}, arrival {}, unfilled 4
