#!/usr/bin/env bash
# Scaffold the cape-hc cap-evolve project (README: cap-evolve arm) and run the hard gate.
#   bash setup_project.sh RUN_DIR     e.g. /tmp/aw_eval/runs/cape_hc_s0
set -euo pipefail
EX="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="$(cd "$EX/../../../.." && pwd)"
AW_EVAL="${AW_EVAL:-/tmp/aw_eval}"
PY="$AW_EVAL/venv-aw/bin/python"
RUN_DIR="${1:?run dir}"
OPT_MODEL="${OPT_MODEL:-aws/claude-sonnet-5-5}"
PROJECT="$RUN_DIR/.capevolve/project"
LINT_CACHE="$AW_EVAL/lint_cache.json"
[ -f "$LINT_CACHE" ] || { echo "missing $LINT_CACHE: run scripts/make_roots.py first" >&2; exit 1; }

"$PY" "$REPO/skills/phases/intake/scripts/run.py" --base "$RUN_DIR/.capevolve" --workdir "$EX" --force >/dev/null
mkdir -p "$PROJECT/adapters" "$PROJECT/optimizer" "$PROJECT/reference"
cp "$EX/adapters/adapter.py" "$EX/adapters/aw_agent.py" "$EX/adapters/lints.py" "$PROJECT/adapters/"
rm -rf "$PROJECT/seed_capability"; cp -R "$EX/seed_capability" "$PROJECT/seed_capability"
cp "$AW_EVAL/reference/api_index.md" "$AW_EVAL/reference/react_agent_notes.md" "$PROJECT/reference/"
"$PY" "$EX/scripts/make_splits.py" "$PROJECT/split_ids.json"
INSTR="$PROJECT/optimizer/INSTRUCTIONS.md"
sed -e "s|{AW_REFERENCE}|$AW_EVAL/reference|g" -e "s|{AW_LINT_CACHE}|$LINT_CACHE|g" \
    -e "s|{AW_PY}|$PY|g" -e "s|{AW_LINTS}|$EX/adapters/lints.py|g" \
    "$EX/optimizer/INSTRUCTIONS.template.md" > "$INSTR"
sed -e "s|@OPT_MODEL@|$OPT_MODEL|" -e "s|@INSTRUCTIONS@|$INSTR|" -e "s|@AW_EVAL@|$AW_EVAL|g" "$EX/capevolve.yaml" > "$PROJECT/capevolve.yaml"
mkdir -p "$PROJECT/sandbox"
for t in optimizer-permissions optimizer-sandbox; do
  sed -e "s|@AW_EVAL@|$AW_EVAL|g" -e "s|@AW_SECRETS_FILE@|${AW_SECRETS_FILE:-$REPO/.env}|g" \
      "$EX/sandbox/$t.template.json" > "$PROJECT/sandbox/$t.json"
done
cat > "$PROJECT/PROJECT.md" <<MD
# cape-hc: AppWorld (official splits), gpt-oss-120b on RITS, hill-climb --focus all

Example: benchmarks/appworld/examples/react_agent/README.md (repo $REPO). Resolved inputs:
- capability: system-prompt + tools (seed: stock AppWorld ReAct prompt @ 42b5bcf, empty helpers, no notes)
- target: openai/gpt-oss-120b-a100 on RITS, reasoning medium, temperature 0 (adapters/aw_agent.py MODEL_CONFIG)
- optimizer: claude-code, $OPT_MODEL; instructions: $INSTR
- data: adapter tasks(); split_ids.json train = val = official train ∪ dev (147), test = []
- AppWorld root at search time: $AW_EVAL/root_opt (no test files)
- gate: paired, k = 1.0; 1 trial; 6 iterations; max_metric_calls 1050; max_optimizer_usd 120
MD
cd "$PROJECT"
PYTHONPATH="$PROJECT/adapters" CAPEVOLVE_SKILLS_DIR="$REPO/skills" APPWORLD_ROOT="$AW_EVAL/root_opt" \
  "$AW_EVAL/venv-aw/bin/cap-evolve" check "$PROJECT"
