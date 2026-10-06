#!/usr/bin/env bash
# STAGE 3 of the parsec v2 tier's local pipeline.
#
# Start 10 kaegis processes (one per v2 task), each seeded from that task's own seed.json,
# each on its own REST port. Then rewrite each task's task.toml so ${BACKEND_MCP_URL} points
# at that task's kaegis. This per-task isolation is the main thing that distinguishes v2 from
# v1, where all 30 tasks share four sim endpoints.
#
# Idempotent by refusing to start over a live manifest — call stop-sims-v2.sh first.
#
# RUNTIME STATE LIVES OUTSIDE THE COMMITTED TREE. The manifest, the sim logs and the per-task
# skills-store shadows all land under $PARSEC_V2_WORK (default <repo>/e2e/parsec/v2, which is
# gitignored), NOT under ci/benchmarks/parsec/. The intake-time version of this script derived
# its root from its own location, which after promotion into ci/benchmarks/parsec/utils/ would
# have written runtime scratch into a committed source tree.
#
# Overrides (env vars):
#   HARNESS_SRC                  — a github.ibm.com/kaegis/simulation-harness checkout
#                                  (REQUIRED; no default — IBM-internal, see
#                                  utils/bake-aap2-skill.sh). Needs `uv` on PATH.
#   PARSEC_HARBOR_TASKS_V2_STAGE — the stage-1 shadow whose task.toml files get the concrete
#                                  MCP URLs written into them
#                                  (default: <repo>/e2e/parsec/v2/harbor-tasks-v2)
#   PARSEC_V2_WORK               — runtime scratch root (default: <repo>/e2e/parsec/v2)
#   KAEGIS_PORT_BASE             — first REST port (default 9086; 10 tasks -> 9086..9095)
#   KAEGIS_HOST                  — bind address (default 127.0.0.1). Stage 4 rewrites this to
#                                  host.containers.internal in the task.toml URLs so the
#                                  Podman task container can reach these host-bound sockets.
#
# Requires: jq, curl, lsof, uv.
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd -P)
REPO=$(cd "$HERE/../../../.." && pwd -P)
V2WORK=${PARSEC_V2_WORK:-$REPO/e2e/parsec/v2}
MANIFEST="$V2WORK/sims-v2.manifest.json"
LOGS="$V2WORK/logs/sims-v2"
BAKED="$V2WORK/harness-src/skills-store/aap2"
SHADOWS_ROOT="$V2WORK/harness-src/skills-stores"
HARBOR_TASKS=${PARSEC_HARBOR_TASKS_V2_STAGE:-$REPO/e2e/parsec/v2/harbor-tasks-v2}
HARNESS_SRC=${HARNESS_SRC:?set HARNESS_SRC to your github.ibm.com/kaegis/simulation-harness checkout}
PORT_BASE=${KAEGIS_PORT_BASE:-9086}
HOST=${KAEGIS_HOST:-127.0.0.1}

if [ -f "$MANIFEST" ]; then
  echo "manifest exists: $MANIFEST — run stop-sims-v2.sh first" >&2
  exit 1
fi

[ -d "$HARNESS_SRC" ] || { echo "missing simulation-harness at $HARNESS_SRC (override with HARNESS_SRC)" >&2; exit 1; }
[ -d "$BAKED" ] || { echo "missing baked skill at $BAKED — run bake-aap2-skill.sh first" >&2; exit 1; }
[ -d "$HARBOR_TASKS" ] || { echo "missing patched tasks at $HARBOR_TASKS — run patch-harbor-tasks-v2.sh first" >&2; exit 1; }

mkdir -p "$LOGS" "$SHADOWS_ROOT"

TASKS=()
for t in "$HARBOR_TASKS"/bench-aap2-*/; do
  [ -d "$t" ] || continue
  TASKS+=("$(basename "$t")")
done
if [ "${#TASKS[@]}" -eq 0 ]; then
  echo "no tasks found under $HARBOR_TASKS" >&2; exit 1
fi

# Build manifest incrementally so a mid-loop failure still stops cleanly.
tmp=$(mktemp)
echo '{"started_at":"'"$(date -u +%FT%TZ)"'","kaegis_host":"'"$HOST"'","tasks":[]}' > "$tmp"

# Cleanup on partial start. Kills every `uv run` wrapper spawned so far (which
# takes their python listener children with them) plus, defensively, any
# listener pids already recorded in $tmp. Disarmed on the successful mv below.
WRAPPER_PIDS=()
cleanup_failed_start() {
  local rc=$?
  if [ "${#WRAPPER_PIDS[@]}" -gt 0 ]; then
    echo "start-sims-v2.sh: cleanup — killing ${#WRAPPER_PIDS[@]} wrapper pid(s): ${WRAPPER_PIDS[*]}" >&2
    kill "${WRAPPER_PIDS[@]}" 2>/dev/null || true
  fi
  local listener_pids
  listener_pids=$(jq -r '.tasks[].pid' "$tmp" 2>/dev/null || true)
  if [ -n "$listener_pids" ]; then
    echo "start-sims-v2.sh: cleanup — killing listener pid(s): $listener_pids" >&2
    echo "$listener_pids" | xargs kill 2>/dev/null || true
  fi
  rm -f "$tmp"
  return $rc
}
trap cleanup_failed_start ERR EXIT

