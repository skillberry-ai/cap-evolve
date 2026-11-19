#!/usr/bin/env bash
# Run the AppWorld example. Prereq: setup.sh (with --blackbox for the blackbox approach).
#
#   bash run.sh --smoke                 # direct:   1 task, 1 trial, 1 iteration (scripts/itest.sh)
#   bash run.sh --fix10                 # direct:   the 10 fixed tasks, 5 trials, 3 iterations
#   bash run.sh                         # direct:   the full search (147 tasks, 6 iterations)
#   bash run.sh --blackbox --smoke      # blackbox: 1 task, 1 trial, 1 iteration
#   bash run.sh --blackbox --fix10      # blackbox: the same 10 fixed tasks as direct
#   bash run.sh --blackbox              # blackbox: the full search
#
# The 10 fixed tasks (fix10_split.json, drawn once from train + dev with seed 0) are the same in
# both approaches, so their runs compare directly. Each run lands in a new run_<YYYYMMDD_HHMMSS>
# under $AW_EVAL/.capevolve (direct) or $AW_EVAL/.capevolve-blackbox; the smoke under
# $AW_EVAL/.capevolve-itest/run_itest (direct).
#
# The model comes from AW_MODEL_NAME / AW_MODEL_URL / AW_KEY_HEADER / AW_KEY_ENV / AW_SECRETS_FILE
# (README: Setup step 3). The optimizer runs isolated (AW_ISOLATION): run
# scripts/check_optimizer_isolation.sh $AW_ISOLATION first; the launch refuses without a passing report.
set -uo pipefail

EX="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AW_EVAL="${AW_EVAL:-/tmp/aw_eval}"; export AW_EVAL

APPROACH=direct
MODE=full
for arg in "$@"; do
  case "$arg" in
    --blackbox) APPROACH=blackbox ;;
    --smoke)    MODE=smoke ;;
    --fix10)    MODE=fix10 ;;
    -h|--help)  sed -n '2,9p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $arg  (use --blackbox, --smoke, --fix10)" >&2; exit 2 ;;
  esac
done

say(){ printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }
die(){ printf '\n\033[1;31mRUN FAILED: %s\033[0m\n' "$*" >&2; exit 1; }

case "$APPROACH" in
  direct)   BASE="$AW_EVAL/.capevolve" ;;
  blackbox) BASE="$AW_EVAL/.capevolve-blackbox" ;;
esac
case "$MODE" in
  smoke) SPEC=capevolve.smoke.yaml ;;
  fix10) SPEC=capevolve.fix10.yaml ;;
  full)  SPEC=capevolve.yaml ;;
esac
[ -n "${AW_MODEL_NAME:-}" ] || echo "  WARNING: AW_MODEL_NAME not set: the agent falls back to adapters/aw_agent.py's default (RITS)"

say "$APPROACH · $MODE"
if [ "$APPROACH" = direct ] && [ "$MODE" = smoke ]; then
  # Direct's smoke is the example's own regression run: it builds its own project and asserts the result.
  exec bash "$EX/scripts/itest.sh"
fi
[ -f "$BASE/project/$SPEC" ] || die "no $BASE/project/$SPEC: run bash $EX/setup.sh$([ "$APPROACH" = blackbox ] && echo ' --blackbox') first"
echo "  spec $SPEC in $BASE/project"
if [ "$APPROACH" = blackbox ]; then
  AW_SPEC="$SPEC" exec bash "$EX/blackbox/scripts/launch.sh" "$BASE"
else
  AW_SPEC="$SPEC" exec bash "$EX/scripts/launch_cape_hc.sh" "$BASE"
fi
