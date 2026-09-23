#!/bin/bash
#
# Bring up/down/health-check parsec v4's 6 host-process services: the 5 MCP
# simulation harnesses (platform/github/icinga/cost/cloud) and parsec-live
# itself. See docs/how-to/ccc/CCC_PODMAN_SETUP.md's "Parsec v4 (v4_t2_e1)"
# section for why these are host processes, not containers.
#
# Usage:
#   export PARSEC_V4N=/path/to/rhdp-parsec/v4_2026-09-16
#   bash scripts/ccc/parsec_stack.sh up
#   bash scripts/ccc/parsec_stack.sh status
#   bash scripts/ccc/parsec_stack.sh down
#   bash scripts/ccc/parsec_stack.sh reap     # kill anything holding our ports, even orphans
#
# Exits non-zero if $PARSEC_V4N is unset, or (for `status`) if any port
# isn't accepting connections within the wait budget.

set -eo pipefail

usage() {
  sed -n '2,15p' "$0"
  exit 2
}

CMD="${1:-}"
if [[ -z "$CMD" ]]; then
  usage
fi

: "${PARSEC_V4N:?PARSEC_V4N environment variable is required (see parsec_paths.py)}"

PID_DIR="$PARSEC_V4N/_run/logs/pids"
LOG_DIR="$PARSEC_V4N/_run/logs/sims"
mkdir -p "$PID_DIR" "$LOG_DIR"

# name:port:kind — kind "sim" starts via `python -m simulation_harness
# --config <harness-cfg/<name>.yaml>`; kind "live" starts parsec-live's own
# `uv run uvicorn` from its own directory. Order matches
# docs/how-to/ccc/CCC_PODMAN_SETUP.md's table.
SERVICES=(
  "platform:8086:sim"
  "github:8087:sim"
  "icinga:8088:sim"
  "cost:8089:sim"
  "cloud:8090:sim"
  "parsec-live:8000:live"
)

banner() {
  printf '\n============================================================\n'
  printf '%s\n' "$1"
  printf '============================================================\n'
}

port_open() {
  local port="$1"
  (exec 3<>"/dev/tcp/127.0.0.1/$port") 2>/dev/null && exec 3>&- 3<&-
}

start_one() {
  local name="$1" port="$2" kind="$3"
  local pid_file="$PID_DIR/$name.pid"
  if [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
    echo "$name already running (pid $(cat "$pid_file"))"
    return 0
  fi
  if [[ "$kind" == "sim" ]]; then
    ( cd "$PARSEC_V4N" && \
      nohup python3 -m simulation_harness --config "_run/harness-cfg/$name.yaml" \
        > "$LOG_DIR/$name.log" 2>&1 & echo $! > "$pid_file" )
  else
    ( cd "$PARSEC_V4N/_run/parsec-live" && \
      nohup uv run uvicorn src.app:app --host 0.0.0.0 --port "$port" \
        > "$LOG_DIR/$name.log" 2>&1 & echo $! > "$pid_file" )
  fi
  echo "started $name (pid $(cat "$pid_file"), port $port, log $LOG_DIR/$name.log)"
}

stop_one() {
  local name="$1"
  local pid_file="$PID_DIR/$name.pid"
  if [[ -f "$pid_file" ]]; then
    local pid
    pid="$(cat "$pid_file")"
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      echo "stopped $name (pid $pid)"
    fi
    rm -f "$pid_file"
  else
    echo "$name: no pid file, nothing to stop"
  fi
}

case "$CMD" in
  up)
    banner "starting parsec v4 stack under $PARSEC_V4N"
    for entry in "${SERVICES[@]}"; do
      IFS=: read -r name port kind <<< "$entry"
      start_one "$name" "$port" "$kind"
    done
    ;;
  down)
    banner "stopping parsec v4 stack"
    for entry in "${SERVICES[@]}"; do
      IFS=: read -r name _ _ <<< "$entry"
      stop_one "$name"
    done
    ;;
  reap)
    # Belt-and-suspenders teardown: kill whatever is actually listening on
    # our 6 ports, regardless of whether a pid file exists for it (covers
    # an orphan left by a killed-mid-startup job). Never sends a bare kill
    # to a pid we didn't just look up by port.
    banner "reaping anything on parsec v4's 6 ports"
    for entry in "${SERVICES[@]}"; do
      IFS=: read -r name port _ <<< "$entry"
      pid="$(lsof -t -i ":$port" -sTCP:LISTEN 2>/dev/null || true)"
      if [[ -n "$pid" ]]; then
        kill "$pid" 2>/dev/null || true
        echo "reaped $name (port $port, pid $pid)"
      fi
    done
    rm -f "$PID_DIR"/*.pid
    ;;
  status)
    banner "waiting for parsec v4 stack health (max 60s)"
    deadline=$((SECONDS + 60))
    for entry in "${SERVICES[@]}"; do
      IFS=: read -r name port _ <<< "$entry"
      until port_open "$port"; do
        if (( SECONDS >= deadline )); then
          echo "FATAL: $name (port $port) never opened within 60s" >&2
          exit 1
        fi
        sleep 1
      done
      echo "OK: $name (port $port) is accepting connections"
    done
    ;;
  *)
    echo "Unknown command: $CMD" >&2
    usage
    ;;
esac
