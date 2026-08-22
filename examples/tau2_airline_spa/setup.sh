#!/usr/bin/env bash
# Onboard tau2-bench airline (SPA variant) as a NEW benchmark and prepare it
# for optimization.
#
# This sets up the full SPA stack: Skillberry Store + Skillberry Proxy-Agent +
# tau2 Environment Manager, imports the frozen primitive tools as standalone
# store tools, imports the single `airline_skill`, and verifies the adapter.
#
#   bash examples/tau2_airline_spa/setup.sh
#
set -uo pipefail

EX_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$EX_DIR/../.." && pwd)"
VENV="$REPO/.venv"
PY="$VENV/bin/python"
PIP_INDEX="${PIP_INDEX:-https://pypi.org/simple}"

# Vendor directories for services
VENDOR="$REPO/vendor"
STORE_DIR="${SKILLBERRY_STORE_DIR:-$VENDOR/skillberry-store}"
AGENT_DIR="${SKILLBERRY_AGENT_DIR:-$VENDOR/skillberry-agent}"
BENCHMARKS_DIR="${SKILLBERRY_BENCHMARKS_DIR:-$VENDOR/skillberry-benchmarks}"
TAU2_DIR="$BENCHMARKS_DIR/tau2/tau2-bench"

# Ports
STORE_PORT="${SKILLBERRY_STORE_PORT:-8000}"
ENV_MGR_PORT="${TAU2_ENV_MANAGER_PORT:-8004}"
SPA_PORT="7000"
SPA_CONFIG_PORT="7001"

# Pinned versions (reproducibility)
STORE_TAG="${SKILLBERRY_STORE_TAG:-0.2.1}"
BENCHMARKS_COMMIT="${SKILLBERRY_BENCHMARKS_COMMIT:-a3a83266008275e9d800fd709927fa3dc4f23ec5}"
AGENT_COMMIT="${SKILLBERRY_AGENT_COMMIT:-e359494f18267e339f9561acbd7a930e3b51189e}"

# SPA configuration defaults (can be overridden by .env or exported vars)
SPA_PROVIDER_NAME="${SPA_PROVIDER_NAME:-litellm}"
SPA_MODEL_NAME="${SPA_MODEL_NAME:-openai/aws/gpt-oss-120b}"

say(){ printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }
die(){ printf '\n\033[1;31mSETUP FAILED: %s\033[0m\n' "$*" >&2; exit 1; }
command -v uv >/dev/null 2>&1 || die "uv is required but not found — install from https://docs.astral.sh/uv/"

