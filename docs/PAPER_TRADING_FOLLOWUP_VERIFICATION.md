# Paper trading follow-up verification

October 17, 2026 (client date). This supersedes the earlier recorder-only delivery for manual paper trading; it does not unlock reference-dependent strategies or complete the full research release.

## What was wrong

Manual buys received no model probability but were subjected to model/reference admission gates, so every buy was rejected. There was no complete place/order/fill/exit UI. Cached REST books failed freshness checks. Arrivals shared a slow metadata/reference loop, and a preview-time book could previously be consumed at arrival. Same-market order uniqueness prevented a manual buy/sell cycle. An old API listener also survived a lost PID record; the previous launcher could mistakenly accept its health response as proof the new backend was ready. Opening the website as localhost instead of 127.0.0.1 was rejected by the Origin check.

## Implemented behavior

Discretionary paper and Verification (paper) accounts use the same initial money and hard risk limits, with independent balances. Only the server-assigned discretionary account/strategy pairs omit model-derived reference/probability requirements. The three research accounts retain their gates. Verification trades never form strategy-return evidence and are not added to user-account returns.

Each preview and order arrival obtains a production snapshot, records its source timestamp/cache age/body hash, and checks freshness. GET-only cache-key variation was observed to produce a cache miss/current timestamp where normal reads returned cached data. Public HTTP429 was also observed. The fallback now uses at most one GET/second, honors Retry-After plus exponential cooldown, and fails fast during cooldown rather than repeatedly attempting queued requests. Unavailable arrival data cancels the unfilled IOC order and retains positions.

The UI supports preview/place, order state/cancel, fills and fees, exit preparation, closed/settled positions, pause/stop/resume, account/scenario selection, data health, themes, recording verification and audit dialogs. Rejected previews are logged directly; a button intended merely to record a rejection can no longer become an order when data improves. A preview is bound to every ticket field and cannot follow a contract rollover or delayed edited response.

Official settlement uses resolved status plus a matching binary endpoint payoff; no inferred BRTI/spot outcome is permitted. Missing outcomes retain collateral. Correction monitoring has no silent 24-hour cutoff, and corrections can return to a previously seen payoff without duplicate credits.

## Research evidence

[BRTI follow-up](BRTI_FOLLOWUP_RESEARCH.md) preserves eight market comparisons, cross-bucket inconsistencies, the official worked-example failure, 67 validated public-body hashes, and official binary payoff reads for four 15m and three 1h markets. The double-averaging hypothesis remains unconfirmed; model reference validation remains false.

## Independent review

Fresh read-only review of be6c512..99f7dc8 found no Critical live-order or research-gate escape. Four Important findings were fixed:

- Persist daily-loss locks at preview/admission/arrival rejection; restored same-day equity cannot re-admit.
- Bind previews to immutable account/market/side/quantity/limit/scenario and discard late responses for changed tickets.
- Retain correction watch beyond 24 hours and restart.
- Recover missing PID files without aborting shutdown; actual listener ownership is verified.

The review's readiness-label minor was addressed with server feed readiness/cooldown indicators. The reviewer independently ran 14 non-database tests plus six subtests. Fixes were verified by the implementer, not re-reviewed by another agent.

## Executed checks

- Full backend suite: **53 passed, six subtests passed**. One upstream Starlette TestClient deprecation warning remains.
- Production Next.js Webpack build and TypeScript: PASS.
- Controlled UI regression: edited ticket during delayed preview and market replacement after preview both remove Place permission; zero orders are sent. This is explicitly fixture evidence, not production execution evidence.
- Real localhost checks: persistent stop/pause/resume, both exact local Origins, five isolated accounts, no live order path.
- Actual production book checks already recorded an hourly buy and sale, a 15m buy, and a canceled 15m sale when its arrival read failed. The holding was retained. A prior manual test buy was also preserved. No account balance, loss, or holding was reset to make a check pass.

Final resumed browser suite: **four passed**. The production lifecycle test resumed actual persisted trades rather than fabricating new fills. The hourly position closed through a real-book paper sale; the 15m exit read failed, leaving the holding intact until an official DOWN settlement arrived. Both verification positions are now closed or settled. The separate manual position also settled from the official endpoint. These are execution checks, not strategy-performance evidence.

Safe ledger, fill and settlement evidence is retained in [production-paper-lifecycle.json](evidence/production-paper-lifecycle.json). Verification order IDs:

- 1h buy: `674794ce-4c82-47d3-9da3-123a53532761`; sell: `4c5503fc-a6f5-49e7-b5e9-168cc8dd9970` (both FILLED).
- 15m buy: `63c27fd6-2c5f-46e5-b642-108aa377429d` (FILLED); sell: `1ab7416a-3d0a-4b5f-87f6-632769be7bb4` (CANCELED, ARRIVAL_BOOK_REFRESH_FAILED), followed by official settlement.

No paper balances or losses were reset. Authenticated streaming remains unconfigured. Public snapshot access can return stale data, rate limits or errors, which honestly reject/cancel paper requests. Reference validation remains false, live execution remains prohibited, and all unvalidated strategies remain disabled.


Final restart: launcher stopped and restarted the workspace database/API/web successfully. Fresh post-restart verification passed 53 backend tests plus six subtests and four browser tests (3.9s). Authenticated state confirmed production 15m/1h contracts, PAPER mode, reference validation false, no REST cooldown at observation, and preserved balances. Generated local passwords were absent from tracked/candidate files and browser static assets.
