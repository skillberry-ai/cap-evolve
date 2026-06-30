#!/usr/bin/env bash
# Full cap-evolve run on SkillsBench: optimize the four shared office skills, with a
# claude-sonnet-4-6 agent in Docker and a live dashboard.
# Prereq: bash examples/skillsbench/setup.sh  (installs deps + scaffolds + checks).
set -uo pipefail
EX_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$EX_DIR/../.." && pwd)"
PROJECT="$REPO/.capevolve/project"

export PATH="$HOME/.local/bin:$PATH"
export PYTHONPATH="$PROJECT/adapters"
export CAPEVOLVE_SKILLS_DIR="$REPO/skills"
# Stable fixed dir so the ~1.1GB bench dataset cache is reused across all candidate evals.
export SKILLSBENCH_BENCH_CWD="$REPO/.bench_cwd"
export SKILLSBENCH_TASK_TIMEOUT="${SKILLSBENCH_TASK_TIMEOUT:-2400}"

echo "skillsbench commit: $(git -C "$REPO/vendor/skillsbench" rev-parse HEAD 2>/dev/null || echo '?')"
echo "agent under test: claude (Claude Code via ACP) @ claude-sonnet-4-6 | sandbox docker"
echo "optimizer: claude-code @ claude-opus-4-8 | 7 iters · 7 val tasks · 3 trials"
echo "------ pre-run cost preview (spends nothing) ------"
"$REPO/.venv/bin/cap-evolve" estimate --spec "$PROJECT/capevolve.yaml" --project "$PROJECT"
echo "------ cap-evolve run (live dashboard) ------"
"$REPO/.venv/bin/cap-evolve" run \
  --spec "$PROJECT/capevolve.yaml" --project "$PROJECT" \
  --run-ts full --dashboard "${CAPEVOLVE_DASHBOARD:-auto}"
