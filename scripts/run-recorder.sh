#!/usr/bin/env bash
# Entry point for the continuous recorder (used by the launchd agent; also runnable by hand).
# Ensures the project-local Postgres is up, then runs the engine in the foreground so launchd can supervise it.
set -euo pipefail
export LC_ALL="${LC_ALL:-C}"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if ! pg_ctl -D "$ROOT/.pgdata" status >/dev/null 2>&1; then
  "$ROOT/scripts/dev-db.sh" start
fi
# -i: prevent idle sleep while recording (the lid closing or an explicit sleep still stop it).
if [ "${PQ_PREVENT_SLEEP:-1}" = "1" ]; then
  exec /usr/bin/caffeinate -i "$ROOT/.venv/bin/polyquant" run
fi
exec "$ROOT/.venv/bin/polyquant" run
