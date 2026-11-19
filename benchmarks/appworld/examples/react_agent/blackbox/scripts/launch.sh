#!/usr/bin/env bash
# Launch (or resume) an AppWorld blackbox run, with the optimizer isolated (README: Running).
#
#   bash scripts/launch.sh [BASE] [extra cap-evolve run args]   # BASE default: $AW_EVAL/.capevolve-blackbox
#   AW_SPEC=capevolve.smoke.yaml bash scripts/launch.sh          # one task, one trial, one iteration
#   AW_RUN_TS=20261118_171500 bash scripts/launch.sh "" --resume # resume that run in place
#
# Every launch is a new run folder BASE/run_<YYYYMMDD_HHMMSS> next to BASE/project, named by its
# start time as cap-evolve names runs by default (AW_RUN_TS overrides the name).
#
# The model the proxy calls comes from the direct approach's AW_* variables (README: Models):
# AW_MODEL_NAME, AW_MODEL_URL, AW_KEY_HEADER=bearer, AW_KEY_ENV (its value read from AW_SECRETS_FILE).
# AW_ISOLATION=sandbox (default) or namespace, exactly as in the direct approach: run
# ../scripts/check_optimizer_isolation.sh $AW_ISOLATION first (it must PASS).
set -euo pipefail

EX="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"     # this approach (blackbox/)
DIRECT="$(cd "$EX/.." && pwd)"                            # the direct approach: its sandbox and gate
REPO="$(cd "$EX/../../../../.." && pwd)"
AW_EVAL="${AW_EVAL:-/tmp/aw_eval}"
BASE="${1:-}"; [ $# -gt 0 ] && shift
BASE="${BASE:-$AW_EVAL/.capevolve-blackbox}"
P="$BASE/project"
TS="${AW_RUN_TS:-$(date +%Y%m%d_%H%M%S)}"
SPEC="${AW_SPEC:-capevolve.yaml}"
PY="$AW_EVAL/venv-aw/bin/python"
OUT_LOG="$AW_EVAL/progress/$TS.out"

say(){ printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }
die(){ printf '\n\033[1;31mLAUNCH FAILED: %s\033[0m\n' "$*" >&2; exit 1; }

say "1/4  Preconditions"
[ -f "$AW_EVAL/lint_cache.json" ]             || die "missing $AW_EVAL/lint_cache.json: run ../scripts/make_roots.py"
[ -f "$P/seed_capability/my_skill/SKILL.md" ] || die "no project at $P: run scripts/setup_project.sh $BASE"
[ -f "$P/$SPEC" ]                             || die "no $P/$SPEC"
echo "  project $P, spec $SPEC"

cd "$P"
export PYTHONPATH="$P/adapters" CAPEVOLVE_SKILLS_DIR="$REPO/skills"
export LITELLM_LOCAL_MODEL_COST_MAP=True
export AW_SECRETS_FILE="${AW_SECRETS_FILE:-$REPO/.env}" AW_EXPERIMENT="$TS" AW_WORKERS="${AW_WORKERS:-24}"
export AW_EVAL AW_LINT_CACHE="$AW_EVAL/lint_cache.json" AW_APP_DESCRIPTIONS="$AW_EVAL/app_descriptions.json"
export AW_PROGRESS_LOG="$AW_EVAL/progress/$TS.log" AW_TRIAL=blackbox AW_PHASE=eval

say "2/4  The model, and the Skillberry store"
# Fail fast, before any spend, when the AW_* model cannot be served through the proxy (bearer key).
"$PY" -c "import appworld_tailoring as t; t.spa_upstream_env()" \
  || die "the AW_* model settings cannot be served through the proxy (README: Models)"
# The model key stays in AW_SECRETS_FILE: the adapter reads it only to hand it to the proxy.
unset "${AW_KEY_ENV:-RITS_API_KEY}"
# The store must be up before the run's preflight; the adapter (re)starts the proxy per candidate.
"$PY" -c "import appworld_tailoring as t; t.blackbox_env().start_store()" || die "the store did not start"

say "3/4  Isolation gate (${AW_ISOLATION:-sandbox})"
# every optimizer call runs through ../sandbox/claude, isolated by AW_ISOLATION
AW_ISOLATION="${AW_ISOLATION:-sandbox}"
case "$AW_ISOLATION" in
  sandbox)   SETTINGS="$P/sandbox/optimizer-sandbox.json" ;;
  namespace) SETTINGS="$P/sandbox/optimizer-permissions.json" ;;
  *) die "AW_ISOLATION must be sandbox or namespace" ;;
esac
# TEMPORARY (dev only): AW_SKIP_ISOLATION_GATE=1 skips the planted-secret gate while the WSL
# /mnt/wslg/distro hole in ../sandbox/ns_exec.sh is open. The namespace still applies.
if [ "${AW_SKIP_ISOLATION_GATE:-0}" = 1 ]; then
  echo "WARNING: isolation gate SKIPPED (AW_SKIP_ISOLATION_GATE=1) - optimizer isolation is NOT verified" >&2
else
  "$PY" "$DIRECT/scripts/isolation_gate.py" "$AW_EVAL" "$AW_ISOLATION" "$SETTINGS" \
    || die "run: bash $DIRECT/scripts/check_optimizer_isolation.sh $AW_ISOLATION (it must PASS)"
fi

say "4/4  cap-evolve run"
mkdir -p "$AW_EVAL/progress"
export PATH="$DIRECT/sandbox:$PATH" AW_ISOLATION AW_CLAUDE_SETTINGS="$SETTINGS"
export AW_NS_TRANSCRIPTS="$AW_EVAL/runs/optimizer_transcripts/$TS"
echo "  run: $BASE/run_$TS"
echo "  log: $OUT_LOG"
exec "$AW_EVAL/venv-aw/bin/cap-evolve" run --spec "$P/$SPEC" --project "$P" --run-ts "$TS" \
  --dashboard off --follow "$@" >> "$OUT_LOG" 2>&1
