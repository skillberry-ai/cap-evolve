#!/usr/bin/env bash
# Full cap-evolve run on tau2-bench airline via IBM RITS, with a live dashboard.
# Prereq: bash examples/tau2_airline/setup.sh  (installs deps + scaffolds + checks).
set -uo pipefail
EX_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$EX_DIR/../.." && pwd)"
PROJECT="$REPO/.capevolve/project"

export PYTHONPATH="$PROJECT/adapters"
export CAPEVOLVE_SKILLS_DIR="$REPO/skills"
export TAU2_MAX_CONCURRENCY="${TAU2_MAX_CONCURRENCY:-100}"
export TAU2_LLM_TIMEOUT="${TAU2_LLM_TIMEOUT:-240}"
export TAU2_LLM_RETRIES="${TAU2_LLM_RETRIES:-2}"
export TAU2_INFRA_RETRIES="${TAU2_INFRA_RETRIES:-2}"

echo "tau2-bench commit: $(cat "$EX_DIR/run_full/TAU2_COMMIT.txt" 2>/dev/null || echo '?')"
echo "optimizer: claude-code @ claude-opus-4-6 | 10 iters · 50 tasks · 10 trials · concurrency $TAU2_MAX_CONCURRENCY"
echo "------ pre-run cost preview (spends nothing) ------"
"$REPO/.venv/bin/cap-evolve" estimate --spec "$PROJECT/capevolve.yaml" --project "$PROJECT"
echo "------ cap-evolve run (live dashboard) ------"
"$REPO/.venv/bin/cap-evolve" run \
  --spec "$PROJECT/capevolve.yaml" --project "$PROJECT" \
  --run-ts full --dashboard "${CAPEVOLVE_DASHBOARD:-auto}"
