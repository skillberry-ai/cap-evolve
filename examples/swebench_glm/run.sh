#!/usr/bin/env bash
# Harbor + cap-evolve on OpenShift via AI gateway (GLM).
#
# This is the exact script used to produce run_full/ (SWE-bench Verified, 500 tasks,
# GLM-5.3 agent + optimizer, unlimited turns). It expects a ./.capevolve/project
# already scaffolded per the Harbor adapter docs (see ../../docs), with this
# directory's capevolve.yaml and seed_capability/ copied into
# .capevolve/project/adapters/ and .capevolve/project/seed_capability respectively,
# plus an optimizer-claude/settings.json configuring the GLM `behavesAs`.
#
# Prereqs: .venv, harbor on PATH, oc login, ANTHROPIC_API_KEY
# Usage:
#   export ANTHROPIC_API_KEY='sk-oai-...'
#   ./run.sh                                              # pilot (50)
#   HARBOR_TASK_IDS_FILE=.../task_ids_mini.txt RUN_TS=x ./run.sh
set -euo pipefail

if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
  echo "error: do not source run.sh — run it as ./run.sh" >&2
  return 1 2>/dev/null || exit 1
fi

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT="$REPO/.capevolve/project"
SPEC="$PROJECT/adapters/capevolve.yaml"
CAPEVOLVE="${CAPEVOLVE:-$REPO/.venv/bin/cap-evolve}"
OPTIMIZER_CLAUDE_DIR="$PROJECT/optimizer-claude"
GLM="rits/zai-org/glm-5-3"
# Internal dogfood gateway — set your own ANTHROPIC_BASE_URL when reproducing.
GATEWAY="${ANTHROPIC_BASE_URL:-}"

HARBOR="${HARBOR_BIN:-}"
[ -x "$HARBOR" ] || HARBOR="$(command -v harbor 2>/dev/null || true)"
[ -x "${HARBOR:-}" ] || { echo "error: harbor CLI not found" >&2; exit 1; }
[ -x "$CAPEVOLVE" ] || { echo "error: $CAPEVOLVE not found — pip install ./core" >&2; exit 1; }
[ -f "$SPEC" ] || { echo "error: missing $SPEC" >&2; exit 1; }
[ -n "${ANTHROPIC_API_KEY:-}" ] || { echo "error: set ANTHROPIC_API_KEY" >&2; exit 1; }
[ -f "$OPTIMIZER_CLAUDE_DIR/settings.json" ] || {
  echo "error: missing $OPTIMIZER_CLAUDE_DIR/settings.json (GLM behavesAs)" >&2
  exit 1
}

# Seed onboarding so headless claude -p does not hang.
CLAUDE_JSON="$OPTIMIZER_CLAUDE_DIR/.claude.json"
if [ ! -f "$CLAUDE_JSON" ] || ! grep -q '"hasCompletedOnboarding": true' "$CLAUDE_JSON" 2>/dev/null; then
  printf '%s\n' '{"hasCompletedOnboarding":true,"migrationVersion":14}' > "$CLAUDE_JSON"
fi

TASK_IDS_FILE="${HARBOR_TASK_IDS_FILE:-$PROJECT/adapters/task_ids_pilot.txt}"
RUN_TS="${RUN_TS:-swebench-pilot}"
MODEL="${HARBOR_MODEL:-$GLM}"

# Harbor (OpenShift evals)
export HARBOR_BIN="$HARBOR"
export HARBOR_DATASET="${HARBOR_DATASET:-swe-bench/swe-bench-verified}"
export HARBOR_AGENT="${HARBOR_AGENT:-claude-code}"
export HARBOR_MODEL="$MODEL"
export HARBOR_PARALLEL="${HARBOR_PARALLEL:-16}"
export HARBOR_TIMEOUT="${HARBOR_TIMEOUT:-1800}"
export HARBOR_EXTRA_FLAGS="${HARBOR_EXTRA_FLAGS:--e openshift}"
export HARBOR_TASK_IDS="$(tr '\n' ',' < "$TASK_IDS_FILE" | sed 's/,$//')"
export HARBOR_AGENT_BASE_URL="$GATEWAY"
export HARBOR_AGENT_API_KEY="$ANTHROPIC_API_KEY"

# Optimizer (local claude-code → same gateway; behavesAs in CLAUDE_CONFIG_DIR)
unset CLAUDE_CODE_USE_VERTEX CLOUD_ML_REGION ANTHROPIC_VERTEX_PROJECT_ID
export ANTHROPIC_BASE_URL="$GATEWAY"
export ANTHROPIC_API_KEY
export CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY=1
export CLAUDE_CONFIG_DIR="$OPTIMIZER_CLAUDE_DIR"

export PYTHONPATH="$PROJECT/adapters:$REPO"
export CAPEVOLVE_SKILLS_DIR="$REPO/skills"
export GIT_EDITOR=true

echo "==> Harbor: $HARBOR_AGENT @ $HARBOR_MODEL (OpenShift)"
echo "==> Optimizer: $MODEL via $CLAUDE_CONFIG_DIR"
echo "==> Tasks: $(echo "$HARBOR_TASK_IDS" | tr ',' '\n' | wc -l) ($(basename "$TASK_IDS_FILE"))"
echo "==> Run: .capevolve/run_${RUN_TS}"

exec "$CAPEVOLVE" run \
  --spec "$SPEC" \
  --project "$PROJECT" \
  --run-ts "$RUN_TS" \
  --dashboard "${CAPEVOLVE_DASHBOARD:-auto}"
