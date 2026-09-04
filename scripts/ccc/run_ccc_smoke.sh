#!/bin/bash
#
# Smoke-test the CCC batch environment on a SINGLE task + SINGLE trial.
#
# Cheap (~10 min, few cents) way to prove the LSF path — same podman
# setup, same bench command shape, same result-tree layout — before
# committing to a full cap-evolve baseline.
#
# Usage (direct, on an interactive compute node):
#   bash scripts/ccc/run_ccc_smoke.sh --suite-id smoke_batch_v1
#
# Usage (batch, via LSF):
#   bsub -q normal -M 100G -n 1 \
#        -oo "$CCC_LOGS/%J.stdout" -eo "$CCC_LOGS/%J.stderr" \
#        bash scripts/ccc/run_ccc_smoke.sh --suite-id smoke_batch_v1
#
# Options:
#   --suite-id ID    [REQUIRED] result grouping (e.g. "smoke_batch_v1")
#   --run-id ID      unique-within-suite; defaults to $LSB_JOBID or local_<ts>
#   --task NAME      SkillsBench task id (default: invoice-fraud-detection).
#                    Chosen because it passes with the seed skills and is
#                    cheap, so a PASS proves the plumbing. The docs use
#                    offer-letter-generator in their examples instead: that
#                    is the task the v7 base image was built to unblock, so
#                    it exercises the uv/verifier path. Use --task to switch.
#
# Output layout:
#   results/<suite-id>/<run-id>/
#     setup.log                    setup_podman.sh output
#     bench.log                    bench eval run stdout+stderr
#     env_snapshot.txt             .env(redacted) + git commit + podman info
#     bench_jobs/                  bench's --jobs-dir output
#     OUTCOME                      marker file containing PASS/FAIL/ERROR

set -eo pipefail

SUITE_ID=""
RUN_ID=""
TASK="invoice-fraud-detection"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --suite-id) SUITE_ID="$2"; shift 2 ;;
    --run-id)   RUN_ID="$2"; shift 2 ;;
    --task)     TASK="$2"; shift 2 ;;
    -h|--help)  sed -n '2,/^$/p' "$0"; exit 2 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "$SUITE_ID" ]]; then
  echo "ERROR: --suite-id is required" >&2
  exit 2
fi

if [[ -z "$RUN_ID" ]]; then
  if [[ -n "${LSB_JOBID:-}" ]]; then
    RUN_ID="$LSB_JOBID"
  else
    RUN_ID="local_$(date +%Y%m%d_%H%M%S)"
  fi
fi

# Locate project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}"

OUT_DIR="$PROJECT_ROOT/results/$SUITE_ID/$RUN_ID"
mkdir -p "$OUT_DIR"

SETUP_LOG="$OUT_DIR/setup.log"
BENCH_LOG="$OUT_DIR/bench.log"
ENV_SNAP="$OUT_DIR/env_snapshot.txt"

banner() { printf '\n============================================================\n%s\n============================================================\n' "$1"; }

banner "cap-evolve CCC smoke: $SUITE_ID / $RUN_ID (task=$TASK)"
{
  echo "Host:          $(hostname)"
  echo "Start:         $(date -Iseconds)"
  echo "PROJECT_ROOT:  $PROJECT_ROOT"
  echo "OUT_DIR:       $OUT_DIR"
  echo "TASK:          $TASK"
  [[ -n "${LSB_JOBID:-}" ]] && echo "LSF job:       $LSB_JOBID  queue=${LSB_QUEUE:-}  host=${LSB_HOSTS:-}"
} | tee "$ENV_SNAP"

# --- Phase 1: podman setup ---
banner "Phase 1: setup_podman.sh"
# CRITICAL: `source X | tee Y` runs X in a subshell — its `export`s
# would be discarded. Process substitution `> >(tee ...)` keeps `source`
# in the current shell so PATH/DOCKER_HOST/... persist.
# Use the sibling script in this repo. $CCC_SETUP_PODMAN overrides it for
# anyone keeping a patched copy outside the tree.
SETUP_PODMAN="${CCC_SETUP_PODMAN:-$SCRIPT_DIR/setup_podman.sh}"
if [[ ! -r "$SETUP_PODMAN" ]]; then
  echo "FATAL: setup_podman.sh not readable at $SETUP_PODMAN" >&2
  echo "       Set \$CCC_SETUP_PODMAN to override." >&2
  exit 2
fi
# shellcheck disable=SC1090
source "$SETUP_PODMAN" \
    > >(tee "$SETUP_LOG") 2>&1
# Wait a tick so tee finishes flushing to disk before we proceed.
wait 2>/dev/null || true

# Belt-and-suspenders: prepend the docker shim explicitly, in case
# setup_podman.sh's PATH prepend logic regresses.
if [[ -x "$HOME/.local/bin/docker" ]]; then
  export PATH="$HOME/.local/bin:${PATH/#$HOME\/.local\/bin:/}"
fi

# Sanity: docker shim wins PATH?
# Resolve BOTH sides: $HOME often contains a symlink (e.g. /u/<user>
# fronting GPFS), and comparing a resolved path against an unresolved
# one aborts on correctly configured nodes.
if [[ "$(readlink -f "$(command -v docker)")" != "$(readlink -f "$HOME/.local/bin/docker")" ]]; then
  echo "FATAL: 'docker' resolves to $(which docker), not $HOME/.local/bin/docker."
  echo "       PATH ordering is wrong; the run would be corrupted. Aborting."
  echo "ERROR" > "$OUT_DIR/OUTCOME"
  exit 3
