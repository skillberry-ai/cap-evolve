#!/usr/bin/env bash
# Regenerate harbor-tasks-v2.1/ as a downstream patch of harbor-tasks-v2/.
#
# This is NOT a fresh copy from /Users/boazc/workarea/Python/rhdp-parsec/tasks_v2/;
# it starts from the already-patched v2 shadow (which has task.toml URLs pointing
# at the live per-task kaegis sims on 127.0.0.1:9086..9095) and applies three edits:
#
#   Bug A fix — MCP server name: "backend" -> "aap2"  (10 x task.toml)
#     Claude Code namespaces MCP tools as `mcp__<serverName>__<toolName>`.
#     With name = "backend", SKILL.md's bare `query_aap2` resolved to
#     `mcp__backend__query_aap2`, which the agent then invoked as bare
#     `query_aap2` -> "No such tool available". v1's convention is
#     name = "aap2" -> `mcp__aap2__query_aap2`.
#
#   Bug B fix — verify.py strip: add STRIP_MCP_PREFIX_PATCHED block  (10 x verify.py)
#     scorer compares against bare `query_aap2` in expected.json; without the
#     strip the namespaced tool_use names never match and tool_calls = 0.0
#     regardless of correct calls.
#
#   Bug C fix — MCP URL host: 127.0.0.1 -> host.containers.internal (10 x task.toml)
#     Sims bind to TCP 127.0.0.1:9086..9095 on the HOST. Inside a Podman task
#     container, 127.0.0.1 is the container's own loopback (not the host's), so
#     the MCP SSE handshake to http://127.0.0.1:908X/mcp/sse fails and the agent
#     runs without any mcp__aap2__* tools exposed. Podman's host-bridge alias
#     `host.containers.internal` reaches the host's 127.0.0.1 sockets via
#     slirp/gvproxy port forwarding, matching v1's convention.
#
# Idempotent — rebuilds v2.1 from v2 on every invocation.
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd -P)
V2=$(cd "$HERE/.." && pwd -P)
SRC="$V2/harbor-tasks-v2"
DST="$V2/harbor-tasks-v2.1"

[ -d "$SRC" ] || { echo "missing v2 shadow: $SRC" >&2; exit 1; }

rm -rf "$DST"
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
# The v2 shadow already resolved ${BACKEND_MCP_URL} to a literal
# http://127.0.0.1:908X/mcp/sse per task. There is exactly one such line per
# task.toml (the mcp_servers block URL); rewrite it to host.containers.internal
# so the alias resolves to the host loopback from inside the Podman task
# container.
for task in "$DST"/bench-aap2-*/; do
  toml="$task/task.toml"
  [ -f "$toml" ] || { echo "missing task.toml under $task" >&2; exit 1; }
  sed -i.bak 's|url = "http://127\.0\.0\.1:|url = "http://host.containers.internal:|g' "$toml"
  rm -f "$toml.bak"
done

echo "Regenerated $(ls "$DST" | wc -l | tr -d ' ') tasks in $DST"
