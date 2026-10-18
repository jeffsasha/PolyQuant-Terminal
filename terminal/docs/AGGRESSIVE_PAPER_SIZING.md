# Aggressive paper profile and adaptive sizing

October 17, 2026. The owner explicitly selected: a separate aggressive simulation targeting 70% simultaneous deployment, maximum 80%, accepting possible total loss of committed funds. This is an authorized paper experiment, not a change to live-trading permissions or validation status.

## Separate profile

`book_aggressive` starts with its own $1,000, uses frozen strategy `book-imbalance-aggressive-v2`, and is the default bot profile. The original `book_experiment` account, version, balances, one-contract sizing and conservative limits remain available. Only one automation profile is armed at a time. STOP is required before changing profile; STOP/emergency stop cancel pending orders for both automation accounts and retain holdings. Native restart requires RUN again.

The directional signal is unchanged: same-direction top-three-level quantity imbalance of at least 20%, three distinct fresh source observations, minimum four-second span, source/receive freshness, price/spread gates and no late-window entries. No BRTI forecast, calibrated edge or copy trading is introduced. Manual tickets cannot access either automation account. Live execution remains code-prohibited.

## Frozen aggressive limits

| Parameter | Aggressive paper | Original conservative paper |
|---|---:|---:|
| Total target deployment | 70% | Fixed one contract per signal |
| Target per cadence | 35% | Fixed one contract per signal |
| Maximum possible loss per new entry, including fees | 40% of risk equity | 0.5% |
| Maximum committed cost plus pending reservations on admission | 80% of risk equity | 5% |
| Maximum per-cadence commitment on admission | 40% of risk equity | 2.5% |
| Daily-loss new-entry halt | 20% | 2% |
| Positions including pending entries | Two; one per cadence | Two; one per cadence |
| Exit | Official settlement | Official settlement |

These are entry controls, not guaranteed portfolio loss or utilization bounds after prices move. Open holdings may lose more than the daily entry-halt threshold. A fall in equity can make existing commitment exceed the percentage entry cap; this blocks additional entries and does not invent a forced sale. Three consecutive realized losses still impose the existing 30-minute cooldown. Same-risk-day daily locks cannot be resumed away.

## Quantity calculation

For a qualifying signal, take the minimum of:

- 35% of current risk equity minus existing commitment for that cadence;
- 70% total target minus all open acquisition cost **and paid entry fees** and pending reservations;
- 40% per-entry hard budget;
- remaining 80% total and 40% cadence hard-cap budgets;
- unreserved cash.

Price limit is the current executable ask (or DOWN complement of YES bid) plus one tick. Only eligible visible levels within that limit count, and only 50% of their quantity is usable. Decimal binary search finds the largest venue quantity increment whose limit-price purchase plus rounded-up worst-case fee reserve fits the budget and visible depth. It never rounds up to force a minimum lot. Insufficient capacity/depth yields NO_TRADE. Arrival still obtains a new actual production book and rechecks the same frozen risk profile; partial IOC remainder cancels. Admitted attempts are not chased.

Target 70% is not a compulsory allocation. A missing signal, insufficient depth, fee reserve, source fault, loss lock or cadence slot can leave deployment much lower. A large balance does not imply a large executable order. Sizing details and all limiting budgets are retained with the decision.

## Valuation

Aggressive admission and sizing use account-specific conservative **net full liquidation** estimates: available fresh bids, conservative 50% depth, one adverse tick and modeled exit fees. A small account's mark must never value a larger position in another paper account. No midpoint or stale quote is a valid liquidation mark. Missing/full-depth-unprovable valuations use zero as a labeled risk bound and block aggressive entries with `PORTFOLIO_VALUATION_UNAVAILABLE`; that absence alone must not create a persistent daily-loss lock. Displayed estimates are not paper sales or realized PnL.

Snapshots, equity recordings and risk-day rollovers use account-specific marks. If marks are incomplete at rollover, the prior baseline/day are retained and a persisted pending flag blocks aggressive entries. Once full marks return, the new baseline is the greater of the prior known baseline and the newly observed equity, preventing a cash-only or delayed lower baseline from concealing losses. STOP/RUN increments a generation token; an in-flight read from a previous profile/run cannot warm up or submit for the new profile. Risk profiles are server-assigned exact account/version pairs; callers cannot select aggressive limits for a conservative or research account. The UI displays the selected account's actual risk percentages instead of hard-coded 0.5%/2% labels.

## Verification sequence

Test sizing against equity changes, fee rounding, pending reservations, paid fees, venue increments and shallow books; test exact profile scoping and 80% cap. Then integration-test both cadence entries/arrivals, profile switching, preserved old balances, manual-ticket rejection, missing-valuation handling and cross-account mark isolation. Build/type-check the English UI, run browser RUN/STOP and profile/risk-label regressions, obtain a fresh independent review, restart and verify the default profile is stopped with the approved parameters. Synthetic sizing/fills prove mechanics, not production liquidity or strategy performance.
