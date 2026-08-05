#!/bin/bash
#
# Run one cap-evolve experiment on a CCC compute node.
#
# Designed to be called via `bsub` (see submit_ccc_experiment.sh) or run
# directly on a compute node for testing. Handles all the CCC-specific
# podman setup and saves results under the project tree.
#
# Usage:
#   # Direct execution (on a compute node with an interactive shell)
#   bash scripts/ccc/run_ccc_experiment.sh \
#       --suite-id baseline_v1 \
#       --max-iterations 0
#
#   # Baseline (iter=0) at a specific run-id
#   bash scripts/ccc/run_ccc_experiment.sh \
#       --suite-id baseline_v1 \
#       --run-id my_test \
#       --max-iterations 0
#
#   # Full 7-iter run
#   bash scripts/ccc/run_ccc_experiment.sh \
#       --suite-id iter7_opus_v1 \
#       --max-iterations 7
#
# Output layout under the project (all under $PROJECT_ROOT/results/):
#
#   results/
#     <suite-id>/                  # e.g. "baseline_v1"
#       <run-id>/                  # e.g. LSF job id, or timestamp when local
#         setup.log                # setup_podman.sh output
#         cap-evolve.log           # cap-evolve stdout+stderr
#         env_snapshot.txt         # .env + capevolve.yaml + git commit + hostname
#         run/                     # cap-evolve's run dir (symlinked from .capevolve/run_<run-id>)
#
# Suite-id / run-id conventions:
#   - suite-id: your logical grouping ("baseline_ccc_v1", "iter7_opus_20260730").
#     Not required to be unique across sessions; multiple runs can share.
#   - run-id: uniquely identifies THIS run. Defaults to $LSB_JOBID (when
#     submitted via LSF) or local_<timestamp> otherwise.
#
# The script exits non-zero if setup fails or cap-evolve returns an error.

set -eo pipefail

# --------------------------------------------------------------------
# Argument parsing
# --------------------------------------------------------------------
SUITE_ID=""
RUN_ID=""
RUN_TS=""        # stable name for cap-evolve's run dir; defaults to RUN_ID
RESUME=false     # pass --resume to cap-evolve (continue an interrupted run)
MAX_ITERATIONS="0"
SPEC=".capevolve/project/capevolve.yaml"
PROJECT_DIR=".capevolve/project"
INCLUDE=""       # optional; forwarded as --include to bench if bench-mode is added later
EXTRA_ARGS=""    # any extra flags to append verbatim to cap-evolve
DRY_RUN=false

usage() {
  sed -n '2,45p' "$0"
  exit 2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --suite-id)         SUITE_ID="$2"; shift 2 ;;
    --run-id)           RUN_ID="$2"; shift 2 ;;
    --run-ts)           RUN_TS="$2"; shift 2 ;;
    --resume)           RESUME=true; shift ;;
    --max-iterations)   MAX_ITERATIONS="$2"; shift 2 ;;
    --spec)             SPEC="$2"; shift 2 ;;
    --project)          PROJECT_DIR="$2"; shift 2 ;;
    --extra-args)       EXTRA_ARGS="$2"; shift 2 ;;
    --dry-run)          DRY_RUN=true; shift ;;
    -h|--help)          usage ;;
    *)  echo "Unknown option: $1" >&2; usage ;;
  esac
done

# --run-ts defaults to RUN_ID when not explicitly given. Using the same
# --run-ts across LSF jobs is how you resume: cap-evolve looks up its state
# under .capevolve/run_<run-ts>/, so a stable name lets the second submission
# find the first's checkpoint.
if [[ -z "$RUN_TS" ]]; then
  RUN_TS="$RUN_ID"
fi

if [[ -z "$SUITE_ID" ]]; then
  echo "ERROR: --suite-id is required (e.g. --suite-id baseline_v1)" >&2
  usage
fi

# Default RUN_ID from LSF job id, else a timestamp.
if [[ -z "$RUN_ID" ]]; then
  if [[ -n "${LSB_JOBID:-}" ]]; then
    RUN_ID="$LSB_JOBID"
  else
    RUN_ID="local_$(date +%Y%m%d_%H%M%S)"
  fi
fi

# RUN_TS still empty means the user didn't pass --run-ts and RUN_ID was
# resolved above. Re-default RUN_TS to RUN_ID now that RUN_ID is known.
if [[ -z "$RUN_TS" ]]; then
  RUN_TS="$RUN_ID"
fi

