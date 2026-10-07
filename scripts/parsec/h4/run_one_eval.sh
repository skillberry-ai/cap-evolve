#!/bin/bash
#
# Evaluate ONE artifact on ONE parsec v4 task, in its own LANE, on this host.
# This is the payload a single `bsub` job runs; fan_out.sh submits N of them,
# one per task, each pinned to its own compute node.
#
# It does only what run_ccc_experiment.sh cannot do for itself — set up the
# lane, bring parsec's simulator stack up and tear it down — then hands off to
# run_ccc_experiment.sh unmodified, exactly as run_ccc_parsec_g2.sh does for
# the joint 34-task run.
#
# Why one host per job, and why no port offsetting: podman's graphroot is
# per-UID-per-host (/tmp/podman-$UID), so two jobs on one node corrupt each
# other's image store. Given one node per job, all six services bind the
# default ports on 127.0.0.1 with no collision — and that is the only scheme
# that works, because install_seeds.py hardcodes localhost and those ports.
#
# Usage:
#   export PARSEC_V4N=/path/to/rhdp-parsec/v4_2026-09-16
#   export LLM_API_KEY=...  LLM_API_BASE=https://your-gateway
#   export HARNESS_LLM_SIMULATION_MODEL=azure/gpt-5.4
#   bash scripts/parsec/h4/run_one_eval.sh --suite-id base01 --task-id <task>
#
# Optional env:
#   H4_LANE             lane id (default: $LSB_JOBID, else short hostname)
#   H4_LANES_ROOT       where lanes live (default: $PARSEC_V4N/_run/h4-lanes)
#   H4_SIM_IMAGE_TAR    podman-save tarball to load when the image is absent
#
# Extra arguments are forwarded verbatim to run_ccc_experiment.sh.
#
# Exit codes:
#   0  evaluation completed (read results/<suite>/<run-id>/run/baseline.json)
#   2  bad usage / project not scaffolded
#   3  lane failed verification — nothing was evaluated
#   *  parsec_stack.sh's or run_ccc_experiment.sh's own exit code
set -eo pipefail

: "${PARSEC_V4N:?PARSEC_V4N environment variable is required (see parsec_paths.py)}"
: "${LLM_API_KEY:?LLM_API_KEY environment variable is required by parsec_stack.sh up (the simulators LLM credentials)}"
: "${LLM_API_BASE:?LLM_API_BASE environment variable is required by parsec_stack.sh up}"
: "${HARNESS_LLM_SIMULATION_MODEL:?HARNESS_LLM_SIMULATION_MODEL environment variable is required by parsec_stack.sh up}"

H4_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -z "${PROJECT_ROOT:-}" ]]; then
  PROJECT_ROOT="$(cd "$H4_DIR/../../.." && pwd)"
fi
CCC_DIR="$PROJECT_ROOT/scripts/ccc"

SUITE_ID=""
TASK_ID_ARG=""
LANE=""
DRY_RUN=false
PASSTHRU=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --suite-id)  SUITE_ID="$2"; shift 2 ;;
    --task-id)   TASK_ID_ARG="$2"; shift 2 ;;
    --lane)      LANE="$2"; shift 2 ;;
    --dry-run)   DRY_RUN=true; shift ;;
    -h|--help)   sed -n '2,33p' "$0"; exit 0 ;;
    *)           PASSTHRU+=("$1"); shift ;;
  esac
done

if [[ -z "$SUITE_ID" || -z "$TASK_ID_ARG" ]]; then
  echo "usage: run_one_eval.sh --suite-id ID --task-id TASK [--lane L] [--dry-run]" >&2
  exit 2
fi

PROJECT_DIR=".capevolve/h4_${SUITE_ID}_${TASK_ID_ARG}/project"
SPEC="$PROJECT_DIR/capevolve.yaml"
if [[ ! -f "$PROJECT_ROOT/$SPEC" ]]; then
  echo "ERROR: $PROJECT_ROOT/$SPEC not found — scaffold it first:" >&2
  echo "  python3 scripts/parsec/h4/scaffold_eval_projects.py --suite-id $SUITE_ID --artifact <dir>" >&2
  exit 2
