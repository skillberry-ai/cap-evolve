#!/usr/bin/env bash
# Run the toy_calc example end-to-end (zero-API, deterministic).
# Usage: cd <repo-root> && bash examples/toy_calc/run.sh
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
export CAPEVOLVE_CORE="$REPO/core"
export PYTHONPATH="$REPO/core"
export CAPEVOLVE_SKILLS_DIR="$REPO/skills"
export CAPEVOLVE_TOY_DATA="$REPO/examples/toy_calc"
export CAPEVOLVE_MOCK_SCRIPT="$REPO/examples/toy_calc/mock_script.json"

D="$(mktemp -d -t toy_calc.XXXXXX)"
mkdir -p "$D/.capevolve/project/adapters"
cp "$REPO/examples/toy_calc/adapter.py"   "$D/.capevolve/project/adapters/"
cp -R "$REPO/examples/toy_calc/capability" "$D/seed_capability"
cp "$REPO/templates/project/capevolve.yaml"   "$D/.capevolve/project/capevolve.yaml"
# The spec names optimizer/INSTRUCTIONS.md; ship it, or the run warns and hands the
# optimizer cap-evolve's generic template instead of the project's own.
cp -R "$REPO/templates/project/optimizer" "$D/.capevolve/project/optimizer"

echo "Working directory: $D"
python3 -m cap_evolve.cli run \
  --spec    "$D/.capevolve/project/capevolve.yaml" \
  --project "$D/.capevolve/project" \
  --run-ts  demo
