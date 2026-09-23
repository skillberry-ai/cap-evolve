#!/bin/bash
#
# Run one v4_t2_e1 task's cap-evolve project on a CCC compute node, by hand.
# Mirrors run_ccc_experiment.sh's phase structure (podman setup -> stack
# health-wait -> cap-evolve run -> summarize), but for parsec's own stack
# and its own env contract (PARSEC_V4N, not SKILLSBENCH_TASKS_DIR).
#
# Usage:
#   export PARSEC_V4N=/path/to/rhdp-parsec/v4_2026-09-16
#   bash scripts/ccc/run_ccc_parsec.sh --task-id icinga-011-aap2-job-status-alert
#
# Output layout under the project (all under $PROJECT_ROOT/results/parsec/):
#   results/parsec/<task-id>/<run-id>/
#     setup.log            # setup_podman.sh + parsec_stack.sh output
#     cap-evolve.log        # cap-evolve stdout+stderr
#     env_snapshot.txt      # PARSEC_V4N, capevolve.yaml, git commit, hostname
#     run/                  # symlink to cap-evolve's real run dir, which is
#                           # .capevolve/v4_t2_e1_<task-id>/run_<run-id>
#
# --max-iterations is NOT defaulted: omit it and the scaffolded spec's own
# `max_iterations` governs. Pass `--max-iterations 0` explicitly for a
# baseline-only run.
#
# The parsec stack is torn down by an EXIT trap, so an LSF job that dies
# doesn't leave 5 containers and parsec-live holding ports 8000/8086-8090.
#
# Exits non-zero if setup fails, the stack never becomes healthy, or
# cap-evolve returns an error.

set -eo pipefail

TASK_ID=""
RUN_ID=""
MAX_ITERATIONS=""
DRY_RUN=false

usage() {
  sed -n '2,28p' "$0"
  exit 2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --task-id)         TASK_ID="$2"; shift 2 ;;
    --run-id)          RUN_ID="$2"; shift 2 ;;
    --max-iterations)  MAX_ITERATIONS="$2"; shift 2 ;;
    --dry-run)         DRY_RUN=true; shift ;;
    -h|--help)         usage ;;
    *) echo "Unknown option: $1" >&2; usage ;;
  esac
done

if [[ -z "$TASK_ID" ]]; then
  echo "ERROR: --task-id is required (e.g. --task-id icinga-011-aap2-job-status-alert)" >&2
  usage
fi

: "${PARSEC_V4N:?PARSEC_V4N environment variable is required (see parsec_paths.py)}"

if [[ -z "$RUN_ID" ]]; then
  if [[ -n "${LSB_JOBID:-}" ]]; then
    RUN_ID="$LSB_JOBID"
  else
    RUN_ID="local_$(date +%Y%m%d_%H%M%S)"
  fi
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -z "${PROJECT_ROOT:-}" ]]; then
  PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
fi

PROJECT_DIR=".capevolve/v4_t2_e1_${TASK_ID}/project"
SPEC="$PROJECT_DIR/capevolve.yaml"
if [[ ! -f "$PROJECT_ROOT/$SPEC" ]]; then
  echo "ERROR: $PROJECT_ROOT/$SPEC not found — run scaffold_projects.py first" >&2
  exit 2
fi

OUT_DIR="$PROJECT_ROOT/results/parsec/$TASK_ID/$RUN_ID"
mkdir -p "$OUT_DIR"
SETUP_LOG="$OUT_DIR/setup.log"
RUN_LOG="$OUT_DIR/cap-evolve.log"
ENV_SNAP="$OUT_DIR/env_snapshot.txt"

banner() {
  printf '\n============================================================\n'
  printf '%s\n' "$1"
  printf '============================================================\n'
}

banner "parsec v4 (v4_t2_e1) on CCC: $TASK_ID / $RUN_ID"
{
  echo "Host:          $(hostname)"
  echo "Start:         $(date -Iseconds)"
  echo "PROJECT_ROOT:  $PROJECT_ROOT"
  echo "PARSEC_V4N:    $PARSEC_V4N"
  echo "OUT_DIR:       $OUT_DIR"
  echo "TASK_ID:       $TASK_ID"
  echo "MAX_ITER:      ${MAX_ITERATIONS:-(from spec)}"
  if [[ -n "${LSB_JOBID:-}" ]]; then
    echo "LSF job:       $LSB_JOBID"
  fi
} | tee "$ENV_SNAP"

if [[ "$DRY_RUN" == true ]]; then
  echo "(dry-run: exiting before setup)"
  exit 0
fi

