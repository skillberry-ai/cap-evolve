#!/bin/bash
#
# Submit (or resume) the v6_t2 task-by-task drivers: one LSF driver per task, each running stock
# cap-evolve hill-climb on its own single-task project (scaffold_projects.py), all dispatching
# their evaluations to ONE shared lane queue and ONE worker pool, sized by default so that every
# submitted task can evaluate at once (tasks x num_trials workers).
#
# Each driver is examples/parsec/v6/run_v6.sh, unchanged in what it runs; this script only sets
# the shared-queue environment and the v6_t2 optimizer registry, then submits it per task.
#
# Usage:
#   source ~/.v5_g2e1_env.sh        # LLM_API_KEY/BASE, HARNESS_LLM_SIMULATION_MODEL, CE_BIN
#   export PARSEC_V6N=/path/to/rhdp-parsec/v6_2026-10-16
#   bash examples/parsec/v6_t2/run_t2.sh --suite-id e1 --max-iterations 3 [--only TASK ...]
#   bash examples/parsec/v6_t2/run_t2.sh --suite-id e1 --max-iterations 3 --resume [--only TASK ...]
#   bash examples/parsec/v6_t2/run_t2.sh --suite-id e1 --max-iterations 5 --resume --only TASK --after JOBID
#   bash examples/parsec/v6_t2/run_t2.sh --suite-id e1 --dry-run     # print, submit nothing
#
# Without --only, every task scaffolded under .capevolve/v6_t2_<suite>_*/ is submitted.
# --resume reuses each task's run name (the task id), so a resubmission continues its run.
# --after JOBID holds every submitted driver until that LSF job has ended (run_v6.sh --after).
set -eo pipefail

T2_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$T2_DIR/../../.." && pwd)"
: "${PARSEC_V6N:?PARSEC_V6N environment variable is required (the v6 benchmark tree)}"

SUITE=""
MAX_ITERATIONS=""
RESUME=false
DRY_RUN=false
AFTER=""
ONLY=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --suite-id)       SUITE="$2"; shift 2 ;;
    --max-iterations) MAX_ITERATIONS="$2"; shift 2 ;;
    --resume)         RESUME=true; shift ;;
    --only)           ONLY+=("$2"); shift 2 ;;
    --after)          AFTER="$2"; shift 2 ;;
    --dry-run)        DRY_RUN=true; shift ;;
    -h|--help)        sed -n '2,20p' "$0"; exit 0 ;;
    *)                echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
[[ -n "$SUITE" ]] || { echo "--suite-id is required" >&2; exit 2; }
[[ -n "$MAX_ITERATIONS" || "$DRY_RUN" == true ]] || { echo "--max-iterations is required" >&2; exit 2; }

if [[ ${#ONLY[@]} -eq 0 ]]; then
  for d in "$PROJECT_ROOT"/.capevolve/v6_t2_"${SUITE}"_*/project; do
    [[ -f "$d/capevolve.yaml" ]] || continue
    t="$(basename "$(dirname "$d")")"
    ONLY+=("${t#v6_t2_${SUITE}_}")
  done
fi
[[ ${#ONLY[@]} -gt 0 ]] || { echo "no v6_t2_${SUITE}_* projects; run scaffold_projects.py first" >&2; exit 2; }

# Enough lane workers for every submitted task to evaluate at the same time (tasks x num_trials),
# so no task waits for a lane behind another; V6_MAX_WORKERS in the environment overrides it.
# Idle workers exit after V6_WORKER_IDLE_EXIT seconds, so an unused cap costs nothing.
first_spec="$PROJECT_ROOT/.capevolve/v6_t2_${SUITE}_${ONLY[0]}/project/capevolve.yaml"
trials="$(sed -n 's/^num_trials: *\([0-9]*\).*/\1/p' "$first_spec")"
export V6_MAX_WORKERS="${V6_MAX_WORKERS:-$(( ${#ONLY[@]} * ${trials:-5} ))}"
export V6_QUEUE_ROOT="$PARSEC_V6N/_run/v6-queue/v6_t2_${SUITE}"
export V6_SHARED_QUEUE=1
export V6_T2_DIR="$T2_DIR"
export CAPEVOLVE_OPTIMIZER_REGISTRY="$T2_DIR/registry.yaml"
[[ -f "$CAPEVOLVE_OPTIMIZER_REGISTRY" ]] || { echo "missing $CAPEVOLVE_OPTIMIZER_REGISTRY; run build_registry.py" >&2; exit 2; }

echo "v6_t2 ${SUITE}: ${#ONLY[@]} task(s), queue=$V6_QUEUE_ROOT workers<=${V6_MAX_WORKERS:-15}"
for task in "${ONLY[@]}"; do
  args=(--suite-id "t2_${SUITE}_${task}" --max-iterations "${MAX_ITERATIONS:-0}" --run-ts "$task" --submit)
  [[ "$RESUME" == true ]] && args+=(--resume)
  [[ -n "$AFTER" ]] && args+=(--after "$AFTER")
  if [[ "$DRY_RUN" == true ]]; then
    echo "  would run: bash examples/parsec/v6/run_v6.sh ${args[*]}"
  else
    echo "  $task: $(bash "$PROJECT_ROOT/examples/parsec/v6/run_v6.sh" "${args[@]}")"
  fi
done
