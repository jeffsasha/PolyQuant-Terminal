# Production-data manual paper trading fix

Owner requested investigation of both BRTI intervals and a functioning paper-trading interface after finding buttons and orders unusable.

Confirmed causes: the API gives manual intents no probability but applies MODEL_PROBABILITY_UNAVAILABLE and the reference gate to every buy; the ticket offers only rejection recording rather than an order submission lifecycle; cached REST books routinely fail the freshness gate; processing arrivals after discovery/index/spot polling can miss fresh-book timing; order uniqueness prevents a manual buy and subsequent sell in the same market.

Ruling: introduce an isolated `manual` discretionary paper account with the same $1,000 initial capital, maximum-loss/fee budget, exposure/slot/daily/cooldown, market-window, tick/quantity, spread, and fresh-book rules. Only that server-assigned account/intent pair omits model/reference-derived edge requirements. The three research accounts remain blocked and their results stay uncontaminated. No claim of calibrated probability, demonstrated edge or automatic strategy execution is made for manual trading.

Public GET experiment: ordinary and no-cache-header book calls returned CF HIT/Age12 with old transactTime; a unique read query returned CF MISS with current transactTime. Use bounded read-only polling and independent arrival captures, retaining actual timestamps/cache headers and the two-second freshness requirement. Never fill from preview data, last price, midpoint or invented missing depth.

Implement in order: regression tests; manual account/risk and repeatable order/position ledger; fresh GET adapter + bounded arrival worker; authenticated preview/place/status/cancel and authoritative settlement where verified; working English controls and clear unavailable states; fixture API/order lifecycle checks and actual production-book browser buy/close in both cadences; fresh independent review and local restart.

Acceptance: observe actual new paper order IDs, arrival book hashes/timestamps, partial/full fills or honest limit cancellation, cash/fees/positions, sale/settlement and restart persistence. Test a closed-market and stale-book rejection and strategy-gate non-bypass. Do not call a test of successful rejection a successful paper-trading test. BRTI facts/inferences remain separately documented by primary-source research.


Follow-up: a separate Verification (paper) account preserves user-account risk budgets during lifecycle tests. Both discretionary accounts retain the same hard limits. Final independent-review fixes and evidence are recorded in [follow-up verification](PAPER_TRADING_FOLLOWUP_VERIFICATION.md).
