#!/usr/bin/env bash
# cap-evolve run on tau2-bench airline, SPA arm: the candidate becomes a Skillberry Store
# skill and the Proxy-Agent injects it into the agent's LLM calls.
# Prereq: bash examples/skillberry_benchmarks_tau2_airline/spa/setup.sh
#
#   bash run.sh                 # the pinned spec (capevolve.yaml)
#   bash run.sh --smoke         # the cheap smoke spec over the same stack
#   SPEC=capevolve.itest.yaml bash run.sh     # any spec already copied into the project
#
# STARTS the stack (it was provisioned by setup.sh) and leaves it running: SPA binds ONE
# skill at start, and restarting it mid-evaluation would swap the skill under a running
# rollout. Per-candidate deploys are the adapter's job, not this script's.
set -uo pipefail
EX_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$EX_DIR/../../.." && pwd)"
BASE="${BASE:-$REPO/.capevolve-spa}"
PROJECT="${PROJECT:-$BASE/project}"
VENV="${VENV:-$REPO/.venv}"
case "$VENV" in /*) ;; *) VENV="$REPO/$VENV" ;; esac
PY="$VENV/bin/python"
say(){ printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }
die(){ printf '\n\033[1;31mRUN FAILED: %s\033[0m\n' "$*" >&2; exit 1; }

SPEC="${SPEC:-capevolve.yaml}"
# Remember whether the caller pinned a tag: otherwise the default below would already be
# set by the time --smoke is parsed, and ${RUN_TS:-spa_smoke} would silently keep "spa" —
# writing the smoke into the full run's dir.
RUN_TS_EXPLICIT="${RUN_TS:+1}"
RUN_TS="${RUN_TS:-spa}"
for arg in "$@"; do
  case "$arg" in
    --smoke) SPEC="capevolve.smoke.yaml"; [ -z "$RUN_TS_EXPLICIT" ] && RUN_TS="spa_smoke" ;;
    -h|--help) echo "usage: run.sh [--smoke]   (or SPEC=<file> RUN_TS=<tag> bash run.sh)"; exit 0 ;;
    *) echo "unknown option: $arg  (use --smoke)" >&2; exit 2 ;;
  esac
done
[ -f "$PROJECT/$SPEC" ] || die "$PROJECT/$SPEC not found — run setup.sh first"
[ -x "$PY" ] || die "no venv at $VENV — run setup.sh first"

export PYTHONPATH="$PROJECT/adapters"
export CAPEVOLVE_SKILLS_DIR="$REPO/skills"
# LOW on purpose: every agent call funnels through ONE proxy and ONE store process, so the
# direct arm's 125 would just queue behind them and time out.
export TAU2_MAX_CONCURRENCY="${TAU2_MAX_CONCURRENCY:-4}"
export TAU2_LLM_TIMEOUT="${TAU2_LLM_TIMEOUT:-240}"
export TAU2_LLM_RETRIES="${TAU2_LLM_RETRIES:-2}"
export TAU2_INFRA_RETRIES="${TAU2_INFRA_RETRIES:-2}"
# The AGENT is the SPA sentinel — tau2 routes that exact string to the proxy. The USER
# SIMULATOR goes STRAIGHT to the gateway: proxying it would inject the capability into the
# very thing measuring the agent. gateway.py refuses the sentinel for the simulator.
export TAU2_AGENT_MODEL="${TAU2_AGENT_MODEL:-ibm/skillberry-local}"
export TAU2_USER_MODEL="${TAU2_USER_MODEL:-aws/gpt-oss-120b}"
export SPA_REMOTE_ENV_URL="${SPA_REMOTE_ENV_URL:-http://127.0.0.1:8004}"
ENV_PORT="${ENV_PORT:-8004}"

say "1/3  The benchmark's environment service (port $ENV_PORT)"
# tau2's Environment Manager fronts the airline env over HTTP; the store's executor calls
# it per rollout with an injected env_id. LITELLM_LOCAL_MODEL_COST_MAP=True skips litellm's
# doomed remote cost-map fetch, which otherwise stalls startup until timeout.
if curl -sf -o /dev/null --max-time 3 "http://127.0.0.1:$ENV_PORT/docs" \
   || curl -sf -o /dev/null --max-time 3 "http://127.0.0.1:$ENV_PORT/"; then
  echo "  already up"
else
  echo "  starting -> $REPO/env_manager.log"
  ( cd "$REPO" && LITELLM_LOCAL_MODEL_COST_MAP=True nohup "$PY" -c "
import asyncio
from tau2.orchestrator.environment_manager import EnvironmentManager
asyncio.run(EnvironmentManager(host='127.0.0.1', port=$ENV_PORT).run())
" > env_manager.log 2>&1 & )
  # POLL, never sleep a fixed amount: importing tau2 pulls in litellm, so first start is
  # ~10s, and a fixed sleep either wastes time or races the service.
  for _ in $(seq 1 60); do
    curl -sf -o /dev/null --max-time 2 "http://127.0.0.1:$ENV_PORT/docs" && break
    curl -sf -o /dev/null --max-time 2 "http://127.0.0.1:$ENV_PORT/" && break
    sleep 1
  done
  curl -sf -o /dev/null --max-time 3 "http://127.0.0.1:$ENV_PORT/docs" \
    || curl -sf -o /dev/null --max-time 3 "http://127.0.0.1:$ENV_PORT/" \
    || die "environment service did not come up on $ENV_PORT — see $REPO/env_manager.log"
  echo "  healthy"
fi

say "2/3  The Skillberry stack (Store, then Proxy-Agent)"
# ORDER MATTERS: the store must be healthy before SPA starts, and SPA binds ONE skill by
# name at start. Both starts are idempotent — a healthy service is reported, not restarted.
"$PY" - <<'PYEOF' || die "could not start the Skillberry stack"
import json, sys
sys.path.insert(0, "skills/interventions/llm-proxies/spa/scripts")
import spa_env
spa_env.start_store()
spa_env.start_spa("my_skill")
print("  " + json.dumps(spa_env.status()))
PYEOF

say "3/3  cap-evolve run  (spec: $SPEC)"
echo "  benchmark: $(git -C "$REPO/vendor/skillberry-benchmarks" rev-parse --short HEAD 2>/dev/null || echo '?')"
echo "  agent: $TAU2_AGENT_MODEL (via SPA) | user sim: $TAU2_USER_MODEL (direct to gateway) | concurrency $TAU2_MAX_CONCURRENCY"
echo "------ pre-run cost preview (spends nothing) ------"
"$VENV/bin/cap-evolve" estimate --spec "$PROJECT/$SPEC" --project "$PROJECT" || true
echo "------ cap-evolve run ------"
"$VENV/bin/cap-evolve" run \
  --spec "$PROJECT/$SPEC" --project "$PROJECT" \
  --run-ts "$RUN_TS" --dashboard "${CAPEVOLVE_DASHBOARD:-auto}"
rc=$?

# Left running on purpose (a later run reuses a healthy stack). To stop:
#   python -c "import sys; sys.path.insert(0,'skills/interventions/llm-proxies/spa/scripts'); import spa_env; spa_env.stop_all()"
printf '\nstack left running. stop it with:\n  %s -c "import sys; sys.path.insert(0,%s); import spa_env; spa_env.stop_all()"\n' \
  "$PY" "'skills/interventions/llm-proxies/spa/scripts'"
exit $rc
