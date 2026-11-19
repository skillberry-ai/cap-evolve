#!/usr/bin/env bash
# Set up the AppWorld BLACKBOX approach: one cap-evolve project whose only capability is the system
# prompt, kept as a Skillberry Store skill (my_skill/SKILL.md) that the Skillberry Proxy-Agent injects
# into every LLM call of AppWorld's stock ReAct agent.
#
# It builds on the direct approach (..): AppWorld itself, its data roots, the lint cache, the
# reference docs and the optimizer isolation are set up once there (../README.md, Setup steps 1-2)
# and reused here. This script only adds what blackbox needs on top:
#
#   bash benchmarks/appworld/examples/react_agent/blackbox/scripts/setup_project.sh
#   AW_SPEC=capevolve.smoke.yaml bash benchmarks/appworld/examples/react_agent/blackbox/scripts/launch.sh
#
# Both default to BASE=$AW_EVAL/.capevolve-blackbox:
# the project in BASE/project, and one run folder BASE/run_<YYYYMMDD_HHMMSS> per launch beside it.
# BASE must be under $AW_EVAL: the optimizer's isolation only binds a working dir inside it.
#
# The seed SKILL.md is generated from AppWorld's own prompt and never committed (AppWorld's
# README_BEFORE_SHARING). The store and proxy are the shared clones in the repo's vendor/; nothing
# here deletes or re-clones them.
set -euo pipefail

EX="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"       # this approach (blackbox/)
DIRECT="$(cd "$EX/.." && pwd)"                              # the direct approach: its harness is reused
REPO="$(cd "$EX/../../../../.." && pwd)"
# Everything AppWorld lives in $AW_EVAL, outside the repo, so the optimizer's isolation can hide it.
AW_EVAL="${AW_EVAL:-/tmp/aw_eval}"
BASE="${1:-$AW_EVAL/.capevolve-blackbox}"                   # the project + all its runs
PROJECT="$BASE/project"
PY="${AW_VENV:-$AW_EVAL/.venv}/bin/python"
LINT_CACHE="$AW_EVAL/lint_cache.json"
REFERENCE="$AW_EVAL/reference"
CLIENT_PROMPT="$AW_EVAL/appworld/experiments/prompts/react_code_agent/instructions.txt"
APP_DESCRIPTIONS="$AW_EVAL/app_descriptions.json"

OPT_MODEL="${OPT_MODEL:-aws/claude-sonnet-5-5}"
SECRETS="${AW_SECRETS_FILE:-$REPO/.env}"
INSTR="$PROJECT/optimizer/INSTRUCTIONS.md"
export CAPEVOLVE_SKILLS_DIR="$REPO/skills"

say(){ printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }
die(){ printf '\n\033[1;31mSETUP FAILED: %s\033[0m\n' "$*" >&2; exit 1; }
# render TEMPLATE OUT: fill this run's paths and settings into a committed template
render(){
  sed -e "s|@REPO@|$REPO|g" -e "s|@AW_EVAL@|$AW_EVAL|g" -e "s|@AW_SECRETS_FILE@|$SECRETS|g" \
      -e "s|@OPT_MODEL@|$OPT_MODEL|g" -e "s|@INSTRUCTIONS@|$INSTR|g" \
      -e "s|{AW_REFERENCE}|$REFERENCE|g" -e "s|{AW_LINT_CACHE}|$LINT_CACHE|g" -e "s|{AW_PY}|$PY|g" \
      -e "s|{AW_BB_LINTS}|$PROJECT/adapters/bb_lints.py|g" -e "s|{AW_APP_DESCRIPTIONS}|$APP_DESCRIPTIONS|g" \
      "$1" > "$2"
}

