#!/usr/bin/env bash
# STAGE 4 of the parsec v2 tier's local pipeline — and the tier's actual HARBOR_DATASET.
#
# Regenerate <repo>/e2e/parsec/v2/harbor-tasks-v2.1/ as a downstream patch of
# harbor-tasks-v2/. This is NOT a fresh copy from the authored tasks_v2/ tree; it starts
# from the stage-1 shadow AFTER stage 3 (start-sims-v2.sh) has baked each task's live
# kaegis URL (127.0.0.1:9086..9095) into its task.toml, and applies three edits — each one
# a bug found only by actually running the tier inside a Harbor/Podman container:
#
#   Bug A fix — MCP server name: "backend" -> "aap2"  (10 x task.toml)
#     Claude Code namespaces MCP tools as `mcp__<serverName>__<toolName>`.
#     With name = "backend", SKILL.md's bare `query_aap2` resolved to
#     `mcp__backend__query_aap2`, which the agent then invoked as bare
#     `query_aap2` -> "No such tool available". v1's convention is
#     name = "aap2" -> `mcp__aap2__query_aap2`.
#
#   Bug B fix — verify.py strip: add STRIP_MCP_PREFIX_PATCHED block  (10 x verify.py)
#     The scorer compares against bare `query_aap2` in expected.json; without the
#     strip the namespaced tool_use names never match and tool_calls = 0.0
#     regardless of correct calls. (Same class of fix as v1's patcher applies.)
#
#   Bug C fix — MCP URL host: 127.0.0.1 -> host.containers.internal (10 x task.toml)
#     Sims bind to TCP 127.0.0.1:9086..9095 on the HOST. Inside a Podman task
#     container, 127.0.0.1 is the container's own loopback (not the host's), so
#     the MCP SSE handshake to http://127.0.0.1:908X/mcp/sse fails and the agent
#     runs without any mcp__aap2__* tools exposed. Podman's host-bridge alias
#     `host.containers.internal` reaches the host's 127.0.0.1 sockets via
#     slirp/gvproxy port forwarding, matching v1's convention.
#
# DST below is byte-identical to run_suite.sh's `parsec)` HARBOR_DATASET default for
# TIER=v2 — if you change one, change both.
#
# Overrides (env vars):
#   PARSEC_HARBOR_TASKS_V2_STAGE — stage-1 shadow to read
#                                  (default: <repo>/e2e/parsec/v2/harbor-tasks-v2)
#   PARSEC_HARBOR_TASKS_V2_DST   — this tier's dataset
#                                  (default: <repo>/e2e/parsec/v2/harbor-tasks-v2.1)
#
# Idempotent — rebuilds v2.1 from v2 on every invocation.
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd -P)
REPO=$(cd "$HERE/../../../.." && pwd -P)
SRC=${PARSEC_HARBOR_TASKS_V2_STAGE:-$REPO/e2e/parsec/v2/harbor-tasks-v2}
DST=${PARSEC_HARBOR_TASKS_V2_DST:-$REPO/e2e/parsec/v2/harbor-tasks-v2.1}

[ -d "$SRC" ] || { echo "missing v2 shadow: $SRC — run utils/patch-harbor-tasks-v2.sh first" >&2; exit 1; }

rm -rf "$DST"
mkdir -p "$(dirname "$DST")"
cp -R "$SRC" "$DST"

# --- Bug A: rename MCP server on each task.toml ---
for task in "$DST"/bench-aap2-*/; do
  toml="$task/task.toml"
  [ -f "$toml" ] || { echo "missing task.toml under $task" >&2; exit 1; }
  # Only match `name = "backend"` under [[environment.mcp_servers]] — the other
  # `name = ...` line is the task name which must not change. sed with a fixed
  # literal match to `name = "backend"` is safe: the substring appears once per
  # file (the task name lines all read `name = "bench/..."`).
  sed -i.bak 's|^name = "backend"$|name = "aap2"|' "$toml"
  rm -f "$toml.bak"
done

# --- Bug B: port STRIP_MCP_PREFIX_PATCHED into each verify.py ---
# Uses a python transform (not sed) so a multi-line, whitespace-preserving
# replacement stays readable and doesn't depend on sed dialect (GNU vs BSD).
python3 - "$DST" <<'PY'
import sys
from pathlib import Path

DST = Path(sys.argv[1])

# Indentation matches the actual verify.py (16-space leading indent).
OLD = (
    '                if isinstance(block, dict) and block.get("type") == "tool_use":\n'
    '                    args = block.get("input")\n'
    '                    calls.append((\n'
    '                        block.get("name", ""),\n'
    '                        args if isinstance(args, dict) else {},\n'
    '                    ))'
)

NEW = (
    '                if isinstance(block, dict) and block.get("type") == "tool_use":\n'
    '                    args = block.get("input")\n'
    '                    _name = block.get("name", "")\n'
    '                    if _name.startswith("mcp__"):\n'
    '                        _parts = _name.split("__", 2)\n'
    '                        if len(_parts) == 3:\n'
    '                            _name = _parts[2]  # STRIP_MCP_PREFIX_PATCHED\n'
    '                    calls.append((\n'
    '                        _name,\n'
    '                        args if isinstance(args, dict) else {},\n'
    '                    ))'
)

count = 0
for verify in sorted(DST.glob("bench-aap2-*/tests/verify.py")):
    text = verify.read_text()
    if "STRIP_MCP_PREFIX_PATCHED" in text:
        count += 1
        continue
    if OLD not in text:
        raise SystemExit(f"patch target not found in {verify}")
    verify.write_text(text.replace(OLD, NEW))
    count += 1

print(f"patched verify.py in {count} tasks under {DST}")
PY

# --- Bug C: rewrite MCP URL host on each task.toml ---
# Stage 3 already resolved ${BACKEND_MCP_URL} to a literal
# http://127.0.0.1:908X/mcp/sse per task. There is exactly one such line per
# task.toml (the mcp_servers block URL); rewrite it to host.containers.internal
# so the alias resolves to the host loopback from inside the Podman task
# container.
for task in "$DST"/bench-aap2-*/; do
  toml="$task/task.toml"
  [ -f "$toml" ] || { echo "missing task.toml under $task" >&2; exit 1; }
  if grep -q '\${BACKEND_MCP_URL}' "$toml"; then
    echo "::error:: $toml still carries the \${BACKEND_MCP_URL} placeholder — run utils/start-sims-v2.sh (stage 3) before this script" >&2
    exit 1
  fi
  sed -i.bak 's|url = "http://127\.0\.0\.1:|url = "http://host.containers.internal:|g' "$toml"
  rm -f "$toml.bak"
done

count=$(find "$DST" -maxdepth 1 -type d -name 'bench-aap2-*' | wc -l | tr -d ' ')
echo "Regenerated $count tasks in $DST"
echo "Next: TIER=v2 bash ci/benchmarks/lib/run_suite.sh parsec"