fi

# One lane per concurrent job. $LSB_JOBID is the natural id under LSF: it is
# unique per job, so two jobs that land on one host (which should not happen,
# but -m is a request and not a guarantee) still get separate lanes.
if [[ -z "$LANE" ]]; then
  LANE="${H4_LANE:-${LSB_JOBID:-$(hostname -s)}}"
fi

LANES_ROOT="${H4_LANES_ROOT:-$PARSEC_V4N/_run/h4-lanes}"
LANE_DIR="$LANES_ROOT/$LANE"
LANE_LOGS="$LANE_DIR/_h4/logs"

banner() {
  printf '\n============================================================\n'
  printf '%s\n' "$1"
  printf '============================================================\n'
}

banner "parsec v4 h4 eval — suite=$SUITE_ID task=$TASK_ID_ARG"
echo "Host:          $(hostname)"
echo "Start:         $(date -Iseconds)"
echo "PROJECT_ROOT:  $PROJECT_ROOT"
echo "PARSEC_V4N:    $PARSEC_V4N"
echo "Lane:          $LANE  ($LANE_DIR)"
echo "PROJECT_DIR:   $PROJECT_DIR"
[[ -n "${LSB_JOBID:-}" ]] && echo "LSF job:       $LSB_JOBID"

if [[ "$DRY_RUN" == true ]]; then
  echo
  echo "[dry-run] would build/verify lane, bring the stack up, then run:"
  echo "  bash $CCC_DIR/run_ccc_experiment.sh --suite-id h4_$SUITE_ID \\"
  echo "       --max-iterations 0 --spec $SPEC --project $PROJECT_DIR"
  exit 0
fi

# ---------------------------------------------------------------------------
# Lane. Built and verified BEFORE the stack comes up: if the lane is wrong,
# parsec-live would serve the shared bundle instead of this artifact and the
# sweep would record confidently wrong rewards with no error anywhere.
# ---------------------------------------------------------------------------
banner "Lane setup"
bash "$H4_DIR/make_lane.sh" "$LANE" || exit 3

# These six are what make the lane a lane. parsec_stack.sh and adapter.py read
# the SAME variables, which is what keeps the writer and the reader pointed at
# one path: PARSEC_SIM_TRACE is handed both to parsec-live (which appends to it)
# and to the Harbor container (which reads the trajectory back out of it), and
# PARSEC_LIVE_LOG must name the file parsec_stack.sh actually writes or the
# cost-attribution window silently sums zero.
export PARSEC_LIVE_ROOT="$LANE_DIR"
export PARSEC_LIVE_PROMPTS_DIR="$LANE_DIR/config/prompts"
export PARSEC_SKILLS_DIR="$LANE_DIR/_h4/skills"
export PARSEC_LOG_DIR="$LANE_LOGS"
export PARSEC_LIVE_LOG="$LANE_LOGS/parsec-live.log"
export PARSEC_SIM_TRACE="$LANE_LOGS/parsec-trace/trace.jsonl"
# A lane's .venv is a symlink to the one shared venv; `uv run` syncs the project
# environment before exec'ing, so N lanes starting at once would each sync the
# same venv through their own symlink.
export PARSEC_LIVE_UV_FLAGS="--no-sync --frozen"
# .pyc for lane/src would be written into the SHARED src/__pycache__.
export PYTHONDONTWRITEBYTECODE=1

mkdir -p "$(dirname "$PARSEC_SIM_TRACE")"
echo "  PARSEC_LIVE_ROOT      = $PARSEC_LIVE_ROOT"
echo "  PARSEC_LIVE_PROMPTS_DIR = $PARSEC_LIVE_PROMPTS_DIR"
echo "  PARSEC_SKILLS_DIR     = $PARSEC_SKILLS_DIR"
echo "  PARSEC_LIVE_LOG       = $PARSEC_LIVE_LOG"
echo "  PARSEC_SIM_TRACE      = $PARSEC_SIM_TRACE"