port=$PORT_BASE
idx=1
for task_id in "${TASKS[@]}"; do
  padded=$(printf "%03d" "$idx")
  task_dir="$HARBOR_TASKS/$task_id"
  seed="$task_dir/seed.json"
  [ -f "$seed" ] || { echo "$task_id: missing seed.json" >&2; exit 1; }

  # 1. Per-task skills-store: copy baked, then swap db.json for the task's seed.
  shadow="$SHADOWS_ROOT/task-$padded/aap2"
  rm -rf "$SHADOWS_ROOT/task-$padded"
  mkdir -p "$shadow"
  cp "$BAKED"/{SKILL.md,api.json,schema.json} "$shadow/"
  cp "$seed" "$shadow/db.json"

  # 2. Per-task harness config — points skills.folder at the per-task shadow.
  cfg="$SHADOWS_ROOT/task-$padded/harness.yaml"
  cat > "$cfg" <<YAML
llm:
  provider: openai
  skill_generation_model: azure/gpt-5.4
  simulation_model: azure/gpt-5.4
  temperature: 0
skills:
  folder: $SHADOWS_ROOT/task-$padded
sessions:
  max_messages: 100
  idle_timeout_seconds: 3600
  max_concurrent_queue_depth: 8
  agent_recursion_limit: 50
creation:
  max_duration_seconds: 120
mcp:
  transport: sse
server:
  host: $HOST
  port: $port
logging:
  level: INFO
  destination_folder: $LOGS
startup:
  autostart_enabled: true
  autostart_simulation: aap2
YAML

  # 3. Launch kaegis in background.
  # NOTE: `python -m simulation_harness` does not parse CLI args; it reads
  # HARNESS_CONFIG_PATH (see simulation_harness/__main__.py). We set that env
  # var so kaegis loads our per-task config instead of its default
  # config/harness.yaml (which would autostart from the wrong skills-store).
  log="$LOGS/task-$padded.log"
  (
    cd "$HARNESS_SRC"
    HARNESS_CONFIG_PATH="$cfg" \
    HARNESS_SERVER_PORT=$port \
    HARNESS_AUTOSTART_ENABLED=true \
    HARNESS_AUTOSTART_SIMULATION=aap2 \
    exec uv run python -m simulation_harness --config "$cfg" >"$log" 2>&1
  ) &
  pid=$!
  WRAPPER_PIDS+=("$pid")

  # 4. Wait for /readyz + status=ready (up to 90s).
  base="http://$HOST:$port"
  ready=0
  for _ in $(seq 1 90); do
    if curl -fsS "$base/readyz" >/dev/null 2>&1; then
      status=$(curl -fsS "$base/api/v1/simulation" 2>/dev/null | jq -r '.status // "none"')
      if [ "$status" = "ready" ]; then ready=1; break; fi
    fi
    sleep 1
  done
  if [ "$ready" -ne 1 ]; then
    echo "$task_id: kaegis on port $port never became ready — see $log" >&2
    # No explicit kill here — the ERR/EXIT trap tears down all tracked
    # wrappers (including this one, which is already in WRAPPER_PIDS) and any
    # listener pids recorded in $tmp for previously-succeeded tasks.
    exit 1
  fi

  mcp_url=$(curl -fsS "$base/api/v1/simulation" | jq -r '.mcp_url')

  # Resolve the actual port-owning python listener pid (child of the `uv run`
  # wrapper captured as $pid). We record THIS in the manifest — a stop script
  # can then kill the listener without leaving a wrapper orphan on SIGKILL,
  # and uv run also exits naturally when its child dies on plain SIGTERM.
  listener_pid=$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | head -1)
  if [ -z "$listener_pid" ]; then
    echo "$task_id: could not resolve listener pid for port $port" >&2
    exit 1
  fi

  # 5. Rewrite ${BACKEND_MCP_URL} in that task's task.toml.
  sed -i.bak "s|\${BACKEND_MCP_URL}|$mcp_url|g" "$task_dir/task.toml"
  rm -f "$task_dir/task.toml.bak"

  # 6. Append to manifest — pid field holds the listener pid, not the wrapper.
  jq --arg id "$task_id" --argjson port "$port" \
     --arg rest "$base" --arg mcp "$mcp_url" \
     --argjson pid "$listener_pid" --arg sf "$SHADOWS_ROOT/task-$padded" \
     --arg log "$log" \
     '.tasks += [{task_id:$id, rest_port:$port, rest_url:$rest, mcp_url:$mcp, pid:$pid, skills_folder:$sf, log:$log}]' \
     "$tmp" > "$tmp.new" && mv "$tmp.new" "$tmp"

  echo "  $task_id  port=$port  mcp=$mcp_url  wrapper_pid=$pid  listener_pid=$listener_pid"
  port=$((port + 1))
  idx=$((idx + 1))
done

mv "$tmp" "$MANIFEST"
# Success — disarm the cleanup trap so it doesn't kill our live sims on EXIT.
trap - ERR EXIT
echo
echo "started ${#TASKS[@]} kaegis processes; manifest: $MANIFEST"
echo "Next: utils/patch-harbor-tasks-v2.1.sh, then TIER=v2 bash ci/benchmarks/lib/run_suite.sh parsec"