say "1/5  Preconditions: the direct approach's AppWorld setup"
[ -x "$PY" ]                     || die "missing $PY (../README.md, Setup step 1)"
[ -f "$CLIENT_PROMPT" ]          || die "missing AppWorld's stock prompt $CLIENT_PROMPT (../README.md, Setup step 1)"
[ -f "$LINT_CACHE" ]             || die "missing $LINT_CACHE: run ../scripts/make_roots.py"
[ -f "$REFERENCE/api_index.md" ] || die "missing $REFERENCE: run ../scripts/make_reference.py"
echo "  AppWorld, lint cache and reference docs found in $AW_EVAL"

say "2/5  Scaffold the project"
"$PY" "$REPO/skills/phases/intake/scripts/run.py" --base "$BASE" --workdir "$EX" --force >/dev/null \
  || die "intake scaffold failed"
mkdir -p "$PROJECT/adapters" "$PROJECT/optimizer" "$PROJECT/reference" "$PROJECT/sandbox"
# This approach's adapter, episode worker, proxy tailoring and SKILL.md lints ...
cp "$EX/adapters/adapter.py" "$EX/adapters/aw_bb_agent.py" \
   "$EX/adapters/appworld_tailoring.py" "$EX/adapters/bb_lints.py" "$PROJECT/adapters/"
# ... plus the direct approach's episode harness and leak checks, which they reuse unchanged.
cp "$DIRECT/adapters/aw_agent.py" "$DIRECT/adapters/lints.py" "$PROJECT/adapters/"
cp "$REFERENCE/api_index.md" "$REFERENCE/react_agent_notes.md" "$PROJECT/reference/"
cp "$EX/smoke_split.json" "$PROJECT/"
# train = val = AppWorld's official train + dev; test stays empty (the final window scores test_normal).
"$PY" "$DIRECT/scripts/make_splits.py" "$PROJECT/split_ids.json" >/dev/null || die "make_splits.py failed"
echo "  project at $PROJECT"

say "3/5  Seed SKILL.md: AppWorld's stock prompt up to the real task turn"
rm -rf "$PROJECT/seed_capability"
"$PY" "$EX/scripts/make_seed_skill.py" "$CLIENT_PROMPT" "$PROJECT/seed_capability/my_skill" "$APP_DESCRIPTIONS" \
  | sed 's/^/  /' || die "make_seed_skill.py failed"

say "4/5  Render the optimizer instructions, the run specs and the isolation settings"
render "$EX/optimizer/INSTRUCTIONS.template.md" "$INSTR"
render "$EX/capevolve.yaml"       "$PROJECT/capevolve.yaml"
render "$EX/capevolve.smoke.yaml" "$PROJECT/capevolve.smoke.yaml"
render "$EX/PROJECT.template.md"  "$PROJECT/PROJECT.md"
# The optimizer runs isolated exactly as in the direct approach (../README.md, Isolation).
render "$DIRECT/sandbox/optimizer-permissions.template.json" "$PROJECT/sandbox/optimizer-permissions.json"
render "$DIRECT/sandbox/optimizer-sandbox.template.json"     "$PROJECT/sandbox/optimizer-sandbox.json"
echo "  optimizer model $OPT_MODEL; instructions at $INSTR"

say "5/5  Store + proxy at the pinned commits (vendor/), then the hard gate (cap-evolve check)"
"$PY" "$EX/scripts/provision_stack.py" || die "store/proxy not at the pinned commits (see the message above)"
( cd "$PROJECT" && PYTHONPATH="$PROJECT/adapters" APPWORLD_ROOT="$AW_EVAL/root_opt" \
    "${AW_VENV:-$AW_EVAL/.venv}/bin/cap-evolve" check "$PROJECT" ) || die "cap-evolve check did not pass"
echo "  cap-evolve check passed"

printf '\n\033[1;32mREADY.\033[0m  Next (each run lands in %s/run_<YYYYMMDD_HHMMSS>):\n  AW_SPEC=capevolve.smoke.yaml bash %s/scripts/launch.sh %s   # 1 task, 1 trial, 1 iteration\n  bash %s/scripts/launch.sh %s                                # the full run\n' \
  "$BASE" "$EX" "$BASE" "$EX" "$BASE"
