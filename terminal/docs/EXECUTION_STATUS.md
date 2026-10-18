# Execution Status

Updated October 17, 2026. Local English terminal: http://127.0.0.1:3000. The default automation profile is now **Aggressive paper**, an owner-authorized isolated $1,000 simulation with adaptive sizing, 70% total deployment target, 80% total entry cap, 35% target per cadence, 40% entry/cadence caps and 20% daily-loss new-entry halt. Actual positions may lose more than the halt threshold and targets are not compulsory. [Sizing and valuation rules](AGGRESSIVE_PAPER_SIZING.md).

The original one-contract conservative paper profile and its 0.5%/5%/2% settings/balances remain separately available. RUN arms only one profile; STOP is required before switching and cancels both profiles' pending entries while retaining holdings. Restart requires RUN. Real US BTC 15m/1h books and official binary settlement are used.

Live execution, BRTI-dependent/unfitted model strategies and copying remain disabled. [US copy-feed research](US_COPY_TRADING_RESEARCH.md) found no documented public attributable US trader feed or verified performance leaderboard. No fake cohort, international substitution or combined account returns are used.

Conservative full-position liquidation marks and fee reserves constrain adaptive size. Unavailable marks block aggressive entry without inventing a daily loss. Unavailable risk-day baselines defer rollover; recovered baselines cannot be lowered to conceal losses. Independent review identified that rollover issue; implementer reproduced and fixed it with regression evidence.

See [aggressive delivery verification](AGGRESSIVE_PAPER_VERIFICATION.md) for actual test/build/browser/restart evidence and limits. The full research release, model fitting, full replay, authenticated streaming, duration/load verification, Docker execution and remote CI remain incomplete.
