#!/bin/bash
#
# Bring up/down/health-check parsec v4's stack. Two different kinds of thing:
#   * the 5 MCP simulation harnesses (platform/github/icinga/cost/cloud) are
#     podman CONTAINERS of the `simulation-harness:bench` image — one per
#     service, internal port always 8086, published 8086-8090;
#   * `parsec-live` is a HOST process (`uv run uvicorn`), pid-file tracked.
# See docs/how-to/ccc/CCC_PODMAN_SETUP.md's "Parsec v4 (v4_t2_e1)" section.
#
# `up` requires the simulators' LLM credentials to be ALREADY EXPORTED by the
# caller: LLM_API_KEY, LLM_API_BASE, HARNESS_LLM_SIMULATION_MODEL. It does not
# read any local config file for them, and it does not build
# `simulation-harness:bench` — building that image is one-time setup, so `up`
# fails with a clear error naming the image if it is missing.
#
# Usage:
#   export PARSEC_V4N=/path/to/rhdp-parsec/v4_2026-09-16
#   bash scripts/ccc/parsec_stack.sh up       # start all 6, then activate the 5 sims
#   bash scripts/ccc/parsec_stack.sh status   # read-only: TCP + simulation `ready`
#   bash scripts/ccc/parsec_stack.sh down     # stop+remove containers, stop parsec-live
#   bash scripts/ccc/parsec_stack.sh reap     # force-remove/kill anything on our ports
#
# Exits non-zero if $PARSEC_V4N is unset, if any of `up`'s preconditions are
# unmet, if a sim's activation POST never returns 2xx/409, or (for `status`) if
# any port isn't accepting connections or a simulation isn't `ready` in budget.

set -eo pipefail

usage() {
  sed -n '2,25p' "$0"
  exit 2
}

CMD="${1:-}"
case "$CMD" in
  -h|--help) usage ;;
  "")        usage ;;
esac

: "${PARSEC_V4N:?PARSEC_V4N environment variable is required (see parsec_paths.py)}"

# Host-scoped: $PARSEC_V4N is on shared GPFS, so an unscoped pid dir would let
# host A's recorded pid be `kill -0`-tested against host B's process table —
# a false "already running" that silently skips starting parsec-live.
PID_DIR="$PARSEC_V4N/_run/logs/pids/$(hostname -s)"
LOG_DIR="$PARSEC_V4N/_run/logs/sims"
mkdir -p "$PID_DIR" "$LOG_DIR"

# Container runtime and image. The image is built once, out of band, from the
# separate `simulation-harness` git repo; this script only ever consumes it.
CRI="${PARSEC_CONTAINER_CLI:-podman}"
SIM_IMAGE="${PARSEC_SIM_IMAGE:-simulation-harness:bench}"
# One skills-store mount shared by all five: each writes only its own
# parsec-<service>/ subdirectory, so they never collide.
SKILLS_DIR="$PARSEC_V4N/_run/skills"

# Must be the SAME path adapter.py passes to the Harbor container, or the agent
# reads an empty trace: adapter.py's default is
# $PARSEC_V4N/_run/logs/parsec-trace/trace.jsonl (it uses setdefault, so an
# exported value here is honoured there too).
PARSEC_SIM_TRACE="${PARSEC_SIM_TRACE:-$PARSEC_V4N/_run/logs/parsec-trace/trace.jsonl}"

# name:published_port:kind. The port numbers are the single source of truth in
# scripts/v4_t2_e1/common/parsec_paths.py's MCP_PORTS — change them there.
SERVICES=(
  "platform:8086:sim"
  "github:8087:sim"
  "icinga:8088:sim"
  "cost:8089:sim"
  "cloud:8090:sim"
  "parsec-live:8000:live"
)

SIM_INTERNAL_PORT=8086
WAIT_BUDGET=60

banner() {
  printf '\n============================================================\n'
  printf '%s\n' "$1"
  printf '============================================================\n'
}

container_name() { printf 'parsec-sim-%s\n' "$1"; }

port_open() {
  local port="$1"
  # fd 3 is opened inside the subshell, so the subshell's exit closes it —
  # there is nothing left open in this shell to clean up afterwards.
  (exec 3<>"/dev/tcp/127.0.0.1/$port") 2>/dev/null
}

