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
#       --queue x86_6h --memory 64G --host cccxc442
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
#   --memory MEM           memory per job (default: 64G). CCC's LSF accepts
#                          the G suffix — verified: bjobs reports MEMLIMIT
#                          back as "64 G", no rusage[mem=] needed.
#   --cpus N               CPU slots (default: 1 for iter=0, else 4)
#   --host HOST            pin to one LSF host (-m). Use one host per
#                          concurrent job; avoid the reserved cccxc6xx range.
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
CPUS=""         # auto by MAX_ITERATIONS below
HOST=""         # -m <host>: pin to a dedicated LSF host
EXTRA_ARGS=""
DRY_RUN=false
CCC_LOGS="${CCC_LOGS:-}"   # resolved after PROJECT_ROOT is known

while [[ $# -gt 0 ]]; do
  case "$1" in
    --suite-id)        SUITE_ID="$2"; shift 2 ;;
    --max-iterations)  MAX_ITERATIONS="$2"; shift 2 ;;
    --spec)            SPEC="$2"; shift 2 ;;
    --project)         PROJECT_DIR="$2"; shift 2 ;;
    --queue)           QUEUE="$2"; shift 2 ;;
    --memory)          MEMORY="$2"; shift 2 ;;
    --cpus)            CPUS="$2"; shift 2 ;;
    --host)            HOST="$2"; shift 2 ;;
    --extra-args)      EXTRA_ARGS="$2"; shift 2 ;;
    --dry-run)         DRY_RUN=true; shift ;;
    -h|--help)         sed -n '2,/^$/p' "$0"; exit 2 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "$SUITE_ID" ]]; then
  echo "ERROR: --suite-id is required" >&2
  exit 2
fi

# There is deliberately NO walltime support here: this script never passes -W,
# and offers no flag to add one. A cap-evolve job often finishes its work and
# then hangs in a post-run step; a wall-clock limit kills it *after* the result
# is already written, turning a successful run into TERM_RUNLIMIT and losing
# the outcome. Detect completion from the job's cap-evolve.log — or a quick
# `lout <jobid> | grep "Exit:     0"` sweep — and bkill that exact job id.
# See docs/how-to/ccc/CCC_PODMAN_SETUP.md § "Batch (LSF) mode".

if [[ -z "$CPUS" ]]; then
  # --max-iterations 0 is a single eval with no internal parallelism.
  if [[ "$MAX_ITERATIONS" == "0" ]]; then
    CPUS="1"
  else
    CPUS="4"
  fi
fi

# Resolve project root: this script lives at $PROJECT_ROOT/scripts/ccc/*.sh
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

INNER="$PROJECT_ROOT/scripts/ccc/run_ccc_experiment.sh"
[[ -x "$INNER" ]] || { echo "ERROR: inner script not executable: $INNER" >&2; exit 2; }

# LSF writes %J.stdout/%J.stderr here. Account-neutral default; override
# with $CCC_LOGS (e.g. a scratch dir with more room than the checkout).
CCC_LOGS="${CCC_LOGS:-$PROJECT_ROOT/results/.ccc_logs}"

JOB_NAME="capevolve_${SUITE_ID}_iter${MAX_ITERATIONS}"

# Build bsub command. -oo/-eo to keep separate stdout/stderr per LSF job id.
BSUB_CMD=(
  bsub
  -q "$QUEUE"
  -M "$MEMORY"
  -n "$CPUS"
  -J "$JOB_NAME"
)
# Pin to a dedicated host: podman's graphroot is per-user per-host, so two of
# your own concurrent jobs on one host corrupt each other's container state.
# Cross-check `brsvs -w` first — the cccxc6xx range is permanently reserved
# for another group despite looking idle in `bhosts -w`.
if [[ -n "$HOST" ]]; then
  BSUB_CMD+=(-m "$HOST")
fi
BSUB_CMD+=(
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
printf 'HOST:         %s\n' "${HOST:-(unpinned)}"
printf 'LOG DIR:      %s\n' "$CCC_LOGS"
printf 'INNER CMD:    %s\n' "${BSUB_CMD[*]}"

if [[ "$DRY_RUN" == true ]]; then
  echo
  echo "(dry-run: not submitting)"
  exit 0
fi

# Only touch the filesystem once we're actually submitting, so --dry-run
# works from any account / read-only checkout.
mkdir -p "$CCC_LOGS"

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
