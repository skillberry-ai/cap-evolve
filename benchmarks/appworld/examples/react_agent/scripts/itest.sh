#!/usr/bin/env bash
# AppWorld regression test on ONE task (82e2fac_1). A real end-to-end optimization run used as an
# on-demand regression check for this example, like benchmarks/tau2/examples/airline/itest.sh. Cheap: 1 task,
# 1 trial, 1 iteration (baseline, one optimizer pass, gate, sealed final, report).
#
#   - agent      : gpt-oss-120b, RITS by default (AW_MODEL_NAME / AW_MODEL_URL / AW_KEY_* override,
#                  see adapters/aw_agent.py). Key from AW_SECRETS_FILE (default <repo>/.env).
#   - optimizer  : claude-code @ OPT_MODEL (default aws/claude-sonnet-5-5), through sandbox/claude
#                  with AW_ISOLATION (default sandbox). It authenticates on its own.
#   - data       : $AW_EVAL as built by README Setup (venv-aw, root_opt, lint cache, reference).
#
#   bash scripts/itest.sh             # the real run; exit code is the test result (0 = pass)
#   bash scripts/itest.sh --dry-run   # everything up to the first model call: preflight, project,
#                                     # cap-evolve check, isolation gate, cost estimate
set -euo pipefail
EX="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="$(cd "$EX/../../../.." && pwd)"
AW_EVAL="${AW_EVAL:-/tmp/aw_eval}"
PY="$AW_EVAL/venv-aw/bin/python"
CAPE="$AW_EVAL/venv-aw/bin/cap-evolve"
RUN_NAME="${AW_ITEST_NAME:-itest}"
RUN_DIR="$AW_EVAL/runs/$RUN_NAME"
P="$RUN_DIR/.capevolve/project"
OPT_MODEL="${OPT_MODEL:-aws/claude-sonnet-5-5}"
AW_ISOLATION="${AW_ISOLATION:-sandbox}"
SECRETS="${AW_SECRETS_FILE:-$REPO/.env}"
DRY=0
case "${1:-}" in --dry-run) DRY=1 ;; "") ;; *) echo "usage: itest.sh [--dry-run]" >&2; exit 2 ;; esac
say(){ printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }
die(){ printf '\n\033[1;31mITEST FAILED: %s\033[0m\n' "$*" >&2; exit 1; }

say "1/4  Preflight (README Setup)"
[ -x "$PY" ] || die "no $PY: build venv-aw (README Setup step 1)"
"$PY" -c "import appworld, appworld_agents, cap_evolve" 2>/dev/null || die "venv-aw lacks appworld / appworld_agents / cap_evolve"
for f in root_opt/data/tasks/82e2fac_1/specs.json lint_cache.json reference/api_index.md; do
  [ -e "$AW_EVAL/$f" ] || die "missing $AW_EVAL/$f (README Setup step 2)"
done
if [ "$DRY" = 0 ]; then
  KEY="${AW_KEY_ENV:-RITS_API_KEY}"
  grep -q "^$KEY=" "$SECRETS" 2>/dev/null || die "no $KEY= line in $SECRETS (the agent model's key; README Setup step 3)"
fi
command -v claude >/dev/null || die "claude CLI not on PATH (the optimizer)"

say "2/4  Wire the project (same as setup_project.sh) + the one-task spec + hard gate"
rm -rf "$RUN_DIR"
AW_SECRETS_FILE="$SECRETS" OPT_MODEL="$OPT_MODEL" bash "$EX/scripts/setup_project.sh" "$RUN_DIR" >/dev/null \
  || die "setup_project.sh (cap-evolve check) did not pass"
cp "$EX/itest_split.json" "$P/"
sed -e "s|@OPT_MODEL@|$OPT_MODEL|" -e "s|@INSTRUCTIONS@|$P/optimizer/INSTRUCTIONS.md|" -e "s|@AW_EVAL@|$AW_EVAL|g" \
  "$EX/capevolve.itest.yaml" > "$P/capevolve.itest.yaml"
(cd "$P" && PYTHONPATH="$P/adapters" CAPEVOLVE_SKILLS_DIR="$REPO/skills" "$CAPE" check "$P" >/dev/null) \
  || die "cap-evolve check did not pass on the itest project"

say "3/4  Isolation gate ($AW_ISOLATION)"
case "$AW_ISOLATION" in sandbox) S="$P/sandbox/optimizer-sandbox.json" ;; namespace) S="$P/sandbox/optimizer-permissions.json" ;;
  *) die "AW_ISOLATION must be sandbox or namespace" ;; esac
# The settings were just rendered, so a check from before this script cannot count for them:
# run a fresh one, as launch_cape_hc.sh requires (it costs one short optimizer call).
if ! "$PY" "$EX/scripts/isolation_gate.py" "$AW_EVAL" "$AW_ISOLATION" "$S" 2>/dev/null; then
  if [ "$DRY" = 1 ]; then
    echo "  (dry run: no isolation check run; the real run runs check_optimizer_isolation.sh $AW_ISOLATION)"
  else
    AW_SECRETS_FILE="$SECRETS" OPT_MODEL="$OPT_MODEL" bash "$EX/scripts/check_optimizer_isolation.sh" "$AW_ISOLATION" >/dev/null \
      || die "check_optimizer_isolation.sh $AW_ISOLATION did not PASS"
    touch -d '1 minute ago' "$P/sandbox/"*.json
    "$PY" "$EX/scripts/isolation_gate.py" "$AW_EVAL" "$AW_ISOLATION" "$S" || die "isolation gate still closed"
  fi
fi

say "4/4  Run the optimization (82e2fac_1 · 1 trial · 1 iter) + assert regression"
export AW_EVAL AW_ISOLATION AW_SECRETS_FILE="$SECRETS" AW_RUN_TS="$RUN_NAME"
if [ "$DRY" = 1 ]; then
  (cd "$P" && PYTHONPATH="$P/adapters" CAPEVOLVE_SKILLS_DIR="$REPO/skills" \
     "$CAPE" run --spec "$P/capevolve.itest.yaml" --project "$P" --dry-run) || die "cap-evolve run --dry-run failed"
  printf '\n\033[1;32mITEST DRY RUN PASSED (no model was called).\033[0m\n'
  exit 0
fi
# launch_cape_hc.sh is the real launch path: PATH shim, isolation gate, env, secrets handling.
AW_SPEC=capevolve.itest.yaml bash "$EX/scripts/launch_cape_hc.sh" "$RUN_DIR" || die "cap-evolve run failed (see $AW_EVAL/progress/$RUN_NAME.out)"
"$PY" "$EX/scripts/assert_itest.py" "$RUN_DIR/.capevolve/run_$RUN_NAME" || die "regression assertions failed"
printf '\n\033[1;32mITEST PASSED.\033[0m\n'