banner "Phase 1: setup_podman.sh"
SETUP_PODMAN="${CCC_SETUP_PODMAN:-$SCRIPT_DIR/setup_podman.sh}"
if [[ ! -r "$SETUP_PODMAN" ]]; then
  echo "FATAL: setup_podman.sh not readable at $SETUP_PODMAN" >&2
  exit 2
fi
# shellcheck disable=SC1090
source "$SETUP_PODMAN" > >(tee "$SETUP_LOG") 2>&1
wait 2>/dev/null || true

banner "Phase 2: parsec stack up + health-wait"
# Arm the teardown BEFORE `up`, so a stack that comes up but fails its health
# check is still torn down. Without this an LSF job exit leaves the 5 simulator
# containers and parsec-live running and holding ports 8000/8086-8090, which
# then makes the next job on this host silently reuse a stale, wrongly-seeded
# stack. `|| true` so a teardown failure never masks the run's real exit code.
STACK_UP=false
teardown_stack() {
  [[ "$STACK_UP" == true ]] || return 0
  bash "$SCRIPT_DIR/parsec_stack.sh" down >> "$SETUP_LOG" 2>&1 || true
}
trap teardown_stack EXIT
STACK_UP=true
bash "$SCRIPT_DIR/parsec_stack.sh" up | tee -a "$SETUP_LOG"
bash "$SCRIPT_DIR/parsec_stack.sh" status | tee -a "$SETUP_LOG"

{
  echo
  echo "===== $SPEC ====="
  cat "$PROJECT_ROOT/$SPEC"
  echo
  echo "===== git status (worktree) ====="
  ( cd "$PROJECT_ROOT" && git log -1 --format='commit %H%n%s' 2>&1 || echo "(not a git repo)" )
} >> "$ENV_SNAP"

banner "Phase 3: cap-evolve run"
cd "$PROJECT_ROOT"
export TASK_ID
export PARSEC_V4N

# cli.py composes the run dir as `proj_abs.parent / run_<ts>` (workdir is
# proj_abs.parent.parent, base is proj_abs.parent relative to it — cli.py:636-639,
# :800). v4_t2_e1's project has one MORE nesting level than the sibling
# run_ccc_experiment.sh's `.capevolve/project`, so the run dir is under
# .capevolve/v4_t2_e1_<task-id>/, NOT directly under .capevolve/.
CE_RUN_ABS="$PROJECT_ROOT/.capevolve/v4_t2_e1_${TASK_ID}/run_${RUN_ID}"
ln -sfn "$CE_RUN_ABS" "$OUT_DIR/run"
# Absolute, not relative: cap-evolve runs every skill subprocess with
# cwd=workdir ($PROJECT_ROOT/.capevolve here), where a relative
# ".capevolve/..." path does not resolve.
export PYTHONPATH="$PROJECT_ROOT/$PROJECT_DIR/adapters${PYTHONPATH:+:$PYTHONPATH}"
# Pin the skills dir the same way the sibling run_ccc_experiment.sh does, so
# cli.py's _find_skills_dir can't silently fall back to a stale ~/.claude/skills.
export CAPEVOLVE_SKILLS_DIR="$PROJECT_ROOT/skills"

if [[ -z "${CE_BIN:-}" ]]; then
  if [[ -x "$PROJECT_ROOT/.venv/bin/cap-evolve" ]]; then
    CE_BIN="$PROJECT_ROOT/.venv/bin/cap-evolve"
  else
    CE_BIN="$(command -v cap-evolve || true)"
  fi
fi
if [[ -z "$CE_BIN" || ! -x "$CE_BIN" ]]; then
  echo "FATAL: cap-evolve CLI not found. Set CE_BIN=/path/to/cap-evolve." >&2
  exit 2
fi

# Only pass --max-iterations when the caller asked for one: cli.py treats the
# flag as an override of the spec ("None = not passed, leave spec value"), and
# `--max-iterations 0` means zero iterations / baseline-only. Defaulting it to 0
# silently overrode the scaffolded spec's own max_iterations.
CE_ARGS=(run --spec "$SPEC" --project "$PROJECT_DIR" --run-ts "$RUN_ID")
if [[ -n "$MAX_ITERATIONS" ]]; then
  CE_ARGS+=(--max-iterations "$MAX_ITERATIONS")
fi

set +e
stdbuf -oL -eL "$CE_BIN" "${CE_ARGS[@]}" 2>&1 | tee "$RUN_LOG"
RC="${PIPESTATUS[0]}"
set -e

banner "Phase 4: done"
echo "End:      $(date -Iseconds)"
echo "Exit:     $RC"
echo "Results:  $OUT_DIR"
exit "$RC"
