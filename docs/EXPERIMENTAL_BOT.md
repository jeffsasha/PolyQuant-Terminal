# Experimental order-book paper automation

Approved scope: autonomous US BTC 15m and 1h paper entries controlled by RUN and STOP; separate account, real production data, no live execution, no BRTI-dependent forecast. The owner explicitly authorized an unvalidated order-book experiment on October 17, 2026. This exception does not activate the three unfitted model accounts.

## Frozen v1 rules

`book-imbalance-experiment-v1` uses account `book_experiment`, initially $1,000, separately reported. For the top three price levels, imbalance is `(bid quantity - ask quantity) / (bid quantity + ask quantity)`. Three distinct, strictly increasing source timestamps must show the same direction with absolute imbalance at least 0.20. Each snapshot must be fresh at observation; the three confirmations span at least four seconds and at most 30 seconds, with no gap greater than 20 seconds. A stale/missing/wide/neutral book, source failure or direction change resets the applicable observation history. A nonce or body hash alone cannot count as a new source observation.

Positive imbalance buys UP; negative buys DOWN. This is a heuristic hypothesis, not calibrated outcome probability or proven edge. Top-level spread must be at most $0.05. Entry limit is executable ask (or DOWN complement of YES bid) plus one tick and must be $0.05–$0.90. Size is one contract, rounded down to the venue increment, or the venue minimum if larger. Existing full-loss risk gates can reject the resulting size. There is no compulsory trade count and no arbitrary trade after timeout.

Only this exact server-owned account/strategy pair is exempt from BRTI reference and fitted-probability/net-edge gates. Official contract threshold, instrument classification, fresh book, tick/quantity, cutoff, capital, 0.5% full possible loss including fees, two positions/one per cadence, exposure, daily loss and consecutive-loss cooldown remain enforced. The API prohibits manual tickets for the automation account.

Conservative IOC execution uses a new production book after arrival, 50% displayed depth, one adverse tick and modeled fees. The deterministic order ID plus database uniqueness permit at most one admitted entry attempt per market/version, including after STOP/RUN/restart. Rejected risk checks may be reconsidered when data/risk changes; an admitted but canceled/partial order is never chased. Holdings remain until official settlement. No early-exit benefit is assumed.

## Control behavior

RUN clears only resumable account halts, resets signal warm-up, audits the frozen configuration and arms both intervals. Same-risk-day daily halts and persistence faults cannot be cleared. STOP immediately disarms, persists an account halt, cancels pending entries/releases reservations and retains holdings. A read that completes after STOP cannot submit. Emergency stop also stops the bot when another account is selected. Browser refresh does not stop a running backend; backend restart cancels gaps and requires explicit RUN again. Services do not automatically start after Mac reboot.

The backend loop runs roughly every five seconds plus actual source request time. Public GETs share the existing serialized rate limiter and cooldown; an authenticated stream is not currently configured. Signal log explains warm-up, duplicate observations, weak imbalance, price, risk, source and order-attempt waits. Rate failures never become synthetic fills.

## Implementation and verification order

1. Test exact exception scope, sustained observations, UP/DOWN, stale/duplicate/neutral resets.
2. Add automatic strategy tick using existing capture, execution, idempotency, risk and ledger paths; test both cadences, cancellation, filled holdings and stop during source read.
3. Make the bot the default terminal account and expose RUN/STOP plus per-cadence reasons; retain discretionary tickets separately.
4. Verify US copy data from first-party sources, show its actual availability and retain source report.
5. Run full backend/build/browser verification, fresh independent code review, fix substantive findings, restart and observe production decisions without forcing trades.

Unit/integration synthetic books prove mechanics, not live fill quality or profitability. Production checks must retain actual signal/no-trade/fill results and must not relabel fixture outcomes. Validation research, probability fitting, full replay, authenticated streaming and unattended-duration evidence are separate unfinished work.

## Copy trading request

The user also requested copying high-win-rate traders. [US source research](US_COPY_TRADING_RESEARCH.md) found no documented public attributable US source-trade feed or verified US performance leaderboard. The UI marks copying unavailable and the backend reports it disabled. No fake cohort, inferred wallet identity, international-to-US substitution, copied order, or win-rate claim is generated. A future supported identifiable source requires a separate paper experiment and receive-time, net-cost and source-performance tests before automation.
