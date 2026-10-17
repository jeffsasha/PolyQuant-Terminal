# apps/web — PolyQuant terminal UI (Phase 2c)

Not started. It needs Node.js ≥20, which isn't installed on the development machine yet. It will consume the
read-only engine API (`/v1/markets`, `/v1/reference`, `/health`, `/v1/alerts`). It must never call the venue
directly, and never render rows whose `source` is `fixture` outside test builds.
