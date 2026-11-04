#!/usr/bin/env bash
# Launch (or resume) the cap-evolve arm with the optimizer isolated (README: Isolation).
#   bash launch_cape_hc.sh RUN_DIR [extra cap-evolve run args, e.g. --resume]
# AW_ISOLATION=sandbox (default: Claude Code's built-in sandbox) or namespace (the fallback where
# bubblewrap cannot start). Run scripts/check_optimizer_isolation.sh $AW_ISOLATION first: launch
# refuses to start without a passing report for that mode newer than the rendered settings.
set -euo pipefail
EX="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="$(cd "$EX/../.." && pwd)"
AW_EVAL="${AW_EVAL:-/tmp/aw_eval}"
RUN_DIR="${1:?run dir}"; shift
P="$RUN_DIR/.capevolve/project"
TS="${AW_RUN_TS:-$(basename "$RUN_DIR")}"
# the optimizer lints from this cache: root_opt is hidden from it (README: Isolation)
[ -f "$AW_EVAL/lint_cache.json" ] || { echo "missing $AW_EVAL/lint_cache.json: run scripts/make_roots.py" >&2; exit 1; }
mkdir -p "$AW_EVAL/progress"
cd "$P"
export PYTHONPATH="$P/adapters" CAPEVOLVE_SKILLS_DIR="$REPO/skills"
export AW_SECRETS_FILE="${AW_SECRETS_FILE:-$REPO/.env}" AW_EXPERIMENT="$TS" AW_WORKERS="${AW_WORKERS:-24}"
export AW_EVAL AW_LINT_CACHE="$AW_EVAL/lint_cache.json"
export AW_PROGRESS_LOG="$AW_EVAL/progress/$TS.log" AW_TRIAL=cape-hc AW_PHASE=eval
unset "${AW_KEY_ENV:-RITS_API_KEY}"
# every optimizer call runs through sandbox/claude, isolated by AW_ISOLATION
AW_ISOLATION="${AW_ISOLATION:-sandbox}"
case "$AW_ISOLATION" in
  sandbox) SETTINGS="$P/sandbox/optimizer-sandbox.json" ;;
  namespace) SETTINGS="$P/sandbox/optimizer-permissions.json" ;;
  *) echo "AW_ISOLATION must be sandbox or namespace" >&2; exit 1 ;;
esac
"$AW_EVAL/venv-aw/bin/python" "$EX/scripts/isolation_gate.py" "$AW_EVAL" "$AW_ISOLATION" "$SETTINGS" \
  || { echo "run: bash $EX/scripts/check_optimizer_isolation.sh $AW_ISOLATION (it must PASS)" >&2; exit 1; }
export PATH="$EX/sandbox:$PATH" AW_ISOLATION AW_CLAUDE_SETTINGS="$SETTINGS"
export AW_NS_TRANSCRIPTS="$AW_EVAL/runs/optimizer_transcripts/$TS"
exec "$AW_EVAL/venv-aw/bin/cap-evolve" run --spec "$P/capevolve.yaml" --project "$P" --run-ts "$TS" \
  --dashboard off --follow "$@" >> "$AW_EVAL/progress/$TS.out" 2>&1