# --------------------------------------------------------------------
# Locate the project root
# --------------------------------------------------------------------
# The intake worktree the script lives in. Resolve by climbing up from
# this file's dir. Users can override with $PROJECT_ROOT.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -z "${PROJECT_ROOT:-}" ]]; then
  PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
fi

if [[ ! -f "$PROJECT_ROOT/$SPEC" ]]; then
  echo "ERROR: --spec not found: $PROJECT_ROOT/$SPEC" >&2
  echo "       (try running from the intake worktree, or set PROJECT_ROOT)" >&2
  exit 2
fi

# --------------------------------------------------------------------
# Output directory
# --------------------------------------------------------------------
OUT_DIR="$PROJECT_ROOT/results/$SUITE_ID/$RUN_ID"
mkdir -p "$OUT_DIR"

SETUP_LOG="$OUT_DIR/setup.log"
RUN_LOG="$OUT_DIR/cap-evolve.log"
ENV_SNAP="$OUT_DIR/env_snapshot.txt"

# --------------------------------------------------------------------
# Print banner
# --------------------------------------------------------------------
banner() {
  printf '\n============================================================\n'
  printf '%s\n' "$1"
  printf '============================================================\n'
}

banner "cap-evolve on CCC: $SUITE_ID / $RUN_ID"
{
  echo "Host:          $(hostname)"
  echo "Start:         $(date -Iseconds)"
  echo "PROJECT_ROOT:  $PROJECT_ROOT"
  echo "OUT_DIR:       $OUT_DIR"
  echo "SPEC:          $SPEC"
  echo "PROJECT_DIR:   $PROJECT_DIR"
  echo "RUN_TS:        $RUN_TS   (cap-evolve run dir → .capevolve/run_$RUN_TS/)"
  echo "RESUME:        $RESUME"
  echo "MAX_ITER:      $MAX_ITERATIONS"
  echo "EXTRA_ARGS:    $EXTRA_ARGS"
  echo "DRY_RUN:       $DRY_RUN"
  if [[ -n "${LSB_JOBID:-}" ]]; then
    echo "LSF job:       $LSB_JOBID"
    echo "LSF queue:     ${LSB_QUEUE:-}"
    echo "LSF host:      ${LSB_HOSTS:-}"
  fi
} | tee "$ENV_SNAP"

if [[ "$DRY_RUN" == true ]]; then
  echo
  echo "(dry-run: exiting before setup)"
  exit 0
fi

# --------------------------------------------------------------------
# Phase 1: CCC podman setup (rootless podman + docker shim + patched
# base image + bench patches, all done idempotently)
# --------------------------------------------------------------------
banner "Phase 1: setup_podman.sh"
# CRITICAL: `source X | tee Y` puts X in a subshell — its `export`s
# would be discarded. Process substitution `> >(tee ...)` keeps `source`
# in the current shell so PATH/DOCKER_HOST/... persist.
# shellcheck disable=SC1091
source "$SCRIPT_DIR/setup_podman.sh" \
    > >(tee "$SETUP_LOG") 2>&1
# Wait a tick so tee finishes flushing to disk before we proceed.
wait 2>/dev/null || true

# Belt-and-suspenders: prepend the docker shim explicitly, in case
# setup_podman.sh's PATH prepend logic regresses.
if [[ -x "$HOME/.local/bin/docker" ]]; then
  export PATH="$HOME/.local/bin:${PATH/#$HOME\/.local\/bin:/}"
fi

# Sanity: docker shim must win the PATH lookup, otherwise we'll get the
# "Emulate Docker CLI using podman" stdout pollution in every bench probe.
if [[ "$(readlink -f "$(which docker)")" != "$HOME/.local/bin/docker" ]]; then
  echo "FATAL: 'docker' resolves to $(which docker), not $HOME/.local/bin/docker." >&2
  echo "       PATH ordering is wrong; setup_podman.sh should have prepended it." >&2
  echo "       Aborting to avoid a corrupted run." >&2
  exit 3
fi

# --------------------------------------------------------------------
# Phase 2: load credentials from .env
# --------------------------------------------------------------------
banner "Phase 2: loading .env"
if [[ ! -f "$PROJECT_ROOT/.env" ]]; then
  echo "FATAL: $PROJECT_ROOT/.env not found." >&2
  exit 2
fi
set -a
# shellcheck disable=SC1090,SC1091
source "$PROJECT_ROOT/.env"
set +a
: "${ANTHROPIC_BASE_URL:?ANTHROPIC_BASE_URL missing from .env}"
: "${ANTHROPIC_AUTH_TOKEN:?ANTHROPIC_AUTH_TOKEN missing from .env}"
: "${SKILLSBENCH_TASKS_DIR:?SKILLSBENCH_TASKS_DIR missing from .env}"

