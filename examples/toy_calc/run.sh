#!/usr/bin/env bash
# Run the toy_calc example end-to-end (zero-API, deterministic).
# Usage: cd <repo-root> && bash examples/toy_calc/run.sh
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
export AGENT_CAPO_CORE="$REPO/core"
export PYTHONPATH="$REPO/core"
export ACAPO_SKILLS_DIR="$REPO/skills"
export ACAPO_TOY_DATA="$REPO/examples/toy_calc"
export ACAPO_MOCK_SCRIPT="$REPO/examples/toy_calc/mock_script.json"

D="$(mktemp -d -t toy_calc.XXXXXX)"
mkdir -p "$D/.agentcapo/project/adapters"
cp "$REPO/examples/toy_calc/adapter.py"   "$D/.agentcapo/project/adapters/"
cp -R "$REPO/examples/toy_calc/capability" "$D/seed_capability"
cp "$REPO/templates/project/acapo.yaml"   "$D/.agentcapo/project/acapo.yaml"

echo "Working directory: $D"
python3 -m agent_capo.cli run \
  --spec    "$D/.agentcapo/project/acapo.yaml" \
  --project "$D/.agentcapo/project" \
  --run-ts  demo
