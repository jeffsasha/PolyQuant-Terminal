# Experimental bot delivery verification

October 17, 2026. Scope: the user-authorized unvalidated order-book paper experiment and RUN/STOP controls, extending commit `db28227`. Live execution and BRTI-dependent/unfitted models remain disabled. [Frozen rules](EXPERIMENTAL_BOT.md) describe exactly what the bot does.

## Executed evidence

- Test-first red run: five new backend tests failed because the strategy, exact exception and RUN/STOP routes were missing. Implementation made them green.
- A separate RUN audit-failure regression failed when the bot armed before the audit persisted. Ordering was corrected so an audit failure cannot arm it.
- Full backend suite: **60 passed, six subtests passed** (3.87 seconds). One upstream Starlette TestClient deprecation warning remains.
- Production Next.js Webpack build, TypeScript, prerender and traces: PASS.
- New browser regression first failed against the manual-only app's default account. Final full browser suite: **five passed** (7.2 seconds). It covers default bot account, no manual ticket, RUN/STOP/reload, unavailable-copy messaging, English controls, isolated manual halt persistence, prior genuine paper lifecycle evidence, preview races and mobile overflow.
- The first full browser run exposed an obsolete test assumption: reload now selects the bot rather than the manual account. The test was corrected to reselect its stopped manual account before checking persistence. No balance/halt reset was used to conceal the failure.
- Generated local password scan: PASS for tracked/candidate files and browser static assets. Exchange credentials were not inspected.

## Source and execution limits

[Production observation](evidence/experimental-bot-production.json) records actual RUN, real production decisions for BTC 15m and 1h, and STOP. It observed signal warm-up, imbalance below threshold and venue rate limiting. **Zero bot orders and zero bot fills occurred during this observation.** No trade was forced, no synthetic book was labeled production, and no parameter was relaxed to manufacture activity. Synthetic integration books separately verify automatic entry reservation, arrival fills, pending cancellation, duplicate prevention and retention of filled holdings after STOP.

The public fallback shares serialized GET/cooldown rules; authenticated streaming remains unconfigured. RUN will keep evaluating after transient source cooldowns. Sustained signal and risk gates can legitimately produce zero trades. The experiment does not establish expected profitability, win rate, calibration or out-of-sample performance.

The earlier real-book discretionary and verification trades retain their original balances and source/official-settlement evidence. Their results are not bot-strategy returns and are not combined with the new account.

## Independent review

A fresh read-only reviewer inspected bot lifecycle/races, deterministic order identity, admission/arrival risk, account isolation, API authorization, frontend controls and copy-feed messaging. It reported **no Critical or Important findings** in the final candidate and independently ran four relevant non-database unit tests. It did not access runtime databases, credentials, private logs or orders. The implementer executed the integration/browser/production checks above.

## Copy trading

[Primary-source US feasibility research](US_COPY_TRADING_RESEARCH.md) found no documented public attributable US source-trade feed or verified trader-performance leaderboard. The terminal explicitly reports copying unavailable/disabled. No fake high-win-rate cohort, international-to-US substitution or inferred participant identity is implemented. An entitled identifiable source feed is required before this part of the request can be fulfilled.

## Final armed restart check

The bot was armed through the authenticated local API, then the native services/database were stopped and restarted. [Post-restart state](evidence/experimental-bot-restart.json) confirmed HTTP 200 web, PAPER mode, both production cadences present, bot STOPPED with `RESTART_REQUIRES_RUN`, no pending orders/holdings/fills in the new account, original $1,000 cash, reference validation false and copying disabled. The app remains running locally; the owner must press RUN to arm it.
