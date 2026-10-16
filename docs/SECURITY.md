# Security and Reliability Design

Status: Required implementation behavior; no controls have been tested yet.

## Paper-only boundary

- `LIVE_TRADING_ENABLED` is false; startup rejects attempts to set it true.
- The active US adapter exposes approved data operations only. A transport allowlist permits verified read-only routes and the authenticated market-data stream; exchange order mutation routes are denied before network dispatch.
- LiveExecutionEngine is a disabled contract/stub whose execution methods raise a dedicated error. No live-order route or UI toggle is shipped.
- Order preview is documented for future integration, not required or called in the first release. No account balance, positions, or execution endpoint is needed for a local paper ledger.
- Test the boundary using request interception across all application actions, including manual paper tickets and malicious mode parameters. A permissioned key does not authorize the application to use its trading permissions.

## Credentials and local access

Configure the owner's US key through a gitignored local environment file or mounted secret with restrictive file permissions. Provide placeholders only in `.env.example`. Only the backend loads it; never serialize it into Next.js public variables, browser bundles, logs, recordings, test snapshots, or PR content. Authentication signatures and key identifiers go only to verified official API endpoints as required; the private signing material stays local.

Bind published web/backend ports to 127.0.0.1; keep PostgreSQL internal to Compose. Use a local password hash, expiring HttpOnly SameSite sessions, login rate limiting, CSRF protection for state-changing controls, exact Origin/Host validation, and no permissive CORS. Plain HTTP is limited to localhost in this release; require TLS and secure cookies before remote access. Secret-bearing backend settings are not editable through the dashboard.

Pin and lock audited dependencies. Validate current official SDK version and its transitive dependencies before installation; do not run third-party bot installers. Scan application source and Git history for secrets in CI. No raw recordings, local secrets, or database dumps belong in GitHub.

## Durable safety controls

Persist manual stops, daily loss locks, cooldowns, and storage halts independently of process memory. Default startup state is paused. Risk violations cannot be bypassed through a manual ticket. Cancellation applies to remaining quantity; committed fills remain holdings. Unknown outcomes retain reservations until reconciliation.

Store append-only decisions, executions, and ledger entries with immutable IDs and source hashes. Corrections are compensating entries. Use restricted database roles to prevent ordinary application updates/deletes of audit records. This supports auditability but is not a claim of tamper resistance against the machine owner or database administrator.

Make recorder and database failure visible. A full raw-data budget prevents new entries but does not intentionally stop settlement processing. A fully failed filesystem or database may prevent persistence; expose that failure and resume reconciliation after recovery rather than claiming uninterrupted accounting.

## Backup and recovery

Provide a scheduled local database backup command and a manual backup/export workflow; do not silently install an OS scheduler. Backups and dataset manifests include checksums and version metadata. Restore into a clean database during acceptance, then compare cash, positions, reservations, and halt state. Backups on the same disk do not protect against disk loss; off-device encrypted backups are required before future continuous server operation.

Keep an audit of configuration changes, explicit Paper Start/Resume actions, manual order actions, password events without sensitive contents, and data source failures. Local alerts appear in the terminal and structured logs. External messaging or notification services are outside the first release.

## Future live activation

Requires a separate owner request, implementation review of the live adapter, verified venue permissions, exchange preview and order lifecycle tests, timeout/unknown-outcome reconciliation, balance reconciliation, protective limits, production deployment approval, and controlled activation. Current design approval, a successful paper experiment, repository creation, or changing a variable grants none of these permissions.