wait_port() {
  local name="$1" port="$2" deadline=$((SECONDS + WAIT_BUDGET))
  until port_open "$port"; do
    if (( SECONDS >= deadline )); then
      echo "FATAL: $name (port $port) never opened within ${WAIT_BUDGET}s" >&2
      return 1
    fi
    sleep 1
  done
}

# POST /api/v1/simulation/start with {"name": "parsec-<svc>"} against this
# instance's own published port. A harness process hosts at most one
# simulation, so a second start returns 409 — which means "already activated",
# so 2xx and 409 are both success here and nothing else is.
#
# Retried within WAIT_BUDGET, and deliberately NOT `|| true`: under rootless
# podman the published port is accepted by the port-forwarder as soon as
# `run -d` returns, which can precede the harness inside actually binding
# $SIM_INTERNAL_PORT — so wait_port can report success while the app is not yet
# serving and a single POST would be refused. Swallowing that (or a 404/422/5xx)
# made `up` exit 0 having activated nothing, and the operator learned ~60s later
# only that the harness was "unactivated", with no link back to the failed POST.
activate_sim() {
  local name="$1" port="$2" code
  local deadline=$((SECONDS + WAIT_BUDGET))
  while :; do
    # %{http_code} is "000" when the request got no response at all
    # (connection refused, reset, timeout) — distinguishable in the message.
    code="$(curl -o /dev/null -s -w '%{http_code}' \
                 -X POST "http://127.0.0.1:$port/api/v1/simulation/start" \
                 -H 'content-type: application/json' \
                 -d "{\"name\": \"parsec-$name\"}" 2>/dev/null || true)"
    case "$code" in
      2??|409) return 0 ;;
    esac
    if (( SECONDS >= deadline )); then
      echo "FATAL: could not activate simulation parsec-$name (port $port)" \
           "within ${WAIT_BUDGET}s — last HTTP status: ${code:-<none>}" \
           "(000 = no response at all: the harness inside the container is not" \
           "serving yet, or the container exited — check" \
           "'$CRI logs $(container_name "$name")')" >&2
      return 1
    fi
    sleep 2
  done
}

# Readiness must be the TOP-LEVEL `status`, not some nested per-component or
# per-skill status field: a false "ready" is precisely the silent-wrong-data
# failure this check exists to close, so a bare substring grep is too loose.
# jq is not a dependency of this repo's scripts (grep: zero other uses), so it
# is used only when present; the fallback anchors the match to the start of the
# JSON object, before any nested object can open ([^{}] cannot cross a brace),
# which can only err toward a timeout — never toward a false ready.
sim_ready() {
  local port="$1" body
  body="$(curl -fsS "http://127.0.0.1:$port/api/v1/simulation" 2>/dev/null)" || return 1
  # An empty body is NOT ready: `jq -e` on empty input produces no output and
  # exits 0, which would otherwise read as ready (verified).
  [[ -n "$body" ]] || return 1
  if command -v jq >/dev/null 2>&1; then
    printf '%s' "$body" | jq -e '.status == "ready"' >/dev/null 2>&1
  else
    printf '%s' "$body" | tr -d '[:space:]' | grep -q '^{[^{}]*"status":"ready"'
  fi
}

wait_sim_ready() {
  local name="$1" port="$2" deadline=$((SECONDS + WAIT_BUDGET))
  until sim_ready "$port"; do
    if (( SECONDS >= deadline )); then
      echo "FATAL: $name (port $port) is listening but its simulation never" \
           "reported status=ready within ${WAIT_BUDGET}s — an unactivated or" \
           "unseeded harness answers TCP while serving no tools" >&2
      return 1
    fi
    sleep 2
  done
}

start_sim() {
  local name="$1" port="$2"
  local cname
  cname="$(container_name "$name")"
  if "$CRI" container exists "$cname" 2>/dev/null; then
    if [[ "$("$CRI" inspect -f '{{.State.Running}}' "$cname" 2>/dev/null)" == "true" ]]; then
      echo "$name already running (container $cname)"
      return 0
    fi
    "$CRI" rm -f "$cname" >/dev/null 2>&1 || true
  fi
  "$CRI" run -d --name "$cname" \
    -p "127.0.0.1:$port:$SIM_INTERNAL_PORT" \
    -e "LLM_API_KEY=$LLM_API_KEY" \
    -e "LLM_API_BASE=$LLM_API_BASE" \
    -e "HARNESS_LLM_SIMULATION_MODEL=$HARNESS_LLM_SIMULATION_MODEL" \
    -e "HARNESS_SKILLS_FOLDER=/app/skills-store" \
    -e "HARNESS_AUTOSTART_ENABLED=false" \
    -e "HARNESS_SESSIONS_IDLE_TIMEOUT_SECONDS=86400" \
    -v "$SKILLS_DIR:/app/skills-store:z" \
    "$SIM_IMAGE" >/dev/null
  echo "started $name (container $cname, published port $port -> $SIM_INTERNAL_PORT)"
}

