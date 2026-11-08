#!/usr/bin/env bash
# Cheap 1-task autonomy smoke (1 val task, 1 trial, 1 iteration) — proves the whole
# loop (check → baseline → optimize → gate → finalize → report) end to end, with a
# real sonnet agent in Docker and a verifier reward coming back.
# Prereq: bash examples/skillsbench/setup.sh
set -uo pipefail
EX_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$EX_DIR/../.." && pwd)"
PROJECT="$REPO/.capevolve/project"

export PATH="$HOME/.local/bin:$PATH"
export PYTHONPATH="$PROJECT/adapters"
export CAPEVOLVE_SKILLS_DIR="$REPO/skills"
# Stable fixed dir so the bench dataset cache (.cache/datasets) is reused across evals.
export SKILLSBENCH_BENCH_CWD="$REPO/.bench_cwd"
export SKILLSBENCH_TASK_TIMEOUT="${SKILLSBENCH_TASK_TIMEOUT:-2400}"

"$REPO/.venv/bin/cap-evolve" run \
  --spec "$PROJECT/capevolve.smoke.yaml" --project "$PROJECT" \
  --run-ts smoke --dashboard "${CAPEVOLVE_DASHBOARD:-off}"
