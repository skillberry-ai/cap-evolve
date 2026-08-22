#!/usr/bin/env bash
# Tear down the tau2_airline_spa environment.
#
# WHAT IT DOES
#   1. stops the three services (SPA, store, tau2 env manager)
#   2. removes their PID sentinels and this example's log files
#   3. removes the repos this example cloned:
#      vendor/skillberry-{store,agent,benchmarks}
#
# WHAT IT NEVER TOUCHES
#   $REPO/.venv       SHARED — skillsbench and tau2_airline install cap-evolve
#                     core into this same venv. Never removed; you are warned
#                     about it on exit.
#   $REPO/.capevolve  Yours to manage. Holds run_* artifacts (measurements) and
#                     the project dir that skillsbench / tau2_airline / this
#                     example all scaffold into. setup.sh refreshes this
#                     example's files there on every run, so teardown has no
#                     reason to go in at all.
#   $REPO/vendor/     The DIRECTORY itself — examples/skillsbench keeps
#                     vendor/skillsbench inside it. Only this example's own
#                     subdirectories are removed; vendor/ is rmdir'd only if it
#                     ends up empty.
#
# OPTIONS
#   --keep-clones   stop the services but keep the cloned repos
#
#   bash examples/tau2_airline_spa/teardown.sh [--keep-clones]
#
set -uo pipefail

EX_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$EX_DIR/../.." && pwd)"
VENDOR="$REPO/vendor"
CAPEVOLVE="$REPO/.capevolve"

STORE_PORT="${SKILLBERRY_STORE_PORT:-8000}"
ENV_MGR_PORT="${TAU2_ENV_MANAGER_PORT:-8004}"
# SPA's port is fixed at 7000 (tau2 and SPA hardcode it). Stopping SPA's PID also
# releases 7001, its config port, since one process binds both.
SPA_PORT="7000"

# Sentinels written by skillberry-common/scripts/start-service.sh. They hold the
# PID of the process the service itself started, which is a far safer handle than
# "whoever owns the port".
SPA_PID_FILE="/tmp/skillberry-agent-service.pid"
STORE_PID_FILE="/tmp/skillberry-store-service.pid"

DO_CLONES=1

say(){ printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }
warn(){ printf '\033[1;33m  ! %s\033[0m\n' "$*"; }
die(){ printf '\n\033[1;31mTEARDOWN FAILED: %s\033[0m\n' "$*" >&2; exit 1; }

usage(){ sed -n '2,28p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0; }

while [ $# -gt 0 ]; do
  case "$1" in
    --keep-clones) DO_CLONES=0 ;;
    -h|--help)     usage ;;
    *)             die "unknown option: $1 (try --help)" ;;
  esac
  shift
done

# ---------------------------------------------------------------------------
# Guardrails. `set -u` does NOT protect the removals below: these variables are
# always SET, just potentially wrong, so a bad $REPO would aim rm -rf at
# something real.
# ---------------------------------------------------------------------------
[ -d "$REPO/core/cap_evolve" ] \
  || die "$REPO does not look like the cap-evolve checkout (no core/cap_evolve) — refusing to delete anything"

