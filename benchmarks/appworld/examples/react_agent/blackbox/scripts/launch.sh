#!/usr/bin/env bash
# Launch (or resume) an AppWorld blackbox run, with the optimizer isolated (README: Running).
#
#   bash scripts/launch.sh [BASE] [extra cap-evolve run args]    # BASE default: $AW_EVAL/.capevolve-blackbox
#   AW_SPEC=capevolve.smoke.yaml bash scripts/launch.sh           # one task, one trial, one iteration
#   AW_RUN_TS=20261118_171500 bash scripts/launch.sh "" --resume  # resume that run in place
#
# Every launch is a new run folder, BASE/run_<YYYYMMDD_HHMMSS>, next to BASE/project. It is named by
# its start time, as cap-evolve names runs by default (AW_RUN_TS overrides the name).
#
# The model the proxy calls comes from the direct approach's AW_* variables (README: Models):
#   AW_MODEL_NAME, AW_MODEL_URL, AW_KEY_HEADER=bearer, and AW_KEY_ENV (its value is read from
#   AW_SECRETS_FILE).
# AW_ISOLATION is sandbox (the default) or namespace, exactly as in the direct approach. Run
#   ../scripts/check_optimizer_isolation.sh $AW_ISOLATION   first: it must PASS.
set -euo pipefail

# ---- where things are ---------------------------------------------------------------------------
EX="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"     # this approach (blackbox/)
DIRECT="$(cd "$EX/.." && pwd)"                            # the direct approach: its sandbox and gate
REPO="$(cd "$EX/../../../../.." && pwd)"
AW_EVAL="${AW_EVAL:-/tmp/aw_eval}"

# The first argument, when given, is BASE; everything after it goes to `cap-evolve run`.
BASE="${1:-}"
[ $# -gt 0 ] && shift
BASE="${BASE:-$AW_EVAL/.capevolve-blackbox}"

P="$BASE/project"
TS="${AW_RUN_TS:-$(date +%Y%m%d_%H%M%S)}"                 # the run's name: run_$TS
SPEC="${AW_SPEC:-capevolve.yaml}"
PY="${AW_VENV:-$AW_EVAL/.venv}/bin/python"
OUT_LOG="$AW_EVAL/progress/$TS.out"

say(){ printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }
die(){ printf '\n\033[1;31mLAUNCH FAILED: %s\033[0m\n' "$*" >&2; exit 1; }


say "1/4  Preconditions"
[ -f "$AW_EVAL/lint_cache.json" ] \
  || die "missing $AW_EVAL/lint_cache.json: run ../scripts/make_roots.py"
[ -f "$P/seed_capability/my_skill/SKILL.md" ] \
  || die "no project at $P: run scripts/setup_project.sh $BASE"
[ -f "$P/$SPEC" ] \
  || die "no $P/$SPEC"
echo "  project $P, spec $SPEC"

# Everything below runs from the project, with its adapters importable.
cd "$P"
export PYTHONPATH="$P/adapters"
export CAPEVOLVE_SKILLS_DIR="$REPO/skills"
export LITELLM_LOCAL_MODEL_COST_MAP=True
export AW_SECRETS_FILE="${AW_SECRETS_FILE:-$REPO/.env}"
export AW_EXPERIMENT="$TS"
export AW_WORKERS="${AW_WORKERS:-5}"                      # episodes in parallel (each with its own environment server)
export AW_EVAL
export AW_LINT_CACHE="$AW_EVAL/lint_cache.json"
export AW_APP_DESCRIPTIONS="$AW_EVAL/app_descriptions.json"
export AW_PROGRESS_LOG="$AW_EVAL/progress/$TS.log"
export AW_TRIAL=blackbox
export AW_PHASE=eval


say "2/4  The model, and the Skillberry store"
# Fail fast, before any spend, when the AW_* model cannot be served through the proxy (bearer key).
"$PY" -c "import appworld_tailoring as t; t.spa_upstream_env()" \
  || die "the AW_* model settings cannot be served through the proxy (README: Models)"

# The model key stays in AW_SECRETS_FILE: the adapter reads it only to hand it to the proxy.
unset "${AW_KEY_ENV:-RITS_API_KEY}"

# The store must be up before the run's preflight; the adapter (re)starts the proxy per candidate.
"$PY" -c "import appworld_tailoring as t; t.blackbox_env().start_store()" \
  || die "the store did not start"


say "3/4  Isolation gate (${AW_ISOLATION:-sandbox})"
# Every optimizer call runs through ../sandbox/claude, isolated as AW_ISOLATION says.
AW_ISOLATION="${AW_ISOLATION:-sandbox}"
case "$AW_ISOLATION" in
  sandbox)   SETTINGS="$P/sandbox/optimizer-sandbox.json" ;;
  namespace) SETTINGS="$P/sandbox/optimizer-permissions.json" ;;
  *)         die "AW_ISOLATION must be sandbox or namespace" ;;
esac

# TEMPORARY (dev only): AW_SKIP_ISOLATION_GATE=1 skips the planted-secret gate while the WSL
# /mnt/wslg/distro hole in ../sandbox/ns_exec.sh is open. The namespace itself still applies.
if [ "${AW_SKIP_ISOLATION_GATE:-0}" = 1 ]; then
  echo "WARNING: isolation gate SKIPPED (AW_SKIP_ISOLATION_GATE=1) - optimizer isolation is NOT verified" >&2
else
  "$PY" "$DIRECT/scripts/isolation_gate.py" "$AW_EVAL" "$AW_ISOLATION" "$SETTINGS" \
    || die "run: bash $DIRECT/scripts/check_optimizer_isolation.sh $AW_ISOLATION (it must PASS)"
fi


say "4/4  cap-evolve run"
mkdir -p "$AW_EVAL/progress"
export PATH="$DIRECT/sandbox:$PATH"                       # the isolated `claude` wrapper comes first
export AW_ISOLATION
export AW_CLAUDE_SETTINGS="$SETTINGS"
export AW_NS_TRANSCRIPTS="$AW_EVAL/runs/optimizer_transcripts/$TS"
echo "  run: $BASE/run_$TS"
echo "  log: $OUT_LOG"

exec "${AW_VENV:-$AW_EVAL/.venv}/bin/cap-evolve" run \
  --spec "$P/$SPEC" --project "$P" --run-ts "$TS" \
  --dashboard off --follow "$@" \
  >> "$OUT_LOG" 2>&1
