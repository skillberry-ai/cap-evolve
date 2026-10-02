#!/bin/bash
#
# Run the v4_g2_e1 project (all 34 parsec v4 tasks, optimized jointly in one
# cap-evolve process) on a CCC compute node.
#
# Unlike run_ccc_parsec.sh (one task per process, its own inline Phase 3),
# this script does ONLY the one thing run_ccc_experiment.sh cannot do on its
# own — bring up/tear down parsec's simulator stack — then hands off to
# run_ccc_experiment.sh unmodified for setup, the actual `cap-evolve run`,
# and the summary. See docs/how-to/ccc/CCC_PODMAN_SETUP.md's "Bringing the
# stack up on a CCC compute node" section for the stack's own env contract.
#
# Usage:
#   export PARSEC_V4N=/path/to/rhdp-parsec/v4_2026-09-16
#   export LLM_API_KEY=...  LLM_API_BASE=https://your-gateway
#   export HARNESS_LLM_SIMULATION_MODEL=azure/gpt-5.4
#   bash scripts/ccc/run_ccc_parsec_g2.sh [--run-id ID] [--max-iterations N] [--dry-run]
#
# Any extra arguments are forwarded verbatim to run_ccc_experiment.sh, so
# --resume, --run-ts, --extra-args etc. all work unchanged.
#
# --interactive: run ONE optimization iteration at a time, pausing after
# each to ask (on the controlling terminal) whether to continue. This is a
# pure wrapper-loop feature — no cap-evolve core change: cli.py's
# `--max-iterations` on `--resume` is the RUN's cumulative iteration budget
# (checked against state.json's persisted spent.iterations), not "how many
# more this process should do" — so calling
#   run --max-iterations 1                 (fresh)
#   run --max-iterations 2 --resume         (one more)
#   run --max-iterations 3 --resume         (one more)
#   ...
# with a fixed --run-ts across calls does exactly one NEW iteration per call
# and stops cleanly, ready for the next call. `--max-iterations` under
# --interactive means the CEILING (defaults to the spec's own value); the
# stack is brought up once and stays up for the whole interactive session,
# not re-created per iteration. Each call's stdout is still the JSON-lines
# progress cap-evolve normally prints, just one iteration's worth at a time.
#
# Early stop detection: after each call, spent.iterations in
# .capevolve/v4_g2_e1/run_<run-ts>/state.json is compared against the N just
# requested. If it's less than N, the loop stopped for a real reason (a
# budget cap, a stall, or the reward ceiling — budget_exhausted() at the top
# of hill_climb_loop's for-loop) rather than because we only asked for one
# iteration, so the script reports that and exits instead of asking to
# continue past a stop that already happened.
#
# GPFS multi-host collision (CCC_PODMAN_SETUP.md's "Known gaps"): run exactly
# one lane against this $PARSEC_V4N tree at a time — the 5 simulators,
# parsec-live, and _run/skills/ are shared, stateful resources with no
# per-lane isolation.
#
# The stack is torn down by an EXIT trap, so a dying LSF job doesn't leave
# 5 containers and parsec-live holding ports 8000/8086-8090.

set -eo pipefail

: "${PARSEC_V4N:?PARSEC_V4N environment variable is required (see parsec_paths.py)}"
: "${LLM_API_KEY:?LLM_API_KEY environment variable is required by parsec_stack.sh up (the simulators LLM credentials)}"
: "${LLM_API_BASE:?LLM_API_BASE environment variable is required by parsec_stack.sh up}"
: "${HARNESS_LLM_SIMULATION_MODEL:?HARNESS_LLM_SIMULATION_MODEL environment variable is required by parsec_stack.sh up}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -z "${PROJECT_ROOT:-}" ]]; then
  PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
fi

SUITE_ID="v4_g2_e1"
PROJECT_DIR=".capevolve/v4_g2_e1/project"
SPEC="$PROJECT_DIR/capevolve.yaml"
if [[ ! -f "$PROJECT_ROOT/$SPEC" ]]; then
  echo "ERROR: $PROJECT_ROOT/$SPEC not found" >&2
  exit 2
fi

# --------------------------------------------------------------------
# Pull --interactive (and, for it, --run-id/--max-iterations as the
# ceiling) out of "$@" before forwarding the rest to run_ccc_experiment.sh.
# --------------------------------------------------------------------
INTERACTIVE=false
RUN_ID=""
MAX_ITERATIONS=""
PASSTHRU=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --interactive)     INTERACTIVE=true; shift ;;
    --run-id)          RUN_ID="$2"; shift 2 ;;
    --max-iterations)  MAX_ITERATIONS="$2"; shift 2 ;;
    *)                 PASSTHRU+=("$1"); shift ;;
  esac
done
set -- "${PASSTHRU[@]}"

banner() {
  printf '\n============================================================\n'
  printf '%s\n' "$1"
  printf '============================================================\n'
}

banner "parsec v4 (v4_g2_e1, all 34 tasks jointly) on CCC"
echo "Host:          $(hostname)"
echo "Start:         $(date -Iseconds)"
echo "PROJECT_ROOT:  $PROJECT_ROOT"
echo "PARSEC_V4N:    $PARSEC_V4N"
echo "SUITE_ID:      $SUITE_ID"
echo "PROJECT_DIR:   $PROJECT_DIR"
if [[ -n "${LSB_JOBID:-}" ]]; then
  echo "LSF job:       $LSB_JOBID"
