#!/usr/bin/env bash
# Cheap 2-task autonomy smoke (1 trial, 1 iteration) — proves the whole loop
# (check → baseline → optimize → gate → finalize → report → dashboard) end to end.
# Prereq: bash examples/tau2_airline/setup.sh
set -uo pipefail
EX_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$EX_DIR/../.." && pwd)"
PROJECT="$REPO/.capevolve/project"

export PYTHONPATH="$PROJECT/adapters"
export CAPEVOLVE_SKILLS_DIR="$REPO/skills"
export TAU2_MAX_CONCURRENCY="${TAU2_MAX_CONCURRENCY:-2}"
export TAU2_LLM_TIMEOUT="${TAU2_LLM_TIMEOUT:-120}"

"$REPO/.venv/bin/cap-evolve" run \
  --spec "$PROJECT/capevolve.smoke.yaml" --project "$PROJECT" \
  --run-ts smoke --dashboard "${CAPEVOLVE_DASHBOARD:-off}"