# Remove a path only if it is a real, non-trivial path INSIDE $REPO, and never
# .capevolve or anything under it.
safe_rm(){
  local target="$1" label="$2" resolved parent
  [ -n "$target" ] || { warn "empty path for $label — skipped"; return 1; }
  [ -e "$target" ] || { echo "  - $label not present"; return 0; }
  parent="$(cd "$(dirname "$target")" 2>/dev/null && pwd)" || {
    warn "cannot resolve parent of $target — skipped"; return 1; }
  resolved="$parent/$(basename "$target")"
  case "$resolved" in
    "/"|"$HOME"|"$REPO") die "refusing to remove $resolved ($label)" ;;
    "$CAPEVOLVE"|"$CAPEVOLVE"/*) die "refusing to touch .capevolve ($label)" ;;
    "$REPO/.venv"|"$REPO/.venv"/*) die "refusing to touch the shared venv ($label)" ;;
    "$REPO"/*) : ;;
    *) die "refusing to remove $resolved — outside $REPO ($label)" ;;
  esac
  rm -rf "$resolved" || return 1
  echo "  ✓ removed $label"
}

# ---------------------------------------------------------------------------
# Terminate a PID: SIGTERM, then SIGKILL only if it does not go away.
term_pid(){
  local pid="$1" name="$2"
  kill "$pid" 2>/dev/null || return 1
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    kill -0 "$pid" 2>/dev/null || { echo "  ✓ stopped $name (PID $pid)"; return 0; }
    sleep 1
  done
  kill -9 "$pid" 2>/dev/null || true
  echo "  ✓ killed $name (PID $pid)"
}

# Stop a service via the PID its own sentinel recorded, falling back to the port
# ONLY for a process that matches "$3" — never a blind `kill -9` on whoever holds
# the port. On macOS, port 7000 belongs to ControlCenter (AirPlay Receiver), and
# SIGKILLing a system process because it squats our port is not acceptable.
stop_service(){
  local name="$1" port="$2" pattern="$3" pidfile="${4:-}"
  local pid pids stopped=0

  if [ -n "$pidfile" ] && [ -f "$pidfile" ]; then
    pid=$(head -1 "$pidfile" 2>/dev/null | tr -dc '0-9')
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      term_pid "$pid" "$name" && stopped=1
    fi
    rm -f "$pidfile"
  fi

  if [ "$stopped" -eq 0 ]; then
    # -sTCP:LISTEN: without it lsof also returns CLIENTS of the port (cap-evolve's
    # own runner talks to SPA), which must never be considered the service.
    pids=$(lsof -ti :"$port" -sTCP:LISTEN 2>/dev/null || true)
    for pid in $pids; do
      if ps -p "$pid" -o args= 2>/dev/null | grep -q -- "$pattern"; then
        term_pid "$pid" "$name" && stopped=1
      else
        printf '  ! port %s held by PID %s (%s) — not %s, leaving it alone\n' \
          "$port" "$pid" "$(ps -p "$pid" -o args= 2>/dev/null | head -1)" "$name"
      fi
    done
  fi

  [ "$stopped" -eq 1 ] || echo "  - $name not running (port $port)"
}

# ---------------------------------------------------------------------------
say "1/3  Stop services"
stop_service "skillberry-proxy-agent" "$SPA_PORT"     "-m main"               "$SPA_PID_FILE"
stop_service "skillberry-store"       "$STORE_PORT"   "skillberry_store.main" "$STORE_PID_FILE"
stop_service "tau2-env-manager"       "$ENV_MGR_PORT" "EnvironmentManager"

say "2/3  Remove PID sentinels and logs"
# Sentinels are removed by stop_service; clear them unconditionally in case a
# service died without cleaning up (a stale sentinel blocks the next `make run`).
rm -f "$STORE_PID_FILE" "$SPA_PID_FILE"
rm -f "/tmp/skillberry-agent.log" "/tmp/skillberry-store.log"
rm -f "$REPO/env_manager.log"
echo "  ✓ PID sentinels and log files removed"

if [ "$DO_CLONES" -eq 1 ]; then
  say "3/3  Remove the repos this example cloned"
  for d in skillberry-store skillberry-agent skillberry-benchmarks; do
    safe_rm "$VENDOR/$d" "vendor/$d"
  done
  # vendor/ itself goes only if nothing else lives there — examples/skillsbench
  # keeps vendor/skillsbench.
  if [ -d "$VENDOR" ]; then
    if rmdir "$VENDOR" 2>/dev/null; then
      echo "  ✓ removed empty vendor/"
    else
      echo "  - vendor/ kept (still holds: $(ls -A "$VENDOR" | tr '\n' ' '))"
    fi
  fi
else
  say "3/3  Cloned repos kept (--keep-clones)"
fi

# ---------------------------------------------------------------------------
say "NOT removed — yours to clean up"
warn ".venv was NOT removed: $REPO/.venv"
echo "    It is SHARED — skillsbench and tau2_airline install cap-evolve core into"
echo "    the same venv, so removing it would force them to re-run setup.sh."
echo "    Delete it by hand if you really mean to."
warn ".capevolve was NOT touched: $CAPEVOLVE"
echo "    It holds your run_* artifacts (measurements) and the project dir that"
echo "    skillsbench / tau2_airline / this example all share. setup.sh refreshes"
echo "    this example's files there on every run, so nothing stale survives a"
echo "    re-setup — cleaning it is your call."
if [ -d "$CAPEVOLVE" ]; then
  runs=$(find "$CAPEVOLVE" -maxdepth 1 -type d -name 'run_*' 2>/dev/null | wc -l | tr -d ' ')
  echo "    Currently holds $runs run_* director$([ "$runs" = 1 ] && echo y || echo ies)."
fi

printf '\n\033[1;32mTEARDOWN COMPLETE.\033[0m\n'
