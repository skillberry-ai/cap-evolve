#!/usr/bin/env bash
# cap-evolve run on vanilla tau2-bench airline, direct arm (no services: the runner loads the
# candidate's tools/tools.py in its own process).
# HAND-WRITTEN REPLAY of the run steps ../PROMPT.md prescribes (#6). Prereq: setup.sh.
#
#   bash run.sh --smoke    # capevolve.smoke.yaml: task 9, 1 trial, mock optimizer
#   bash run.sh            # capevolve.yaml: tasks 8 10 20 23 35 42 44, 5 trials, claude-code
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
PROJECT="${BASE:-$REPO/.capevolve}/project"
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
# The direct adapter reads TAU2_AGENT_MODEL / TAU2_USER_MODEL and falls back to
# aws/gpt-oss-120b, which a gateway may not serve.
for v in TAU2_AGENT_MODEL TAU2_USER_MODEL; do
  [ -n "${!v:-}" ] || echo "  WARNING: $v not set — it falls back to aws/gpt-oss-120b"
done

echo "  tau2: $(cat "$REPO/vendor/tau2-bench.COMMIT" 2>/dev/null || echo '?')   spec: $SPEC"
# --project is passed explicitly: its default is cwd-relative, and cap-evolve refuses a --spec
# that lies outside --project.
cd "$REPO" && exec "$VENV/bin/cap-evolve" run --spec "$PROJECT/$SPEC" --project "$PROJECT" \
  --dashboard "${CAPEVOLVE_DASHBOARD:-auto}"
