#!/bin/bash
#
# Submit a cap-evolve experiment to LSF (CCC batch).
#
# Wraps `bsub` around scripts/ccc/run_ccc_experiment.sh with sensible
# defaults for a full baseline or 7-iter run. Modeled on
# skillberry-skill-maker's run_tasks_on_dedicated_machines.sh.
#
# Usage:
#   bash scripts/ccc/submit_ccc_experiment.sh \
#       --suite-id baseline_v1 --max-iterations 0
#
#   # Full 7-iter run
#   bash scripts/ccc/submit_ccc_experiment.sh \
#       --suite-id iter7_opus_v1 --max-iterations 7 \
#       --queue x86_1h --memory 64G --walltime 6:00
#
#   # Dry-run — print the bsub command without submitting
#   bash scripts/ccc/submit_ccc_experiment.sh \
#       --suite-id test --max-iterations 0 --dry-run
#
# Options:
#   --suite-id ID          [REQUIRED] logical grouping (e.g. "baseline_v1")
#   --max-iterations N     0 for baseline (default), 7 for full evolve
#   --spec PATH            path to capevolve.yaml (default: .capevolve/project/capevolve.yaml)
#   --project PATH         path to .capevolve/project (default: .capevolve/project)
#   --queue Q              LSF queue (default: x86_6h)
#   --memory MEM           memory per job (default: 64G)
#   --walltime H:MM        wall-clock limit (default: 6:00 for iter=0, 12:00 for iter>0)
#   --cpus N               CPU slots (default: 4)
#   --extra-args "..."     verbatim flags passed to cap-evolve run
#   --dry-run              print the bsub command, don't submit
#
# The run-id is auto-derived from LSF's job ID once submitted (so results
# land under results/<suite-id>/<LSB_JOBID>/).

set -euo pipefail

# Defaults
SUITE_ID=""
MAX_ITERATIONS="0"
SPEC=".capevolve/project/capevolve.yaml"
PROJECT_DIR=".capevolve/project"
QUEUE="x86_6h"
MEMORY="64G"
WALLTIME=""     # auto by MAX_ITERATIONS below
CPUS="4"
EXTRA_ARGS=""
DRY_RUN=false
CCC_LOGS="${CCC_LOGS:-$HOME/ccc_logs}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --suite-id)        SUITE_ID="$2"; shift 2 ;;
    --max-iterations)  MAX_ITERATIONS="$2"; shift 2 ;;
    --spec)            SPEC="$2"; shift 2 ;;
    --project)         PROJECT_DIR="$2"; shift 2 ;;
    --queue)           QUEUE="$2"; shift 2 ;;
    --memory)          MEMORY="$2"; shift 2 ;;
    --walltime)        WALLTIME="$2"; shift 2 ;;
    --cpus)            CPUS="$2"; shift 2 ;;
    --extra-args)      EXTRA_ARGS="$2"; shift 2 ;;
    --dry-run)         DRY_RUN=true; shift ;;
    -h|--help)         sed -n '2,40p' "$0"; exit 2 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "$SUITE_ID" ]]; then
  echo "ERROR: --suite-id is required" >&2
  exit 2
fi

if [[ -z "$WALLTIME" ]]; then
  # Baseline is ~1h. Full 7-iter is 4-6h; give margin.
  if [[ "$MAX_ITERATIONS" == "0" ]]; then
    WALLTIME="2:00"
  else
    WALLTIME="8:00"
  fi
fi

# Resolve project root: this script lives at $PROJECT_ROOT/scripts/ccc/*.sh
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

INNER="$PROJECT_ROOT/scripts/ccc/run_ccc_experiment.sh"
[[ -x "$INNER" ]] || { echo "ERROR: inner script not executable: $INNER" >&2; exit 2; }

mkdir -p "$CCC_LOGS"

JOB_NAME="capevolve_${SUITE_ID}_iter${MAX_ITERATIONS}"

# Build bsub command. -oo/-eo to keep separate stdout/stderr per LSF job id.
BSUB_CMD=(
  bsub
  -q "$QUEUE"
  -M "$MEMORY"
  -n "$CPUS"
  -W "$WALLTIME"
  -J "$JOB_NAME"
  -oo "${CCC_LOGS}/%J.stdout"
  -eo "${CCC_LOGS}/%J.stderr"
  bash "$INNER"
  --suite-id "$SUITE_ID"
  --max-iterations "$MAX_ITERATIONS"
  --spec "$SPEC"
  --project "$PROJECT_DIR"
)
if [[ -n "$EXTRA_ARGS" ]]; then
  BSUB_CMD+=(--extra-args "$EXTRA_ARGS")
fi

printf 'PROJECT_ROOT: %s\n' "$PROJECT_ROOT"
printf 'JOB:          %s\n' "$JOB_NAME"
printf 'QUEUE:        %s\n' "$QUEUE"
printf 'MEMORY:       %s\n' "$MEMORY"
printf 'CPUs:         %s\n' "$CPUS"
printf 'WALLTIME:     %s\n' "$WALLTIME"
printf 'LOG DIR:      %s\n' "$CCC_LOGS"
printf 'INNER CMD:    %s\n' "${BSUB_CMD[*]}"

if [[ "$DRY_RUN" == true ]]; then
  echo
  echo "(dry-run: not submitting)"
  exit 0
fi

echo
"${BSUB_CMD[@]}"
echo
cat <<EOF

Submitted. Monitor with:
  bjobs -w
  bjobs -l <JOB_ID>
  tail -f ${CCC_LOGS}/<JOB_ID>.stdout

Results will land at:
  $PROJECT_ROOT/results/$SUITE_ID/<JOB_ID>/

  results/${SUITE_ID}/<JOB_ID>/setup.log         # setup_podman.sh output
  results/${SUITE_ID}/<JOB_ID>/cap-evolve.log    # cap-evolve stdout+stderr
  results/${SUITE_ID}/<JOB_ID>/env_snapshot.txt  # .env + capevolve.yaml + git commit + podman info
  results/${SUITE_ID}/<JOB_ID>/run/              # cap-evolve's run dir (symlink)

EOF