start_live() {
  local name="$1" port="$2"
  local pid_file="$PID_DIR/$name.pid"
  if [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
    echo "$name already running (pid $(cat "$pid_file"))"
    return 0
  fi
  mkdir -p "$(dirname "$PARSEC_SIM_TRACE")"
  # --host 127.0.0.1, never 0.0.0.0: a CCC compute node is shared, and the
  # Harbor container reaches this over host networking, not over the LAN.
  # PARSEC_SIM=1 is what makes parsec-live redirect tool calls to the
  # simulators at all — unset means it talks to real backends and produces
  # confidently wrong rewards. MLFLOW_TRACKING_URI= (empty) suppresses a
  # startup warning path. See README.md's "Start it" block.
  ( cd "$PARSEC_V4N/_run/parsec-live" && \
    PARSEC_SIM=1 \
    PARSEC_SIM_TRACE="$PARSEC_SIM_TRACE" \
    PARSEC_SIM_TIMEOUT="${PARSEC_SIM_TIMEOUT:-240}" \
    MLFLOW_TRACKING_URI= \
    exec nohup uv run uvicorn src.app:app --host 127.0.0.1 --port "$port" \
      > "$LOG_DIR/$name.log" 2>&1 & echo $! > "$pid_file" )
  echo "started $name (pid $(cat "$pid_file"), port $port, log $LOG_DIR/$name.log)"
  echo "  PARSEC_SIM=1 PARSEC_SIM_TRACE=$PARSEC_SIM_TRACE"
}

stop_sim() {
  local name="$1"
  local cname
  cname="$(container_name "$name")"
  if "$CRI" container exists "$cname" 2>/dev/null; then
    "$CRI" rm -f "$cname" >/dev/null 2>&1 || true
    echo "removed $name (container $cname)"
  else
    echo "$name: no container $cname, nothing to stop"
  fi
}

stop_live() {
  local name="$1" port="$2"
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
  # start_live records the pid of `uv`, not of the `uvicorn` child it launches.
  # Current `uv` forwards SIGTERM, but if it ever failed to, the port would stay
  # held with no pid file left: the next `up` would write a fresh pid file,
  # start_live would report success, and `status` would see port $port open (the
  # STALE process) and report OK — the "next job silently reuses a stale,
  # wrongly-seeded stack" failure run_ccc_parsec.sh's EXIT trap exists to
  # prevent. So verify the port was actually released and, if not, fall back to
  # the same port-based kill `reap` does. Never a bare kill of an unverified pid.
  #
  # Deliberately lsof, not port_open, to decide this: port_open *connects*, and a
  # process that is wedged holding the port while never calling accept() fills
  # its listen backlog after a few probes, after which connect() blocks — which
  # would hang `down`, and `down` runs from run_ccc_parsec.sh's EXIT trap on
  # every job. lsof only reads the socket table, so it cannot block. If lsof is
  # unavailable, or the holder is another user's process (invisible to a
  # non-root lsof), this degrades to a no-op, same as `reap`.
  local waited=0 pids=""
  while (( waited < 5 )); do
    pids="$(lsof -t -i ":$port" -sTCP:LISTEN 2>/dev/null || true)"
    [[ -n "$pids" ]] || break
    sleep 1
    waited=$((waited + 1))
  done
  if [[ -n "$pids" ]]; then
    printf '%s\n' "$pids" | xargs -r -n1 kill 2>/dev/null || true
    echo "$name: port $port still held after the pid kill — killed by port" \
         "(pids $(printf '%s' "$pids" | tr '\n' ' '))"
  fi
}

require_up_preconditions() {
  local missing=()
  local var
  for var in LLM_API_KEY LLM_API_BASE HARNESS_LLM_SIMULATION_MODEL; do
    [[ -n "${!var:-}" ]] || missing+=("$var")
  done
  if (( ${#missing[@]} )); then
    echo "FATAL: the simulator containers need these exported by the caller," \
         "and they are unset or empty: ${missing[*]}" >&2
    echo "  (export them in your shell or LSF job script; this script" \
         "deliberately reads no local config file for credentials)" >&2
    exit 2
  fi
  if ! command -v "$CRI" >/dev/null 2>&1; then
    echo "FATAL: container runtime '$CRI' not on PATH (override with PARSEC_CONTAINER_CLI)" >&2
    exit 2
  fi
  if ! "$CRI" image exists "$SIM_IMAGE" 2>/dev/null; then
    echo "FATAL: image '$SIM_IMAGE' not present — build it once from the" \
         "separate simulation-harness repo (see CCC_PODMAN_SETUP.md); this" \
         "script does not build it" >&2
    exit 2
  fi
  if [[ ! -d "$SKILLS_DIR" ]]; then
    echo "FATAL: skills store '$SKILLS_DIR' does not exist — unpack the five" \
         "parsec-<service> skill bundles into it before starting the sims" >&2
    exit 2
  fi
}

case "$CMD" in
  up)
    banner "starting parsec v4 stack under $PARSEC_V4N"
    require_up_preconditions
    for entry in "${SERVICES[@]}"; do
      IFS=: read -r name port kind <<< "$entry"
      if [[ "$kind" == "sim" ]]; then
        start_sim "$name" "$port"
      else
        start_live "$name" "$port"
      fi
    done
    banner "activating the 5 simulations"
    for entry in "${SERVICES[@]}"; do
      IFS=: read -r name port kind <<< "$entry"
      [[ "$kind" == "sim" ]] || continue
      wait_port "$name" "$port" || exit 1
      activate_sim "$name" "$port" || exit 1
      echo "activated simulation parsec-$name on port $port"
    done
    echo
    echo "Now run: bash $0 status"
    ;;
  down)
    banner "stopping parsec v4 stack"
    for entry in "${SERVICES[@]}"; do
      IFS=: read -r name port kind <<< "$entry"
      if [[ "$kind" == "sim" ]]; then
        stop_sim "$name"
      else
        stop_live "$name" "$port"
      fi
    done
    ;;
  reap)
    # Belt-and-suspenders teardown: force-remove our containers by name, then
    # kill whatever is still actually listening on our 6 ports regardless of
    # pid files or container records (covers an orphan left by a job killed
    # mid-startup). Never sends a bare kill to a pid we didn't look up by port.
    banner "reaping parsec v4's containers and anything on its 6 ports"
    for entry in "${SERVICES[@]}"; do
      IFS=: read -r name port kind <<< "$entry"
      if [[ "$kind" == "sim" ]]; then
        cname="$(container_name "$name")"
        if "$CRI" container exists "$cname" 2>/dev/null; then
          "$CRI" rm -f "$cname" >/dev/null 2>&1 || true
          echo "reaped container $cname"
        fi
      fi
      # lsof can return several pids, one per line; `kill "$multiline"` kills
      # none of them and exits 1, so feed them to kill one at a time.
      pids="$(lsof -t -i ":$port" -sTCP:LISTEN 2>/dev/null || true)"
      if [[ -n "$pids" ]]; then
        printf '%s\n' "$pids" | xargs -r -n1 kill 2>/dev/null || true
        echo "reaped $name (port $port, pids $(printf '%s' "$pids" | tr '\n' ' '))"
      fi
    done
    rm -f "$PID_DIR"/*.pid
    ;;
  status)
    banner "waiting for parsec v4 stack health (max ${WAIT_BUDGET}s per check)"
    for entry in "${SERVICES[@]}"; do
      IFS=: read -r name port kind <<< "$entry"
      wait_port "$name" "$port" || exit 1
      if [[ "$kind" == "sim" ]]; then
        # A bare TCP check cannot tell an unactivated, unseeded harness from a
        # working one, and that failure mode scores as wrong data rather than
        # an error — so require the simulation itself to report ready.
        wait_sim_ready "$name" "$port" || exit 1
        echo "OK: $name (port $port) simulation parsec-$name is ready"
      else
        # parsec-live has no documented equivalent "ready" endpoint here; TCP
        # accept is the check we have.
        echo "OK: $name (port $port) is accepting connections"
      fi
    done
    ;;
  *)
    echo "Unknown command: $CMD" >&2
    usage
    ;;
esac
