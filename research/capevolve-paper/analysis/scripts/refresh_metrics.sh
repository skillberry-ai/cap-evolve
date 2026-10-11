#!/usr/bin/env bash
# refresh_metrics.sh [--once | --stop | --status]
#   (no args)  start a detached loop (setsid) that runs collect_metrics.py every 30 min until 2026-10-13 07:00 UTC
#   --once     run collect_metrics.py once, in the foreground (safe to call on demand at any time)
#   --stop     stop the background loop
#   --status   show whether the loop is running and the last log lines
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$HERE/../out/metrics"
mkdir -p "$OUT"
PIDF="$OUT/.refresh.pid"; LOG="$OUT/refresh.log"; LOCK="$OUT/.refresh.lock"
DEADLINE="2026-10-13T07:00:00Z"; INTERVAL=1800
run_once() { ( flock -n 9 || { echo "$(date -u +%FT%TZ) another collect is running; skipped" >> "$LOG"; exit 0; }
               { echo "$(date -u +%FT%TZ) collect start"; python3 "$HERE/collect_metrics.py" && echo "$(date -u +%FT%TZ) collect ok" || echo "$(date -u +%FT%TZ) collect FAILED"; } >> "$LOG" 2>&1
             ) 9>"$LOCK"; }
case "${1:-}" in
  --once) run_once; tail -n 3 "$LOG"; exit 0 ;;
  --stop) [ -f "$PIDF" ] && kill "$(cat "$PIDF")" 2>/dev/null && echo stopped || echo "not running"; rm -f "$PIDF"; exit 0 ;;
  --status) if [ -f "$PIDF" ] && kill -0 "$(cat "$PIDF")" 2>/dev/null; then echo "running pid $(cat "$PIDF")"; else echo "not running"; fi; tail -n 5 "$LOG" 2>/dev/null; exit 0 ;;
  --loop) ;;
  "") if [ -f "$PIDF" ] && kill -0 "$(cat "$PIDF")" 2>/dev/null; then echo "already running pid $(cat "$PIDF")"; exit 0; fi
      setsid nohup "$0" --loop > /dev/null 2>&1 < /dev/null &
      echo "started refresh loop (every ${INTERVAL}s until $DEADLINE); log: $LOG"; exit 0 ;;
  *) echo "usage: $0 [--once|--stop|--status]"; exit 2 ;;
esac
# --loop (detached)
echo $$ > "$PIDF"
trap 'rm -f "$PIDF"' EXIT
END=$(date -u -d "$DEADLINE" +%s)
while [ "$(date -u +%s)" -lt "$END" ]; do
  run_once
  sleep "$INTERVAL"
done
echo "$(date -u +%FT%TZ) deadline reached; loop exits" >> "$LOG"
