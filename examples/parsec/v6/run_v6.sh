#!/bin/bash
#
# Run (or resume) the v6 optimization: stock cap-evolve hill-climb on one
# project, with every evaluation fanned out to LSF lane workers by the
# dispatching adapter. This process runs the optimizer and the gate only; it
# brings up no stack of its own, so it can share a node.
#
# Submit it as its own LSF job (--submit) rather than running it from an
# interactive session: a driver started inside a login session dies with that
# session, and with it the whole run.
#
# Usage:
#   source ~/.v5_g2e1_env.sh        # PARSEC_V5N, LLM_API_KEY/BASE, HARNESS_LLM_SIMULATION_MODEL, CE_BIN
#   bash examples/parsec/v6/run_v6.sh --suite-id g2_e1 --max-iterations 1 --submit
#   bash examples/parsec/v6/run_v6.sh --suite-id g2_e1 --max-iterations 2 --run-ts <ts> --resume --submit
#
# --max-iterations is the run's cumulative budget on --resume (cap-evolve's own
# semantics), so raising it by one and resuming runs exactly one more iteration.
#
# Optional env: V6_MAX_WORKERS (15), V6_WORKER_IDLE_EXIT (600), V6_MAX_ATTEMPTS (3),
# V6_DRIVER_MEM (64G), CCC_LOGS (~/ccc_logs). The dashboard listens on the driver's
# node at port 7878; reach it with  ssh -L 7878:<node>:7878 <login-node>.
set -eo pipefail

: "${PARSEC_V5N:?PARSEC_V5N environment variable is required}"
: "${LLM_API_KEY:?LLM_API_KEY environment variable is required by the lane workers}"
: "${LLM_API_BASE:?LLM_API_BASE environment variable is required by the lane workers}"
: "${HARNESS_LLM_SIMULATION_MODEL:?HARNESS_LLM_SIMULATION_MODEL environment variable is required}"
: "${CE_BIN:?CE_BIN must point at the cap-evolve CLI}"

V6_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$V6_DIR/../../.." && pwd)"

SUITE_ID=""
MAX_ITERATIONS=""
RUN_TS=""
RESUME=false
SUBMIT=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --suite-id)        SUITE_ID="$2"; shift 2 ;;
    --max-iterations)  MAX_ITERATIONS="$2"; shift 2 ;;
    --run-ts)          RUN_TS="$2"; shift 2 ;;
    --resume)          RESUME=true; shift ;;
    --submit)          SUBMIT=true; shift ;;
    -h|--help)         sed -n '2,26p' "$0"; exit 0 ;;
    *)                 echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
[[ -n "$SUITE_ID" && -n "$MAX_ITERATIONS" ]] || {
  echo "usage: run_v6.sh --suite-id ID --max-iterations N [--run-ts TS --resume] [--submit]" >&2; exit 2; }

PROJECT_DIR=".capevolve/v6_${SUITE_ID}/project"
[[ -f "$PROJECT_ROOT/$PROJECT_DIR/capevolve.yaml" ]] || {
  echo "no project at $PROJECT_ROOT/$PROJECT_DIR — run scaffold_project.py first" >&2; exit 2; }
[[ -f "$PROJECT_ROOT/.env" ]] || { echo "no $PROJECT_ROOT/.env (the optimizer credentials)" >&2; exit 2; }

if [[ "$SUBMIT" == true ]]; then
  LOGS="${CCC_LOGS:-$HOME/ccc_logs}"
  mkdir -p "$LOGS"
  args=(--suite-id "$SUITE_ID" --max-iterations "$MAX_ITERATIONS")
  [[ -n "$RUN_TS" ]] && args+=(--run-ts "$RUN_TS")
  [[ "$RESUME" == true ]] && args+=(--resume)
  bsub -q "${V6_LSF_QUEUE:-normal}" -M "${V6_DRIVER_MEM:-64G}" -n 1 -J "v6d_${SUITE_ID}" \
       -oo "$LOGS/%J.stdout" -eo "$LOGS/%J.stderr" bash "$0" "${args[@]}"
  exit $?
fi

PROJ_ABS="$PROJECT_ROOT/$PROJECT_DIR"
export PARSEC_BENCH=v5
export PARSEC_JOBS_SUITE="v6_${SUITE_ID}"
export V6_QUEUE_ROOT="$PARSEC_V5N/_run/v6-queue/v6_${SUITE_ID}"
export V6_PUBLIC_TASKS="$PROJ_ABS/public_tasks.txt"
export V6_SEALED_JOBS_ROOT="$PROJ_ABS.sealed/jobs"
export PYTHONPATH="$PROJECT_ROOT/core:$PROJECT_ROOT${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p "$V6_QUEUE_ROOT" "$V6_SEALED_JOBS_ROOT"

echo "v6 driver: suite=$SUITE_ID host=$(hostname) job=${LSB_JOBID:-none} start=$(date -Iseconds)"
echo "  queue=$V6_QUEUE_ROOT sealed jobs=$V6_SEALED_JOBS_ROOT workers<=${V6_MAX_WORKERS:-15}"

ARGS=(--suite-id "v6_$SUITE_ID" --run-id "$SUITE_ID" --max-iterations "$MAX_ITERATIONS"
      --spec "$PROJECT_DIR/capevolve.yaml" --project "$PROJECT_DIR")
[[ -n "$RUN_TS" ]] && ARGS+=(--run-ts "$RUN_TS")
[[ "$RESUME" == true ]] && ARGS+=(--resume)
cd "$PROJECT_ROOT"

# run_ccc_experiment.sh's own Phase 1 runs setup_podman.sh unconditionally, even
# though this driver never brings up the parsec stack itself (evaluation is
# dispatched to lane workers) -- it starts a podman service and a session
# dbus-daemon that never exit on their own. Without stopping them LSF never
# leaves this job RUNning after the script returns, exactly the leak
# lane_worker.sh had to fix. This node is this job's alone, so stopping them
# unconditionally on exit is safe.
cleanup_podman() {
  local uid
  uid="$(id -u)"
  pkill -u "$uid" -f "^podman system service --time=0 unix:///tmp/podman-run-$uid/" 2>/dev/null || true
  pkill -u "$uid" -f "^dbus-daemon --session --address=unix:path=/tmp/podman-run-$uid/" 2>/dev/null || true
  pkill -u "$uid" -x catatonit 2>/dev/null || true
}
trap cleanup_podman EXIT

set +e
bash scripts/ccc/run_ccc_experiment.sh "${ARGS[@]}"
RC=$?
set -e
# Workers exit by themselves once idle; ask them to stop now so none outlives the driver.
"$(dirname "$CE_BIN")/python" -c "import sys; sys.path.insert(0, '$V6_DIR'); \
from lane_queue import LaneQueue; LaneQueue('$V6_QUEUE_ROOT').request_stop()" || true
echo "v6 driver finished rc=$RC end=$(date -Iseconds)"
exit "$RC"
