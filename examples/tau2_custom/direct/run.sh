#!/usr/bin/env bash
# cap-evolve run on tau2-bench airline, DIRECT arm: the runner reads the candidate's tool
# code in its own process — no proxy, no store, no environment service.
# Prereq: bash examples/tau2_custom/direct/setup.sh
#
#   bash run.sh                 # the pinned spec (capevolve.yaml)
#   bash run.sh --smoke         # the cheap smoke spec over the same install
#   SPEC=capevolve.itest.yaml bash run.sh     # any spec already copied into the project
#
# Unlike the blackbox arm's run.sh there is NO stack to start and nothing left running
# afterwards: this arm's only external dependency is the gateway the LLM calls go to.
set -uo pipefail
EX_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$EX_DIR/../../.." && pwd)"
BASE="${BASE:-$REPO/.capevolve}"
PROJECT="${PROJECT:-$BASE/project}"
VENV="${VENV:-$REPO/.venv}"
case "$VENV" in /*) ;; *) VENV="$REPO/$VENV" ;; esac
PY="$VENV/bin/python"
say(){ printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }
die(){ printf '\n\033[1;31mRUN FAILED: %s\033[0m\n' "$*" >&2; exit 1; }

SPEC="${SPEC:-capevolve.yaml}"
# The run dir is run_<tag>. TIMESTAMP it: a FIXED tag is a path cap-evolve has already
# written, and RunDir treats an existing run_<tag> with a state.json as a RESUME — so a
# second `bash run.sh` continued the previous run (its best_id, budget and spend) instead
# of starting a fresh one. Remember whether the caller pinned a tag, otherwise the default
# below is already set by the time --smoke is parsed and the smoke would land in it.
RUN_TS_EXPLICIT="${RUN_TS:+1}"
RUN_TS="${RUN_TS:-$(date +%Y%m%d_%H%M%S)}"
for arg in "$@"; do
  case "$arg" in
    --smoke) SPEC="capevolve.smoke.yaml"
             [ -z "$RUN_TS_EXPLICIT" ] && RUN_TS="smoke_$(date +%Y%m%d_%H%M%S)" ;;
    -h|--help) echo "usage: run.sh [--smoke]   (or SPEC=<file> RUN_TS=<tag> bash run.sh)"; exit 0 ;;
    *) echo "unknown option: $arg  (use --smoke)" >&2; exit 2 ;;
  esac
done
[ -f "$PROJECT/$SPEC" ] || die "$PROJECT/$SPEC not found — run setup.sh first"
[ -x "$PY" ] || die "no venv at $VENV — run setup.sh first"

export PYTHONPATH="$PROJECT/adapters"
export CAPEVOLVE_SKILLS_DIR="$REPO/skills"
# HIGH on purpose: nothing funnels through a single process on this arm, so the ceiling is
# the gateway's, not ours. The blackbox arm runs at 4 for exactly the opposite reason.
export TAU2_MAX_CONCURRENCY="${TAU2_MAX_CONCURRENCY:-125}"
export TAU2_LLM_TIMEOUT="${TAU2_LLM_TIMEOUT:-240}"
export TAU2_LLM_RETRIES="${TAU2_LLM_RETRIES:-2}"
export TAU2_INFRA_RETRIES="${TAU2_INFRA_RETRIES:-2}"
# BOTH the agent under test and the user simulator go straight to the gateway. There is no
# SPA sentinel on this arm — gateway.py would refuse it for the simulator anyway.
export TAU2_AGENT_MODEL="${TAU2_AGENT_MODEL:-aws/gpt-oss-120b}"
export TAU2_USER_MODEL="${TAU2_USER_MODEL:-aws/gpt-oss-120b}"

say "1/1  cap-evolve run  (spec: $SPEC)"
echo "  benchmark: $(git -C "$REPO/vendor/skillberry-benchmarks" rev-parse --short HEAD 2>/dev/null || echo '?')"
echo "  agent: $TAU2_AGENT_MODEL | user sim: $TAU2_USER_MODEL | concurrency $TAU2_MAX_CONCURRENCY"
echo "------ pre-run cost preview (spends nothing) ------"
"$VENV/bin/cap-evolve" estimate --spec "$PROJECT/$SPEC" --project "$PROJECT" || true
echo "------ cap-evolve run ------"
"$VENV/bin/cap-evolve" run \
  --spec "$PROJECT/$SPEC" --project "$PROJECT" \
  --run-ts "$RUN_TS" --dashboard "${CAPEVOLVE_DASHBOARD:-auto}"
exit $?
