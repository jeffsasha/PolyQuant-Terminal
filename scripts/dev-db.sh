#!/usr/bin/env bash
# Project-local PostgreSQL cluster for development (no system service changes).
# Usage: scripts/dev-db.sh start|stop|status|psql
set -euo pipefail
export LC_ALL="${LC_ALL:-C}"  # macOS: postmaster refuses to start without a valid locale
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA="$ROOT/.pgdata"
PORT="${PGPORT_DEV:-54329}"
LOG="$DATA/server.log"
case "${1:-status}" in
  start)
    if [ ! -d "$DATA" ]; then
      initdb -D "$DATA" -U polyquant --auth=trust --encoding=UTF8 --locale=C >/dev/null
      echo "initialised $DATA"
    fi
    pg_ctl -D "$DATA" -l "$LOG" -o "-p $PORT -k $DATA -c listen_addresses=127.0.0.1" -w start
    createdb -h 127.0.0.1 -p "$PORT" -U polyquant polyquant 2>/dev/null || true
    createdb -h 127.0.0.1 -p "$PORT" -U polyquant polyquant_test 2>/dev/null || true
    echo "postgres on 127.0.0.1:$PORT (dbs: polyquant, polyquant_test)";;
  stop) pg_ctl -D "$DATA" -w stop ;;
  status) pg_ctl -D "$DATA" status || true ;;
  psql) exec psql -h 127.0.0.1 -p "$PORT" -U polyquant polyquant ;;
  *) echo "usage: $0 start|stop|status|psql"; exit 2 ;;
esac