fi

# Same arm-before-up, disarm-only-on-rc2 pattern as run_ccc_parsec.sh — see
# that script's comments for why (a signal during the up to 5x60s of
# wait_port plus 5x60s of activation retries must still tear down).
STACK_UP=false
teardown_stack() {
  [[ "$STACK_UP" == true ]] || return 0
  bash "$SCRIPT_DIR/parsec_stack.sh" down || true
}
trap teardown_stack EXIT
STACK_UP=true
set +e
bash "$SCRIPT_DIR/parsec_stack.sh" up
UP_RC=$?
set -e
if (( UP_RC == 2 )); then
  STACK_UP=false
fi
if (( UP_RC != 0 )); then
  echo "FATAL: parsec_stack.sh up failed (rc=$UP_RC)" >&2
  exit "$UP_RC"
fi
bash "$SCRIPT_DIR/parsec_stack.sh" status

if [[ "$INTERACTIVE" != true ]]; then
  banner "Handing off to run_ccc_experiment.sh"
  ARGS=("${PASSTHRU[@]}")
  if [[ -n "$RUN_ID" ]]; then
    ARGS+=(--run-id "$RUN_ID")
  fi
  if [[ -n "$MAX_ITERATIONS" ]]; then
    ARGS+=(--max-iterations "$MAX_ITERATIONS")
  fi
  exec bash "$SCRIPT_DIR/run_ccc_experiment.sh" \
    --suite-id "$SUITE_ID" \
    --spec "$SPEC" \
    --project "$PROJECT_DIR" \
    "${ARGS[@]}"
fi

# --------------------------------------------------------------------
# Interactive mode: one iteration per call, ask before each next one.
# --------------------------------------------------------------------
banner "Interactive mode: one iteration at a time"

if [[ -z "$RUN_ID" ]]; then
  if [[ -n "${LSB_JOBID:-}" ]]; then
    RUN_ID="$LSB_JOBID"
  else
    RUN_ID="local_$(date +%Y%m%d_%H%M%S)"
  fi
fi
RUN_TS="$RUN_ID"   # fixed across every call, so --resume finds the same run dir

if [[ -z "$MAX_ITERATIONS" ]]; then
  MAX_ITERATIONS="$(grep -E '^max_iterations:' "$PROJECT_ROOT/$SPEC" | head -1 | sed -E 's/^max_iterations:[[:space:]]*([0-9]+).*/\1/')"
  if [[ -z "$MAX_ITERATIONS" ]]; then
    echo "ERROR: could not read max_iterations from $SPEC; pass --max-iterations explicitly" >&2
    exit 2
  fi
fi
echo "RUN_TS:            $RUN_TS"
echo "Iteration ceiling: $MAX_ITERATIONS (spec's max_iterations, unless overridden)"

STATE_JSON="$PROJECT_ROOT/.capevolve/v4_g2_e1/run_${RUN_TS}/state.json"

spent_iterations() {
  python3 -c "
import json, sys
try:
    print(json.load(open('$STATE_JSON')).get('spent', {}).get('iterations', 0))
except FileNotFoundError:
    print(0)
"
}

ask_continue() {
  local reply
  if [[ ! -r /dev/tty ]]; then
    echo "ERROR: --interactive needs a controlling terminal to ask; none available (/dev/tty unreadable)." >&2
    exit 2
  fi
  read -r -p "Continue to the next iteration? [y/N] " reply < /dev/tty
  [[ "$reply" =~ ^[Yy]$ ]]
}

# Resuming: re-invoking with the same --run-id (state.json already has
# spent.iterations > 0) picks up at the next iteration instead of restarting.
N=$(( $(spent_iterations) + 1 ))
if (( N > 1 )); then
  echo "Found existing state at $STATE_JSON with $((N - 1)) iteration(s) already done" \
       "— resuming at iteration $N."
fi
while (( N <= MAX_ITERATIONS )); do
  banner "Iteration $N / $MAX_ITERATIONS"
  ITER_ARGS=("${PASSTHRU[@]}" --run-id "$RUN_ID" --run-ts "$RUN_TS" --max-iterations "$N")
  if (( N > 1 )); then
    ITER_ARGS+=(--resume)
  fi
  set +e
  bash "$SCRIPT_DIR/run_ccc_experiment.sh" \
    --suite-id "$SUITE_ID" \
    --spec "$SPEC" \
    --project "$PROJECT_DIR" \
    "${ITER_ARGS[@]}"
  RC=$?
  set -e
  if (( RC != 0 )); then
    echo "FATAL: iteration $N failed (rc=$RC) — see results/$SUITE_ID/$RUN_ID/cap-evolve.log" >&2
    exit "$RC"
  fi

  DONE="$(spent_iterations)"
  echo "spent.iterations after this call: $DONE (requested ceiling this call: $N)"
  if (( DONE < N )); then
    echo "Run stopped before reaching iteration $N (budget exhausted, stalled, or reward" \
         "ceiling reached — see results/$SUITE_ID/$RUN_ID/cap-evolve.log for the stop_reason)."
    break
  fi

  if (( N == MAX_ITERATIONS )); then
    echo "Reached the iteration ceiling ($MAX_ITERATIONS). Nothing more to run without" \
         "raising --max-iterations."
    break
  fi

  ask_continue || { echo "Stopping at your request after iteration $N."; break; }
  N=$((N + 1))
done
