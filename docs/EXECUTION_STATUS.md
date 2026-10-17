# Execution Status

Updated October 17, 2026 (client date). Local discretionary paper trading now supports production US BTC 15m/1h snapshots, conservative arrival-time IOC fills, exits, persistent audit history and official binary settlement. The English terminal runs at http://127.0.0.1:3000. See [README](../README.md) for exact controls and local sign-in.

Live execution is code-prohibited. Reference-dependent and unfitted strategies remain disabled. The BRTI discrepancy is still unresolved; see [research evidence](BRTI_FOLLOWUP_RESEARCH.md).

The final independent review found four Important issues in the follow-up; all were fixed and covered by regressions. Verification includes 53 backend tests, six subtests, four browser tests, a production Webpack/TypeScript build, and persisted actual production-book paper trade/official settlement evidence. See [follow-up verification](PAPER_TRADING_FOLLOWUP_VERIFICATION.md) for scope and limits. Fixes were implementer-verified, not independently re-reviewed.

The full research release remains incomplete: authenticated streaming, reference reconciliation, fitted models/full engine replay, 24-hour/load observation, executed Compose, and remote CI remain outstanding. Native services require manual start after reboot. Paper verification accounts are reported separately; no balances were reset.