# Snapshot the exact resolved config alongside the results.
{
  echo
  echo "===== .env (redacted) ====="
  sed 's/\(TOKEN\|KEY\)=.*/\1=<REDACTED>/' "$PROJECT_ROOT/.env"
  echo
  echo "===== $SPEC ====="
  cat "$PROJECT_ROOT/$SPEC"
  echo
  echo "===== git status (worktree) ====="
  ( cd "$PROJECT_ROOT" && git log -1 --format='commit %H%n%s%n%n%b' 2>&1 || echo "(not a git repo)" )
  echo
  echo "===== podman info ====="
  podman info 2>&1 | head -60
} >> "$ENV_SNAP"

# --------------------------------------------------------------------
# Phase 3: cap-evolve run
# --------------------------------------------------------------------
banner "Phase 3: cap-evolve run"
cd "$PROJECT_ROOT"

# Cap-evolve writes to .capevolve/run_<run-ts>/ by default. Symlink that
# under results/<suite>/<run>/run/ so the run's artifacts live under
# the project tree without cap-evolve needing to know about our layout.
CE_RUN_DIRNAME="run_${RUN_TS}"
CE_RUN_ABS="$PROJECT_ROOT/.capevolve/$CE_RUN_DIRNAME"
LINK_TARGET="$OUT_DIR/run"
ln -sfn "$CE_RUN_ABS" "$LINK_TARGET"

export PYTHONPATH="$PROJECT_DIR/adapters"
export CAPEVOLVE_SKILLS_DIR="$PROJECT_ROOT/skills"

# cap-evolve CLI. Override with $CAP_EVOLVE_BIN, else use whatever's in PATH.
# In a typical install `pip install -e ./core` puts a `cap-evolve` script in
# the active venv's bin/; make sure that venv is on PATH before invoking, or
# set CAP_EVOLVE_BIN to the absolute path.
CE_BIN="${CAP_EVOLVE_BIN:-$(command -v cap-evolve || true)}"
if [[ -z "$CE_BIN" || ! -x "$CE_BIN" ]]; then
  echo "FATAL: cap-evolve CLI not found." >&2
  echo "       Either activate the venv where you installed cap-evolve," >&2
  echo "       or export CAP_EVOLVE_BIN=/absolute/path/to/cap-evolve" >&2
  exit 2
fi

# Compose the command line
CE_CMD=(
  "$CE_BIN" run
  --spec "$SPEC"
  --project "$PROJECT_DIR"
  --run-ts "$RUN_TS"
  --max-iterations "$MAX_ITERATIONS"
)
if [[ "$RESUME" == true ]]; then
  CE_CMD+=(--resume)
fi
if [[ -n "$EXTRA_ARGS" ]]; then
  # shellcheck disable=SC2206
  CE_CMD+=($EXTRA_ARGS)
fi

echo "Running: ${CE_CMD[*]}"
echo

# Run under `stdbuf` so log lines flush live to the file — useful when
# tailing $RUN_LOG from another shell mid-experiment.
set +e
stdbuf -oL -eL "${CE_CMD[@]}" 2>&1 | tee "$RUN_LOG"
RC="${PIPESTATUS[0]}"
set -e

# --------------------------------------------------------------------
# Phase 4: summarize + exit
# --------------------------------------------------------------------
banner "Phase 4: done"
echo "End:      $(date -Iseconds)"
echo "Exit:     $RC"
echo "Results:  $OUT_DIR"
echo "  setup:  $SETUP_LOG"
echo "  run:    $RUN_LOG"
echo "  env:    $ENV_SNAP"
echo "  cap-evolve run dir (symlink → $CE_RUN_ABS): $LINK_TARGET"

# If we produced a baseline.json, show its headline
if [[ -f "$CE_RUN_ABS/baseline.json" ]]; then
  echo
  echo "===== baseline.json headline ====="
  python3 -c "
import json
d = json.load(open('$CE_RUN_ABS/baseline.json'))
v = d.get('val', {})
print(f\"val reward:  {v.get('reward')}   stderr: {v.get('stderr')}\")
print(f\"pass_at_k:   {v.get('pass_at_k')}\")
print(f\"per_task:\")
for t in v.get('per_task', []):
    print(f\"  {t.get('task_id'):<28} reward={t.get('reward')} stderr={t.get('stderr')} trial_rewards={t.get('trial_rewards')}\")
" || echo "(couldn't parse baseline.json)"
fi

exit "$RC"