# ---------------------------------------------------------------------------
# Podman. Must be up before parsec_stack.sh, which starts containers.
# run_ccc_experiment.sh does its own Phase 1 later; sourcing here as well is
# what run_v4g2e1_iter.sh does, and is idempotent.
# ---------------------------------------------------------------------------
banner "Podman setup"
# shellcheck source=/dev/null
source "$CCC_DIR/setup_podman.sh"
if [[ -x "$HOME/.local/bin/docker" ]]; then
  export PATH="$HOME/.local/bin:${PATH/#$HOME\/.local\/bin:/}"
fi
podman info --format '{{.Host.RemoteSocket.Path}}' || true
echo "DOCKER_HOST=${DOCKER_HOST:-<unset>}"

# Podman storage is per-host, so an image built on one node is invisible on the
# next. Every fresh node in the sweep needs the tarball loaded once.
SIM_IMAGE="${PARSEC_SIM_IMAGE:-simulation-harness:bench}"
SIM_TAR="${H4_SIM_IMAGE_TAR:-/dccstor/knewedge2/boazc/workarea/python/simulation-harness-bench.tar}"
if ! podman image exists "$SIM_IMAGE"; then
  if [[ ! -f "$SIM_TAR" ]]; then
    echo "FATAL: $SIM_IMAGE absent on $(hostname -s) and no tarball at $SIM_TAR." >&2
    echo "       Build it once with build_sim_harness.sh, or set H4_SIM_IMAGE_TAR." >&2
    exit 2
  fi
  echo "$SIM_IMAGE not on this host; loading from $SIM_TAR"
  podman load -i "$SIM_TAR"
fi
podman images "$SIM_IMAGE"

# ---------------------------------------------------------------------------
# Stack. Armed before `up` and disarmed only on rc=2, so a signal received
# during up's wait_port/activation retries still tears the stack down — a
# dying LSF job must not leave 5 containers and parsec-live holding
# 8000/8086-8090 on a shared node.
# ---------------------------------------------------------------------------
banner "Bringing up the parsec stack (lane $LANE)"
STACK_UP=false
teardown_stack() {
  [[ "$STACK_UP" == true ]] || return 0
  bash "$CCC_DIR/parsec_stack.sh" down || true
}
trap teardown_stack EXIT
STACK_UP=true
set +e
bash "$CCC_DIR/parsec_stack.sh" up
UP_RC=$?
set -e
if (( UP_RC == 2 )); then
  STACK_UP=false
fi
if (( UP_RC != 0 )); then
  echo "FATAL: parsec_stack.sh up failed (rc=$UP_RC)" >&2
  exit "$UP_RC"
fi
# Not a bare port check: an unactivated harness accepts connections and answers
# /healthz while serving no tools, so `status` polls for simulation `ready`.
bash "$CCC_DIR/parsec_stack.sh" status

# ---------------------------------------------------------------------------
# Evaluate. The shared adapter is symlinked into every project and takes no
# constructor arguments, so $TASK_ID is the only way it can tell which task it
# is running.
# ---------------------------------------------------------------------------
export TASK_ID="$TASK_ID_ARG"
banner "Handing off to run_ccc_experiment.sh (--max-iterations 0)"
# --run-id is the TASK, not $LSB_JOBID (run_ccc_experiment.sh's default). An h4
# sweep runs each (suite, task) exactly once, so keying the output directory by
# task makes results/h4_<suite>/<task>/ stable and predictable: fan_out.sh can
# tell which tasks are already done without consulting LSF, and collect.py can
# map a result back to its task by path instead of by a jobid->task side table
# that goes stale the moment a job is resubmitted.
ARGS=(
  --suite-id "h4_$SUITE_ID"
  --run-id "$TASK_ID_ARG"
  --max-iterations 0
  --spec "$SPEC"
  --project "$PROJECT_DIR"
  "${PASSTHRU[@]}"
)
echo "TASK_ID=$TASK_ID"
echo "run_ccc_experiment.sh ${ARGS[*]}"
bash "$CCC_DIR/run_ccc_experiment.sh" "${ARGS[@]}"
RC=$?
banner "h4 eval finished — suite=$SUITE_ID task=$TASK_ID_ARG rc=$RC"
echo "End: $(date -Iseconds)"
exit "$RC"