# Load repo-root .env into shell (no overwrite of already-exported vars)
if [ -f "$REPO/.env" ]; then
  while IFS= read -r _line || [ -n "$_line" ]; do
    _line="${_line#"${_line%%[![:space:]]*}"}"   # ltrim whitespace
    # skip blank lines and comments
    [[ -z "$_line" || "$_line" == \#* || "$_line" != *=* ]] && continue
    _key="${_line%%=*}"
    _val="${_line#*=}"
    # strip surrounding quotes
    _val="${_val%\"}" ; _val="${_val#\"}"
    _val="${_val%\'}" ; _val="${_val#\'}"
    [ -z "${!_key+x}" ] && export "$_key=$_val"
  done < "$REPO/.env"
fi

wait_for_port(){
  local port="$1" name="$2" max="${3:-20}"
  for i in $(seq 1 "$max"); do
    if curl -sf "http://localhost:$port/health" >/dev/null 2>&1 ||
       curl -sf "http://localhost:$port/docs" >/dev/null 2>&1 ||
       curl -sf "http://localhost:$port/" >/dev/null 2>&1; then
      echo "  ✓ $name responsive on port $port"
      return 0
    fi
    echo "  waiting for $name... (attempt $i/$max)"
    sleep 5
  done
  die "$name failed to start on port $port"
}

port_is_listening(){
  local port="$1"
  lsof -Pi :"$port" -sTCP:LISTEN -t >/dev/null 2>&1 && return 0
  # Fallback when lsof is unavailable: any HTTP answer means the port is bound.
  curl -s -o /dev/null -m 2 "http://127.0.0.1:$port/docs" && return 0
  return 1
}

# Wait for a background service to bind its port. Unlike wait_for_port this also
# watches the PID, so a process that dies during startup fails immediately with
# its log instead of stalling for the whole timeout.
wait_for_listen(){
  local port="$1" name="$2" pid="$3" log="$4" max="${5:-30}"
  for i in $(seq 1 "$max"); do
    if port_is_listening "$port"; then
      echo "  ✓ $name listening on port $port"
      return 0
    fi
    if [ -n "$pid" ] && ! kill -0 "$pid" 2>/dev/null; then
      echo "  $name process exited during startup. Log:"
      tail -40 "$log" 2>/dev/null || true
      die "$name died before binding port $port"
    fi
    echo "  waiting for $name to bind port $port... (attempt $i/$max)"
    sleep 2
  done
  echo "  $name log:"
  tail -40 "$log" 2>/dev/null || true
  die "$name failed to bind port $port after $((max * 2))s"
}

# ---------------------------------------------------------------------------
say "1/7  Install cap-evolve (Python venv + core CLI)"
[ -x "$PY" ] || python3 -m venv "$VENV" || die "could not create venv"
"$PY" -m pip install -q --index-url "$PIP_INDEX" --upgrade pip
"$PY" -m pip install -q --index-url "$PIP_INDEX" -e "$REPO/core" || die "pip install ./core failed"
"$VENV/bin/cap-evolve" version || die "cap-evolve CLI not available"
echo "  ✓ cap-evolve installed"

# ---------------------------------------------------------------------------
say "1.5/7  Check required credentials"
_require_env() {
  local var="$1" desc="$2"
  if [ -z "${!var:-}" ]; then
    die "$var is not set — $desc. Set it in $REPO/.env or export it."
  fi
}
# Skillberry Proxy-Agent (SPA) — these always have defaults set above, just echo them
echo "  SPA_PROVIDER_NAME=$SPA_PROVIDER_NAME"
echo "  SPA_MODEL_NAME=$SPA_MODEL_NAME"
# tau2-bench / upstream LLM
_require_env OPENAI_API_KEY  "needed for the upstream LLM API key"

# OPENAI_API_BASE and OPENAI_BASE_URL are two names litellm accepts for ONE value:
# litellm reads OPENAI_API_BASE, while spa_env._upstream_llm_args() reads
# OPENAI_BASE_URL for the user simulator. Requiring the operator to set the same URL
# twice is a trap, so accept either and derive the other.
if [ -n "${OPENAI_API_BASE:-}" ] && [ -z "${OPENAI_BASE_URL:-}" ]; then
  export OPENAI_BASE_URL="$OPENAI_API_BASE"
  echo "  derived OPENAI_BASE_URL from OPENAI_API_BASE"
elif [ -n "${OPENAI_BASE_URL:-}" ] && [ -z "${OPENAI_API_BASE:-}" ]; then
  export OPENAI_API_BASE="$OPENAI_BASE_URL"
  echo "  derived OPENAI_API_BASE from OPENAI_BASE_URL"
elif [ -z "${OPENAI_API_BASE:-}" ] && [ -z "${OPENAI_BASE_URL:-}" ]; then
  die "set OPENAI_API_BASE or OPENAI_BASE_URL to the upstream LLM endpoint URL. Set it in $REPO/.env or export it."
elif [ "$OPENAI_API_BASE" != "$OPENAI_BASE_URL" ]; then
  # Both set but disagreeing is almost certainly a mistake, and which one wins
  # depends on which component makes the call — refuse rather than pick.
  die "OPENAI_API_BASE ($OPENAI_API_BASE) and OPENAI_BASE_URL ($OPENAI_BASE_URL) differ. They are two names for the same endpoint — set them to the same URL, or set only one."
fi
echo "  ✓ all required credentials present"

# SPA's ports are fixed, so an occupied port is a hard stop — check it now rather
# than 6 steps later when the health check times out with no explanation.
_spa_is_pid(){ ps -p "$1" -o args= 2>/dev/null | grep -q -- "-m main"; }
for _p in "$SPA_PORT" "$SPA_CONFIG_PORT"; do
  for _pid in $(lsof -ti :"$_p" -sTCP:LISTEN 2>/dev/null || true); do
    if ! _spa_is_pid "$_pid"; then
      printf '  port %s is held by PID %s: %s\n' \
        "$_p" "$_pid" "$(ps -p "$_pid" -o args= 2>/dev/null | head -1)" >&2
      die "SPA needs ports $SPA_PORT and $SPA_CONFIG_PORT, and its port is fixed at $SPA_PORT (tau2 and SPA hardcode it). Free the port and re-run. On macOS this is usually ControlCenter — turn off System Settings > General > AirDrop & Handoff > AirPlay Receiver."
    fi
  done
done
echo "  ✓ SPA ports $SPA_PORT/$SPA_CONFIG_PORT are free (or already SPA)"

# ---------------------------------------------------------------------------
say "2/7  Clone + install tau2-bench (from skillberry-benchmarks @ $BENCHMARKS_COMMIT)"
if [ ! -d "$BENCHMARKS_DIR/.git" ]; then
  echo "  cloning skillberry-benchmarks -> $BENCHMARKS_DIR"
  git clone https://github.com/skillberry-ai/skillberry-benchmarks.git "$BENCHMARKS_DIR" \
    || die "git clone skillberry-benchmarks failed"
  git -C "$BENCHMARKS_DIR" checkout "$BENCHMARKS_COMMIT" \
    || die "git checkout $BENCHMARKS_COMMIT failed"
fi
if [ ! -d "$TAU2_DIR" ]; then
  die "tau2-bench directory not found at $TAU2_DIR"
fi
"$PY" -m pip install -q --index-url "$PIP_INDEX" -e "$TAU2_DIR[skillberry]" || die "pip install tau2-bench failed"
TAU2_SHA="$(git -C "$BENCHMARKS_DIR" rev-parse HEAD)"
"$PY" -c "import tau2" >/dev/null 2>&1 || die "tau2 import failed"
echo "  ✓ tau2-bench installed @ $TAU2_SHA (from skillberry-benchmarks)"

# ---------------------------------------------------------------------------
say "3/7  Clone + start Skillberry Store (tag $STORE_TAG, port $STORE_PORT)"
mkdir -p "$VENDOR"
if [ ! -d "$STORE_DIR/.git" ]; then
  echo "  cloning skillberry-store @ $STORE_TAG -> $STORE_DIR"
  git clone --branch "$STORE_TAG" --depth 1 \
    https://github.com/skillberry-ai/skillberry-store.git "$STORE_DIR" \
    || die "git clone skillberry-store failed"
fi
cd "$STORE_DIR"
if [ ! -d ".venv" ]; then
  uv venv -p 3.11 .venv || die "could not create Python 3.11 venv for store (is uv installed?)"
  uv pip install pip --python .venv/bin/python
fi
. .venv/bin/activate
if [ ! -f ".stamps/install-requirements-" ] 2>/dev/null; then
  make install-requirements || pip install -e . || die "store install failed"
fi
deactivate
# Start store if not already running
if ! curl -sf "http://localhost:$STORE_PORT/health" >/dev/null 2>&1; then
  # Remove stale sentinel that blocks startup when no process is actually running
  rm -f /tmp/skillberry-store-service.pid
  echo "  starting store..."
  nohup bash -c "cd $STORE_DIR && . .venv/bin/activate && EXECUTE_PYTHON_LOCALLY=True make run" > store.log 2>&1 &
  sleep 5
fi
cd "$REPO"
wait_for_port "$STORE_PORT" "skillberry-store" 60

# ---------------------------------------------------------------------------
say "4/7  Start tau2 Environment Manager (port $ENV_MGR_PORT)"
if port_is_listening "$ENV_MGR_PORT"; then
  echo "  ✓ env manager already running on port $ENV_MGR_PORT"
else
  echo "  starting env manager..."
  # tau2 is installed in cap-evolve's venv; start the EnvironmentManager inline.
  # Startup is slow (~10s): importing tau2 pulls in litellm, which tries to fetch
  # its remote model-cost map and can stall until that request times out, then the
  # domain/agent registry is built. Poll for the port rather than sleeping a fixed
  # interval. LITELLM_LOCAL_MODEL_COST_MAP skips the doomed remote fetch entirely.
  LITELLM_LOCAL_MODEL_COST_MAP=True nohup "$PY" -c "
import asyncio
from tau2.orchestrator.environment_manager import EnvironmentManager

async def runner():
    manager = EnvironmentManager(host='127.0.0.1', port=$ENV_MGR_PORT)
    await manager.run()

asyncio.run(runner())
" > "$REPO/env_manager.log" 2>&1 &
  ENV_MGR_PID=$!
  wait_for_listen "$ENV_MGR_PORT" "env manager" "$ENV_MGR_PID" "$REPO/env_manager.log" 45
fi

# ---------------------------------------------------------------------------
say "5/7  Purge store + import primitive tools, then the single airline_skill"
# Purge
curl -s -X DELETE "http://localhost:$STORE_PORT/admin/purge-all" >/dev/null 2>&1 || true
echo "  store purged"

# --- 5a. Primitive tools: constant, standalone, tagged `primitive-tool` -------
# Mirrors the `import-primitive-tools` target in skillberry-benchmarks/tau2/Makefile.
# These are NOT a skill. They are never modified by the optimizer.
PRIM_TOOLS="$EX_DIR/seed_capability/primitive_tools/functions.py"
[ -f "$PRIM_TOOLS" ] || die "primitive tools file not found: $PRIM_TOOLS"

# Extract PUBLIC function names only — this is what excludes `_make_api_call`,
# which stays an internal helper of the primitives and never becomes a tool.
FUNC_NAMES=$("$PY" "$EX_DIR/scripts/extract_functions.py" "$PRIM_TOOLS") \
  || die "failed to parse primitive tools"
[ -n "$FUNC_NAMES" ] || die "no public functions found in $PRIM_TOOLS"

TOOL_COUNT=0
FAILED_COUNT=0
for func_name in $FUNC_NAMES; do
  RESPONSE=$(curl -s -X POST \
    "http://localhost:$STORE_PORT/tools/add?selected_func=$func_name&update=true" \
    -F "tool=@$PRIM_TOOLS" 2>&1)
  if echo "$RESPONSE" | grep -q '"uuid"'; then
    TOOL_COUNT=$((TOOL_COUNT + 1))
    # Tag it `primitive-tool`: GET -> set tags -> PUT
    TOOL_DATA=$(curl -s -X GET "http://localhost:$STORE_PORT/tools/$func_name" 2>&1)
    if echo "$TOOL_DATA" | grep -q '"name"'; then
      UPDATED=$(printf '%s' "$TOOL_DATA" | "$PY" -c \
        "import sys,json; d=json.load(sys.stdin); d['tags']=['primitive-tool']; print(json.dumps(d))" 2>/dev/null)
      if [ -n "$UPDATED" ]; then
        printf '%s' "$UPDATED" | curl -s -X PUT \
          "http://localhost:$STORE_PORT/tools/$func_name" \
          -H "Content-Type: application/json" -d @- >/dev/null 2>&1 \
          || echo "  ⚠ could not tag $func_name"
      fi
    fi
  else
    echo "  ⚠ failed to import $func_name"
    FAILED_COUNT=$((FAILED_COUNT + 1))
  fi
done
echo "  ✓ imported $TOOL_COUNT primitive tools (tagged primitive-tool)"
[ "$TOOL_COUNT" -gt 0 ] || die "no primitive tools imported"
[ "$FAILED_COUNT" -eq 0 ] || die "$FAILED_COUNT primitive tool(s) failed to import"

# --- 5b. The single skill: airline_skill -------------------------------------
# Imported AFTER the primitives so the store can auto-detect each wrapper's
# dependency on the primitive it calls by bare name.
SKILL_DIR="$EX_DIR/seed_capability/airline_skill"
[ -f "$SKILL_DIR/SKILL.md" ] || die "airline_skill/SKILL.md not found at $SKILL_DIR"
echo "  importing airline_skill..."
# Delete first so a re-run replaces rather than collides (404 on a clean store is fine).
curl -s -X DELETE \
  "http://localhost:$STORE_PORT/skills/airline_skill?delete_tools=true&delete_snippets=true" \
  >/dev/null 2>&1 || true
SKILL_RESP=$(curl -s -X POST "http://localhost:$STORE_PORT/skills/import-anthropic" \
  -F "source_type=folder" \
  -F "folder_path=$(cd "$SKILL_DIR" && pwd)" \
  -F "snippet_mode=file" 2>&1)
if echo "$SKILL_RESP" | grep -qE '"success"|"skill_name"'; then
  echo "  ✓ airline_skill imported to store"
else
  echo "  ⚠ airline_skill import response: $SKILL_RESP"
  die "failed to import airline_skill"
fi

# Verify: exactly one skill, and its wrappers each depend on a primitive.
WRAPPER_COUNT=$(curl -s "http://localhost:$STORE_PORT/skills/airline_skill?fields=full" 2>/dev/null \
  | "$PY" -c "import sys,json; print(len(json.load(sys.stdin).get('tools') or []))" 2>/dev/null || echo 0)
echo "  ✓ airline_skill exposes $WRAPPER_COUNT tools"
[ "$WRAPPER_COUNT" -gt 0 ] || die "airline_skill imported but exposes no tools"

# ---------------------------------------------------------------------------
say "6/7  Clone + start Skillberry Proxy-Agent (@ $AGENT_COMMIT, port $SPA_PORT)"
if [ ! -d "$AGENT_DIR/.git" ]; then
  echo "  cloning skillberry-agent -> $AGENT_DIR"
  git clone https://github.com/skillberry-ai/skillberry-agent.git "$AGENT_DIR" \
    || die "git clone skillberry-agent failed"
  git -C "$AGENT_DIR" checkout "$AGENT_COMMIT" \
    || die "git checkout $AGENT_COMMIT failed"
fi
cd "$AGENT_DIR"
if [ ! -d ".venv" ]; then
  uv venv -p 3.11 .venv || die "could not create Python 3.11 venv for agent (is uv installed?)"
  uv pip install pip --python .venv/bin/python
fi
. .venv/bin/activate
if [ ! -f ".stamps/install-requirements-" ] 2>/dev/null; then
  make install-requirements || pip install -e . || die "agent install failed"
fi
deactivate
# Start SPA if not already running
if ! curl -sf "http://localhost:$SPA_PORT/health" >/dev/null 2>&1; then
  echo "  starting SPA with SKILL_NAME=airline_skill..."
  export SKILL_NAME=airline_skill
  export USE_AGENT_TOOLS=false
  export USE_AGENT_PROMPTS=true
  export MCP_PROMPTS_POSITION=postfix
  export SPA_PROVIDER_NAME="$SPA_PROVIDER_NAME"
  export SPA_MODEL_NAME="$SPA_MODEL_NAME"
  # Ensure LLM credentials are available for SPA's provider
  if [ -z "${OPENAI_API_KEY:-}" ]; then
    die "OPENAI_API_KEY must be set (SPA's litellm provider needs it)"
  fi
  nohup bash -c "cd $AGENT_DIR && . .venv/bin/activate && make run" > proxy-agent.log 2>&1 &
  sleep 5
fi
cd "$REPO"
wait_for_port "$SPA_PORT" "skillberry-proxy-agent"

# ---------------------------------------------------------------------------
say "7/7  Scaffold cap-evolve project + wire adapter + check"
# Scaffold
"$PY" "$REPO/skills/phases/intake/scripts/run.py" --base "$REPO/.capevolve" --workdir "$REPO" --force >/dev/null 2>&1 \
  || true
PROJECT="$REPO/.capevolve/project"
mkdir -p "$PROJECT/adapters" "$PROJECT/optimizer"

# Wire
cp "$EX_DIR/adapters/adapter.py" "$EX_DIR/adapters/spa_env.py" "$PROJECT/adapters/"
# The optimizer instructions MUST live in the project: cap-evolve resolves
# optimizer_instructions_file relative to the CWD first and only then relative to
# the project, so a repo-relative path silently falls back to the generic
# scaffolded template whenever the run is started from anywhere but the repo root
# — taking the MODIFY-only constraint and the store-import rules with it.
cp "$EX_DIR/optimizer/INSTRUCTIONS.md" "$PROJECT/optimizer/"
rm -rf "$PROJECT/seed_capability"
cp -R "$EX_DIR/seed_capability" "$PROJECT/seed_capability"
rm -rf "$PROJECT/scripts"
cp -R "$EX_DIR/scripts" "$PROJECT/scripts"
cp "$EX_DIR/capevolve.yaml" "$EX_DIR/split_ids.json" "$PROJECT/"

# Breadcrumb: record which example scaffolded this project dir last.
# .capevolve/project is shared by skillsbench, tau2_airline AND this example, so a
# mixed directory is easy to end up with and confusing to diagnose. Nothing reads
# this file — teardown.sh deliberately never touches .capevolve — it exists purely
# so a human can tell whose files these are.
printf 'tau2_airline_spa\n' > "$PROJECT/.owned-by"

# Export service dirs for the adapter
export SKILLBERRY_AGENT_DIR="$AGENT_DIR"
export SKILLBERRY_STORE_DIR="$STORE_DIR"

echo "  project scaffolded at $PROJECT"

PYTHONPATH="$PROJECT/adapters" "$VENV/bin/cap-evolve" check "$PROJECT" || die "cap-evolve check did not pass"

printf '\n\033[1;32mREADY.\033[0m  Next:\n'
printf '  SPA_PROVIDER_NAME=%s \\\n' "$SPA_PROVIDER_NAME"
printf '  SPA_MODEL_NAME=%s \\\n' "$SPA_MODEL_NAME"
printf '  SKILLBERRY_AGENT_DIR=%s \\\n' "$AGENT_DIR"
printf '  SKILLBERRY_STORE_DIR=%s \\\n' "$STORE_DIR"
printf '  cap-evolve run --spec %s/capevolve.yaml\n' "$PROJECT"
