#!/usr/bin/env bash
# Launch (or resume) the cap-evolve arm with the optimizer isolated (README: Isolation).
#   bash launch_cape_hc.sh [BASE] [extra cap-evolve run args]   # BASE default: $AW_EVAL/.capevolve
#   AW_RUN_TS=20261118_171500 bash launch_cape_hc.sh "" --resume  # resume that run in place
# Every launch is a new run folder BASE/run_<YYYYMMDD_HHMMSS> next to BASE/project (tau2's layout),
# named by its start time as cap-evolve names runs by default (AW_RUN_TS overrides the name).
# AW_ISOLATION=sandbox (default: Claude Code's built-in sandbox) or namespace (the fallback where
# bubblewrap cannot start). Run scripts/check_optimizer_isolation.sh $AW_ISOLATION first: launch
# refuses to start without a passing report for that mode newer than the rendered settings.
set -euo pipefail
EX="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="$(cd "$EX/../../../.." && pwd)"
AW_EVAL="${AW_EVAL:-/tmp/aw_eval}"
BASE="${1:-}"; [ $# -gt 0 ] && shift
BASE="${BASE:-$AW_EVAL/.capevolve}"
P="$BASE/project"
TS="${AW_RUN_TS:-$(date +%Y%m%d_%H%M%S)}"
# the optimizer lints from this cache: root_opt is hidden from it (README: Isolation)
[ -f "$AW_EVAL/lint_cache.json" ] || { echo "missing $AW_EVAL/lint_cache.json: run scripts/make_roots.py" >&2; exit 1; }
[ -f "$P/capevolve.yaml" ] || { echo "no project at $P: run scripts/setup_project.sh $BASE" >&2; exit 1; }
echo "run: $BASE/run_$TS   (log: $AW_EVAL/progress/$TS.out)"
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
# TEMPORARY (dev only): AW_SKIP_ISOLATION_GATE=1 skips the planted-secret gate while the WSL
# /mnt/wslg/distro hole in ../sandbox/ns_exec.sh is open. The namespace still applies.
if [ "${AW_SKIP_ISOLATION_GATE:-0}" = 1 ]; then
  echo "WARNING: isolation gate SKIPPED (AW_SKIP_ISOLATION_GATE=1) - optimizer isolation is NOT verified" >&2
else
  "${AW_VENV:-$AW_EVAL/.venv}/bin/python" "$EX/scripts/isolation_gate.py" "$AW_EVAL" "$AW_ISOLATION" "$SETTINGS" \
    || { echo "run: bash $EX/scripts/check_optimizer_isolation.sh $AW_ISOLATION (it must PASS)" >&2; exit 1; }
fi
export PATH="$EX/sandbox:$PATH" AW_ISOLATION AW_CLAUDE_SETTINGS="$SETTINGS"
export AW_NS_TRANSCRIPTS="$AW_EVAL/runs/optimizer_transcripts/$TS"
# AW_SPEC: a spec file in the project other than capevolve.yaml (scripts/itest.sh uses capevolve.itest.yaml)
exec "${AW_VENV:-$AW_EVAL/.venv}/bin/cap-evolve" run --spec "$P/${AW_SPEC:-capevolve.yaml}" --project "$P" --run-ts "$TS" \
  --dashboard off --follow "$@" >> "$AW_EVAL/progress/$TS.out" 2>&1
