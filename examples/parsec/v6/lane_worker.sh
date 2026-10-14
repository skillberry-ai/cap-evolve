#!/bin/bash
#
# The payload of one lane-worker `bsub` job: build this node's lane, bring the
# parsec stack up once, then run lane_worker.py, which claims trials from the
# shared queue until the queue stays empty, a stop is requested, or the lane
# proves broken. The dispatching adapter (v6/adapters/adapter.py) submits these.
#
# Lane, podman and stack bring-up are the same steps as v5/run_one_eval.sh, in
# the same order and for the same reasons (see the comments there); only the
# hand-off differs: trials instead of a whole `cap-evolve run`.
#
# Usage (normally via the dispatcher, not by hand):
#   export PARSEC_V5N=... LLM_API_KEY=... LLM_API_BASE=... HARNESS_LLM_SIMULATION_MODEL=...
#   export CE_BIN=/path/to/.venv/bin/cap-evolve     # its python runs the worker
#   bash examples/parsec/v6/lane_worker.sh --queue <queue-root> [--idle-exit SEC]
#
# Exit codes: 0 queue drained/stopped, 2 bad usage, 3 lane failed verification or
# proved broken, otherwise parsec_stack.sh's own code.
set -eo pipefail

: "${PARSEC_V5N:?PARSEC_V5N environment variable is required (see parsec_paths.py)}"
: "${LLM_API_KEY:?LLM_API_KEY environment variable is required by parsec_stack.sh up}"
: "${LLM_API_BASE:?LLM_API_BASE environment variable is required by parsec_stack.sh up}"
: "${HARNESS_LLM_SIMULATION_MODEL:?HARNESS_LLM_SIMULATION_MODEL environment variable is required by parsec_stack.sh up}"
: "${CE_BIN:?CE_BIN must point at the cap-evolve CLI; the worker runs under the python of that venv}"

V6_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "$V6_DIR/../../.." && pwd)}"
V5_DIR="$PROJECT_ROOT/examples/parsec/v5"
CCC_DIR="$PROJECT_ROOT/scripts/ccc"
PARSEC_CCC_DIR="$PROJECT_ROOT/examples/parsec/ccc"
PYTHON="$(dirname "$CE_BIN")/python"

QUEUE=""
WORKER_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --queue)     QUEUE="$2"; shift 2 ;;
    --idle-exit) WORKER_ARGS+=(--idle-exit "$2"); shift 2 ;;
    -h|--help)   sed -n '2,20p' "$0"; exit 0 ;;
    *)           echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
[[ -n "$QUEUE" ]] || { echo "usage: lane_worker.sh --queue DIR [--idle-exit SEC]" >&2; exit 2; }

LANE="${V5_LANE:-${LSB_JOBID:-$(hostname -s)}}"
LANES_ROOT="${V5_LANES_ROOT:-$PARSEC_V5N/_run/v5-lanes}"
LANE_DIR="$LANES_ROOT/$LANE"
LANE_LOGS="$LANE_DIR/_v5/logs"

echo "lane worker: host=$(hostname) lane=$LANE queue=$QUEUE job=${LSB_JOBID:-none} start=$(date -Iseconds)"

bash "$V5_DIR/make_lane.sh" "$LANE" || exit 3

export PARSEC_BENCH=v5
export PARSEC_LIVE_ROOT="$LANE_DIR"
export PARSEC_LIVE_PROMPTS_DIR="$LANE_DIR/config/prompts"
export PARSEC_SKILLS_DIR="$LANE_DIR/_v5/skills"
export PARSEC_LOG_DIR="$LANE_LOGS"
export PARSEC_LIVE_LOG="$LANE_LOGS/parsec-live.log"
export PARSEC_SIM_TRACE="$LANE_LOGS/parsec-trace/trace.jsonl"
export PARSEC_LIVE_UV_FLAGS="--no-sync --frozen"
export PYTHONDONTWRITEBYTECODE=1
mkdir -p "$(dirname "$PARSEC_SIM_TRACE")"

STACK_UP=false
teardown_stack() {
  if [[ "$STACK_UP" == true ]]; then
    bash "$PARSEC_CCC_DIR/parsec_stack.sh" down || true
  fi
  # setup_podman.sh starts `podman system service --time=0` and a session
  # dbus-daemon, and neither ever exits; LSF keeps the job (and its node) RUNning
  # until every process in it is gone, so an idle worker would hold its node
  # forever. The node is this job's alone (one worker per host), so stopping
  # every such process of ours on it is safe.
  local uid
  uid="$(id -u)"
  echo "teardown: removing task containers, stopping podman service and session dbus of uid $uid"
  # Harbor's per-trial task containers outlive their trials; their conmon parents
  # are this job's processes too.
  podman ps -aq --filter name=__env- 2>/dev/null | xargs -r podman rm -f >/dev/null 2>&1 || true
  pkill -u "$uid" -x conmon 2>/dev/null || true
  pkill -u "$uid" -f "^podman system service --time=0 unix:///tmp/podman-run-$uid/" 2>/dev/null || true
  pkill -u "$uid" -f "^dbus-daemon --session --address=unix:path=/tmp/podman-run-$uid/" 2>/dev/null || true
  pkill -u "$uid" -x catatonit 2>/dev/null || true
  sleep 1
  echo "teardown: still running: $(pgrep -u "$uid" -fa 'podman|dbus-daemon|catatonit' | tr '\n' ';' || true)"
}
trap teardown_stack EXIT

# shellcheck source=/dev/null
source "$CCC_DIR/setup_podman.sh"
if [[ -x "$HOME/.local/bin/docker" ]]; then
  export PATH="$HOME/.local/bin:${PATH/#$HOME\/.local\/bin:/}"
fi
export PATH="$HOME/.local/bin:$PATH"          # harbor

SIM_IMAGE="${PARSEC_SIM_IMAGE:-simulation-harness:bench}"
SIM_TAR="${V5_SIM_IMAGE_TAR:-/dccstor/knewedge2/boazc/workarea/python/simulation-harness-bench.tar}"
if ! podman image exists "$SIM_IMAGE"; then
  [[ -f "$SIM_TAR" ]] || { echo "FATAL: $SIM_IMAGE absent and no tarball at $SIM_TAR" >&2; exit 2; }
  podman load -i "$SIM_TAR"
fi

STACK_UP=true
set +e
bash "$PARSEC_CCC_DIR/parsec_stack.sh" up
UP_RC=$?
set -e
(( UP_RC == 2 )) && STACK_UP=false
if (( UP_RC != 0 )); then
  echo "FATAL: parsec_stack.sh up failed (rc=$UP_RC)" >&2
  exit "$UP_RC"
fi
bash "$PARSEC_CCC_DIR/parsec_stack.sh" status

export PYTHONPATH="$PROJECT_ROOT/core:$PROJECT_ROOT${PYTHONPATH:+:$PYTHONPATH}"
set +e
"$PYTHON" "$V6_DIR/lane_worker.py" --queue "$QUEUE" "${WORKER_ARGS[@]}"
RC=$?
set -e
echo "lane worker finished rc=$RC end=$(date -Iseconds)"
exit "$RC"
