# Aggressive paper sizing verification

October 17, 2026. Extends `4092438` with the explicitly approved isolated aggressive simulation. [Frozen policy](AGGRESSIVE_PAPER_SIZING.md): adaptive quantities, 70% deployment target, 80% total entry cap, 35% cadence targets, 40% entry/cadence caps, 20% daily-loss new-entry halt. Original conservative account/version/settings remain separate. No live, BRTI-model or copy-trading activation.

## Tests and build

- Four sizing/profile tests first failed because per-account configuration and adaptive sizing were absent; implementation made them pass.
- Two integration tests first failed because profile selection and conservative execution-side valuation were missing.
- Cross-account valuation and unavailable-mark tests reproduced overvaluing a large position with another account's small-position mark, and absence of an explicit valuation-ready flag. Both were fixed and passed.
- Independent review identified cash-only risk-day baseline corruption at unavailable rollover. The regression first failed with baseline650 instead of1000. The repair defers rollover, blocks aggressive admission while the baseline is pending and preserves the greater prior/current baseline after a gap. Same-day persistent daily-loss behavior remains enforced.
- A separate STOP/RUN profile-switch test first failed because an old in-flight read warmed the newly armed profile. A generation guard now discards that stale context.
- Final full backend suite: **70 passed, six subtests passed** (6.86s). One upstream Starlette TestClient deprecation warning remains.
- Final production Webpack build and TypeScript: PASS.
- Full browser suite against the restarted app: **five passed** (7.9s), including default aggressive account, 70%/80% labels, 40% aggressive versus0.5% conservative risk labels, RUN/STOP/reload, disabled copy messaging, prior manual controls/lifecycle, preview race and mobile overflow.
- Generated local password scan of tracked/candidate files and browser static assets: PASS. Exchange credentials were not inspected.

Synthetic integration books verify automatically sized entries for both cadences, conservative actual arrival fills, STOP retaining filled positions, fee/depth/lot caps, cash and pending reservations, original-account isolation, API manual-ticket rejection and profile switch rejection while running. These fixture outcomes are not production liquidity or profitability evidence.

## Independent review

A fresh read-only reviewer reported no Critical finding and one Important rollover-baseline finding, described above. It independently ran **39 non-database tests plus six subtests**. The implementer reproduced/fixed the finding and ran the full suite; fixes were not independently re-reviewed a second time. No reviewer accessed credentials, private logs, runtime database or orders.

## Actual production observation

[Real observation](evidence/aggressive-paper-production.json) records RUN for `book_aggressive` on real US production books, decisions for both BTC15m/1h, and final STOP. It observed insufficient imbalance, warm-up, stale books and venue rate limiting. **Zero aggressive orders/fills/positions** occurred; no signal was forced or freshness rule relaxed to manufacture deployment. The account retains its original $1,000. Existing conservative accounts retain their separate ledgers and balances.

Public REST is still the fallback; authenticated streaming remains unconfigured. A 70% target is not guaranteed utilization. Even an eligible signal is sized to conservative actual depth and can partially fill/cancel at arrival. After prices move, existing commitment can exceed percentage admission caps without a fictitious liquidation. Daily-loss entry halts do not guarantee maximum loss on open holdings.

The local app was restarted with the deployed profile/migration and left running, bot STOPPED. Final authenticated state and active policies are saved separately. User action: refresh the terminal, select **Aggressive paper** under **Bot profile**, press RUN. STOP cancels pending entries and retains holdings for official settlement.
