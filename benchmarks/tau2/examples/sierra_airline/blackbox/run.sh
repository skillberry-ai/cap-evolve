#!/usr/bin/env bash
# cap-evolve run on vanilla tau2-bench airline, blackbox arm.
# HAND-WRITTEN REPLAY of the run steps ../PROMPT.md prescribes (#2b, #6). Prereq: setup.sh.
#
#   bash run.sh --smoke    # capevolve.smoke.yaml: task 9, 1 trial, mock optimizer
#   bash run.sh            # capevolve.yaml: tasks 8 10 20 23 35 42 44, 5 trials, claude-code
#
# Starts tau2's environment service and the Skillberry store, deploys the seed once, then runs.
# The run's preflight starts the proxy (it needs `skill_name`). Services are left running.
set -uo pipefail
EX_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$EX_DIR/../../.." && pwd)"

load_dotenv(){
  local f="$1" line key val
  [ -f "$f" ] || return 0
  while IFS= read -r line || [ -n "$line" ]; do
    line="${line#"${line%%[![:space:]]*}"}"
    case "$line" in ''|\#*) continue ;; *=*) ;; *) continue ;; esac
    key="${line%%=*}"; val="${line#*=}"
    key="${key%"${key##*[![:space:]]}"}"
    case "$key" in ''|*[!A-Za-z0-9_]*) continue ;; esac
    val="${val#"${val%%[![:space:]]*}"}"; val="${val%"${val##*[![:space:]]}"}"
    case "$val" in \"*\") val="${val#\"}"; val="${val%\"}" ;; \'*\') val="${val#\'}"; val="${val%\'}" ;; esac
    [ -n "${!key+x}" ] || export "$key=$val"     # shell > .env
  done < "$f"
}
load_dotenv "$REPO/.env"

VENV="${VENV:-$REPO/.venv}"
case "$VENV" in /*) ;; *) VENV="$REPO/$VENV" ;; esac
PY="$VENV/bin/python"
PROJECT="${BASE:-$REPO/.capevolve-blackbox}/project"   # same default as setup.sh
BB="$REPO/skills/interventions/llm-proxies/blackbox/scripts"
ENV_PORT=8004
# /tmp, like the Skillberry services' logs; rotated by the intervention skill's helper.
ENV_LOG=/tmp/env_manager.log
say(){ printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }
die(){ printf '\n\033[1;31mRUN FAILED: %s\033[0m\n' "$*" >&2; exit 1; }

SPEC="capevolve.yaml"
for arg in "$@"; do
  case "$arg" in
    --smoke) SPEC="capevolve.smoke.yaml" ;;
    -h|--help) echo "usage: run.sh [--smoke]"; exit 0 ;;
    *) echo "unknown option: $arg  (use --smoke)" >&2; exit 2 ;;
  esac
done
[ -f "$PROJECT/$SPEC" ] || die "$PROJECT/$SPEC not found — run setup.sh first"
[ -x "$PY" ] || die "no venv at $VENV — run setup.sh first"

export CAPEVOLVE_SKILLS_DIR="$REPO/skills"
export LITELLM_LOCAL_MODEL_COST_MAP=True
export SPA_REMOTE_ENV_URL="${SPA_REMOTE_ENV_URL:-http://127.0.0.1:$ENV_PORT}"
# TAU2_AGENT_MODEL is the one source of the agent model; the adapter falls back to
# SPA_MODEL_NAME, then to aws/gpt-oss-120b. The user simulator has NO such fallback chain.
[ -n "${TAU2_AGENT_MODEL:-}${SPA_MODEL_NAME:-}" ] || echo "  WARNING: neither TAU2_AGENT_MODEL nor SPA_MODEL_NAME set — agent falls back to aws/gpt-oss-120b"
[ -n "${TAU2_USER_MODEL:-}" ] || echo "  WARNING: TAU2_USER_MODEL not set — the user simulator falls back to aws/gpt-oss-120b"

say "1/3  tau2's environment service (port $ENV_PORT)"
if curl -sf --max-time 3 "http://127.0.0.1:$ENV_PORT/status" >/dev/null; then
  echo "  already up"
else
  # Rotate ONLY when the service is down: rotating a log a running service holds open leaves it
  # appending to a deleted inode.
  "$PY" -c "import sys; sys.path.insert(0, '$BB'); import blackbox_env; blackbox_env.rotate_if_large('$ENV_LOG')" \
    || echo "  WARNING: could not rotate $ENV_LOG (continuing)" >&2
  ( cd "$REPO" && nohup "$PY" -c "import asyncio; from tau2.orchestrator.environment_manager import EnvironmentManager; asyncio.run(EnvironmentManager(host='127.0.0.1', port=$ENV_PORT).run())" > "$ENV_LOG" 2>&1 & )
  for _ in $(seq 1 60); do curl -sf --max-time 2 "http://127.0.0.1:$ENV_PORT/status" >/dev/null && break; sleep 1; done
  curl -sf --max-time 3 "http://127.0.0.1:$ENV_PORT/status" >/dev/null || die "env service did not come up — see $ENV_LOG"
  echo "  healthy (log: $ENV_LOG)"
fi

say "2/3  Skillberry store + one seed deploy (the proxy needs a skill to bind at preflight)"
"$PY" - <<PYEOF || die "store start / seed deploy failed"
import sys
sys.path.insert(0, "$BB")
import blackbox_env as bb
bb.start_store()
protect = bb.Protection(tags=("tau2_airline_primitives",))
seed = "$PROJECT/seed_capability"
if len(protect.present_names()) < 14:
    bb.import_standalone_tools(seed + "/primitive_tools/functions.py", tags=("tau2_airline_primitives",))
bb.reset_store_to_skill(seed + "/my_skill", "my_skill", protect)
n = len(protect.present_names())
print(f"  primitives in store: {n}")
sys.exit(0 if n == 14 else 1)
PYEOF

say "3/3  cap-evolve run  (spec: $SPEC)"
echo "  tau2: $(cat "$REPO/vendor/tau2-bench.COMMIT" 2>/dev/null || echo '?')"
# --project is passed explicitly: its default is cwd-relative, and cap-evolve refuses a --spec
# that lies outside --project.
( cd "$REPO" && "$VENV/bin/cap-evolve" run --spec "$PROJECT/$SPEC" --project "$PROJECT" \
    --dashboard "${CAPEVOLVE_DASHBOARD:-auto}" )
rc=$?

printf '\nservices left running. stop them with:\n  %s -c "import sys; sys.path.insert(0,%s); import blackbox_env; blackbox_env.stop_all()"\n  pkill -f tau2.orchestrator.environment_manager\n' \
  "$PY" "'$BB'"
exit $rc
