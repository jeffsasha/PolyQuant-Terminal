# Implementation Sequence for Review

This is the proposed dependency order and stage gates. It is not the executable task-by-task implementation plan; that plan follows design approval. No stage is reported complete by this document.

## Stage 0 — Verify feasibility and freeze contracts

Confirm production US BTC 15m/1h discovery through read-only requests; inspect typed terms, book messages, index coverage, and settlement semantics. Verify key access locally without logging credentials. Resolve official reference boundary discrepancies using published markets. Complete dependency/license review before installation.

Deliver a capability matrix with production/preproduction separated, dated source and request evidence, adapter contracts, pinned dependencies, and updated source audit. If either cadence is absent, explicitly block its real-data acceptance; do not silently replace it with a different product. The owner can review the verified limitation before any scope change.

**Exit gate:** a supported capability has observed evidence; every unsupported or unverified capability has a reason and dependent features remain disabled.

## Stage 1 — Establish the reproducible persistent core

After plan approval, create private `jeffsasha/PolyQuant-Terminal` if access permits. If a same-named repository already exists, inspect ownership and contents before proceeding; never overwrite or repurpose it silently. Use feature branches and PRs; no unrelated repository changes. Include `README.md`, `DESIGN.md`, `docs/`, `apps/web/`, `services/`, `packages/`, `tests/`, Compose, migrations, placeholder environment settings, and CI. Do not create empty packages or services merely to populate the tree.

Implement single-writer ownership, Decimal types, immutable identities, ledger/reservation transactions, persistent halt state, and the paper-only request boundary before strategy orders. Establish localhost authentication. Keep user-facing instructions in English.

Docker is not currently found in common local paths. Deliver Compose setup and a documented native development path; report Docker verification blocked until a working engine is available. Never claim Compose startup from configuration inspection alone.

**Exit gate:** deterministic accounting, rollback, duplicate handling, access control, and real-order denial checks pass; migration and empty-state startup are reproducible.

## Stage 2 — Real data, discovery, and recorder

Build US discovery/rollover, metadata versions, WS books, REST reconciliation, BTC spot and official index adapters, raw recording, manifests, quota enforcement, freshness and clock checks. Display an initial data terminal with real source provenance, countdowns, and unavailable states.

**Exit gate:** observe real production market windows for both supported cadences, automatic rollovers, a controlled disconnect/resync, and a readable replay manifest. Failure to see a required venue product stays an integration blocker.

## Stage 3 — Paper execution, fees, risk, and settlement

Implement arrival-time marketable limits, partial fills and remainder cancellation, conservative maker research behavior, fee versions/rounding uncertainty, balanced financial postings, official settlement, per-account risk and daily halts. Add manual paper tickets behind the same risk gates. Implement optimistic/base/conservative/stress scenarios.

**Exit gate:** exact-money execution/risk fixtures pass; a recorded market runs from decision through fill or justified rejection, then final settlement when available. Risk and accounting remain valid after injected crashes.

## Stage 4 — Probability baseline and event replay

Implement the contract-statistic probability baseline and its benchmark, point-in-time features, frozen experiment configuration, causal replay, chronological splits, calibration and after-cost reporting. Data warm-up and fit gates keep automation disabled until met.

**Exit gate:** repeat replay with identical input/config hashes gives identical orders and financial output; leakage checks pass; reports label sample limitations and all scenario assumptions. Zero eligible trades is acceptable with reasons.

## Stage 5 — Independent comparisons and complete terminal

Add momentum and book strategies in separate accounts, comparison reports, signal inspection, chart markers, execution history, equity/risk views, light/dark themes, and quota/data-health controls. The Smart Money page shows verified US availability; add actual analytics only after evidence of suitable public US trader data. Copy execution remains deferred.

**Exit gate:** account isolation, fair comparison, and English UI flows pass end-to-end tests; all values have source/status labels and fixtures never appear as live production data.

## Stage 6 — Recovery, security, observation, and review

Run unit/integration/UI tests, crash recovery and restore drills, stale-feed and storage-failure scenarios, and a 24-hour real-data observation session when the machine can stay awake and connected. Verify both rollovers and final settlements when products are available. Benchmark recorded-event replay and inject 10× that observed event rate for a 10-minute load run; overload must produce visible backpressure or a safe halt, not silent drops.

Publish an honest evidence report with commands, versions, exit statuses, observed windows, screenshots, known gaps, and strategy research status. Open and attach a reviewable PR. If GitHub write access or Docker execution is blocked, report the exact limitation with local deliverables and reproducible commands.

**Exit gate:** mandatory engineering checks pass, external checks are either proven or explicitly blocked, and the PR is ready for owner review. No automatic merge, production deploy, or live activation.

## Suggested implementation workflow

After this design is approved, prepare the detailed plan with small dependency-ordered tasks and tests for monetary, security, causal-data, and recovery behavior. Implement and verify each stage before expanding scope. No model/dependency/architecture change is justified solely by a desire for a higher backtest return. Revisit this design when observed venue capabilities contradict a proposed contract.
