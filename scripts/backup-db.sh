#!/usr/bin/env bash
# Dump the recorder database to backups/ (git-ignored). Usage: scripts/backup-db.sh [DATABASE_URL]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
URL="${1:-${DATABASE_URL:-postgresql://polyquant@127.0.0.1:54329/polyquant}}"
mkdir -p "$ROOT/backups"
OUT="$ROOT/backups/polyquant-$(date -u +%Y%m%dT%H%M%SZ).dump"
pg_dump --format=custom --file="$OUT" "$URL"
echo "wrote $OUT"