fi

# --- Phase 2: load .env ---
banner "Phase 2: loading .env"
if [[ ! -f "$PROJECT_ROOT/.env" ]]; then
  echo "FATAL: $PROJECT_ROOT/.env not found."
  echo "ERROR" > "$OUT_DIR/OUTCOME"
  exit 2
fi
set -a
# shellcheck disable=SC1090
source "$PROJECT_ROOT/.env"
set +a
: "${ANTHROPIC_BASE_URL:?}"
: "${ANTHROPIC_AUTH_TOKEN:?}"
: "${SKILLSBENCH_TASKS_DIR:?}"

# Snapshot config
{
  echo
  echo "===== .env (redacted) ====="
  # Denylist redaction is unsafe here: a *_SECRET / *_PASSWORD / Authorization
  # line would go to disk in cleartext. Invert it — redact every value except
  # an explicit list of keys known to be non-secret.
  awk -F= '
    /^[[:space:]]*(#|$)/ { print; next }
    {
      key = $1
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", key)
      if (key ~ /^(SKILLSBENCH_(AGENT|MODEL|TASKS_DIR|SANDBOX_USER)|CAPEVOLVE_[A-Z_]+|DOCKER_HOST)$/)
        print
      else
        print key "=<REDACTED>"
    }' "$PROJECT_ROOT/.env"
  echo
  echo "===== git commit ====="
  ( cd "$PROJECT_ROOT" && git log -1 --format='commit %H%n%s' 2>&1 || echo "(not a git repo)" )
  echo
  echo "===== podman info | head -30 ====="
  podman info 2>&1 | head -30
} >> "$ENV_SNAP"

# --- Phase 3: run bench ---
banner "Phase 3: bench eval run --include $TASK"
JOBS="$OUT_DIR/bench_jobs"
rm -rf "$JOBS"

# SECURITY: --agent-env puts the bearer token on bench's argv, which on a
# shared cluster is readable by any other user via `ps -ef`, and can land in
# bench.log if bench ever echoes its own invocation. benchflow 0.6.5 has no
# env-file passthrough, so this is the only route today — but treat the token
# as exposed for the lifetime of the process, and rotate it if that matters.
set +e
stdbuf -oL -eL bench eval run \
  --tasks-dir "$SKILLSBENCH_TASKS_DIR" \
  --include "$TASK" \
  --agent claude-agent-acp --model claude-opus-4-6 \
  --sandbox docker --sandbox-user '' \
  --skill-mode with-skill \
  --skills-dir "$PROJECT_ROOT/.capevolve/project/seed_capability" \
  --jobs-dir "$JOBS" \
  --agent-env "ANTHROPIC_BASE_URL=$ANTHROPIC_BASE_URL" \
  --agent-env "ANTHROPIC_AUTH_TOKEN=$ANTHROPIC_AUTH_TOKEN" 2>&1 | tee "$BENCH_LOG"
RC="${PIPESTATUS[0]}"
set -e

# --- Phase 4: summarize + mark outcome ---
banner "Phase 4: results"
echo "End:   $(date -Iseconds)"
echo "Exit:  $RC"

# Exactly one result.json is expected: $JOBS was rm -rf'd above and this
# is a single-task, single-trial run. `head -1` is arbitrary-but-fine here;
# it is NOT "newest" (find returns filesystem order). If this script ever
# grows multiple trials, select deliberately instead.
RESULT_JSON=$(find "$JOBS" -name result.json 2>/dev/null | head -1)
if [[ -z "$RESULT_JSON" ]]; then
  echo "No result.json produced — bench never got to a rollout."
  echo "ERROR" > "$OUT_DIR/OUTCOME"
  exit "${RC:-1}"
fi

echo
echo "===== result summary ====="
python3 -c "
import json
d = json.load(open('$RESULT_JSON'))
ar = d.get('agent_result',{}) or {}
err = d.get('error') or 'None'
r = d.get('rewards') or 'None'
print(f'rollout:      {d.get(\"rollout_name\")}')
print(f'error:        {str(err)[:200]}')
print(f'error_category:{d.get(\"error_category\")}')
print(f'rewards:      {r}')
print(f'tool_calls:   {d.get(\"n_tool_calls\")}')
print(f'out_tokens:   {ar.get(\"n_output_tokens\")}')
print(f'in_tokens:    {ar.get(\"n_input_tokens\")}')
print(f'cost_usd:     {ar.get(\"cost_usd\")}')
print(f'timing:       {d.get(\"timing\")}')"

# Decide outcome
OUTCOME=$(python3 -c "
import json
d = json.load(open('$RESULT_JSON'))
err = d.get('error')
rewards = d.get('rewards') or {}
reward = rewards.get('reward') if isinstance(rewards, dict) else None
if err:
    print('ERROR')
elif reward == 1.0:
    print('PASS')
elif reward == 0.0:
    print('FAIL')
else:
    print('UNKNOWN')
")
echo "$OUTCOME" > "$OUT_DIR/OUTCOME"
echo
echo "OUTCOME: $OUTCOME"
echo "Results: $OUT_DIR"

# Exit 0 on PASS/FAIL (plumbing works), non-zero on ERROR
case "$OUTCOME" in
  PASS|FAIL) exit 0 ;;
  *)         exit 1 ;;
esac
