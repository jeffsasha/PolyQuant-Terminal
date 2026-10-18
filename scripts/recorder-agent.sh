#!/usr/bin/env bash
# Manage the continuous recorder as a macOS launchd user agent (no admin rights, nothing outside your user).
# Usage: scripts/recorder-agent.sh install|uninstall|start|stop|status|logs
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="com.polyquant.recorder"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOGDIR="$HOME/Library/Logs/polyquant"
DOMAIN="gui/$(id -u)"
case "${1:-status}" in
  install)
    mkdir -p "$HOME/Library/LaunchAgents" "$LOGDIR"
    cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>$ROOT/scripts/run-recorder.sh</string></array>
  <key>WorkingDirectory</key><string>$ROOT</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>30</integer>
  <key>StandardOutPath</key><string>$LOGDIR/recorder.log</string>
  <key>StandardErrorPath</key><string>$LOGDIR/recorder.log</string>
  <key>ProcessType</key><string>Background</string>
</dict></plist>
PL
    launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
    launchctl bootstrap "$DOMAIN" "$PLIST"
    echo "installed and started $LABEL (logs: $LOGDIR/recorder.log)";;
  uninstall)
    launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
    rm -f "$PLIST"; echo "removed $LABEL";;
  start) launchctl kickstart "$DOMAIN/$LABEL" ;;
  stop) launchctl kill TERM "$DOMAIN/$LABEL" ;;
  status)
    launchctl print "$DOMAIN/$LABEL" 2>/dev/null | grep -E "state =|pid =|last exit code" || echo "$LABEL not installed"
    curl -s -m 3 http://127.0.0.1:8787/health | python3 -c 'import json,sys; d=json.load(sys.stdin); print("health ok:", d["ok"], "| ws:", (d.get("ws") or {}).get("connected"), "| stale feeds:", [f["feed"] for f in d["feeds"] if f["stale"]])' 2>/dev/null || echo "API not responding"
    du -sh "$ROOT/.pgdata" 2>/dev/null | awk '{print "database size:", $1}';;
  logs) tail -n 50 "$LOGDIR/recorder.log" ;;
  *) echo "usage: $0 install|uninstall|start|stop|status|logs"; exit 2 ;;
esac
