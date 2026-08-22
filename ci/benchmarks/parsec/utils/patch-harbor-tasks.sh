#!/bin/bash
# Shadow-copy Parsec's harbor-tasks/ with the edits needed for our pilot:
#
#   task.toml edits:
#     1. Swap the docker_image to localhost/parsec-agent-base:latest.
#     2. Rewrite the mcp_servers block: TWO endpoints — the aap2 kaegis sim on
#        :8086 (was ${BACKEND_MCP_URL} placeholder), and the github kaegis sim on
#        :8087 (added — parsec-github/api.json served by a second kaegis instance).
#        Harbor's docker environment does not interpolate ${VAR} placeholders in
#        task.toml, so we substitute concrete URLs here.
#
#   tests/verify.py edits:
#     3. Strip the MCP name-prefix (mcp__<server>__<tool> → <tool>) inside
#        parse_transcript, so trajectory-match compares against the bare tool
#        names in expected.json. Parsec's real runtime uses direct Python
#        function calls (bare names); Harbor's claude-code uses MCP-prefixed
#        names. Without this fix, trajectory-match is 0 for every task.
#
#   filesystem edits:
#     4. Ensure an environment/ subdirectory exists (Harbor's TaskModel.is_valid_dir
#        requires it even for tasks that declare environment inline in task.toml).
#
# The original harbor-tasks/ from RH is left UNTOUCHED. Our shadow lives under
# .capevolve/project/harbor-tasks-patched/ and HARBOR_DATASET should be pointed
# at it (see PROJECT.md env checklist).
#
# Overrides (env vars):
#   PARSEC_HARBOR_TASKS_SRC — RH's original harbor-tasks/ (default: rhdp-parsec/harbor-tasks)
#   PARSEC_HARBOR_TASKS_DST — shadow destination (default: .capevolve/project/harbor-tasks-patched)
#   BACKEND_MCP_URL_VALUE   — aap2 sim URL   (default: http://host.containers.internal:8086/mcp/sse)
#   GITHUB_MCP_URL_VALUE    — github sim URL (default: http://host.containers.internal:8087/mcp/sse)
#
# Rerun. Idempotent — safe to rerun any time. Deletes and recreates the shadow.
#
# Docs: .capevolve/project/docs/container-build.md

set -euo pipefail

SRC=${PARSEC_HARBOR_TASKS_SRC:-/Users/boazc/workarea/Python/rhdp-parsec/harbor-tasks}
DST=${PARSEC_HARBOR_TASKS_DST:-$(cd "$(dirname "$0")/.." && pwd)/harbor-tasks-patched}
FILTER=${1:-aap2}   # subdomain to include; default aap2 for the pilot
BACKEND_MCP_URL_VALUE=${BACKEND_MCP_URL_VALUE:-http://host.containers.internal:8086/mcp/sse}
GITHUB_MCP_URL_VALUE=${GITHUB_MCP_URL_VALUE:-http://host.containers.internal:8087/mcp/sse}
BABYLON_MCP_URL_VALUE=${BABYLON_MCP_URL_VALUE:-http://host.containers.internal:8088/mcp/sse}
PROVISIONS_DB_MCP_URL_VALUE=${PROVISIONS_DB_MCP_URL_VALUE:-http://host.containers.internal:8090/mcp/sse}

if [ ! -d "$SRC" ]; then
    echo "Source harbor-tasks/ not found at $SRC" >&2
    echo "Override via PARSEC_HARBOR_TASKS_SRC=/path/to/harbor-tasks" >&2
    exit 1
fi

echo "→ source:         $SRC"
echo "→ shadow:         $DST"
echo "→ filter:         traces_parsec-${FILTER}-*"
echo "→ aap2 sim:       $BACKEND_MCP_URL_VALUE"
echo "→ github sim:     $GITHUB_MCP_URL_VALUE"
echo "→ babylon sim:    $BABYLON_MCP_URL_VALUE"
echo "→ provisions sim: $PROVISIONS_DB_MCP_URL_VALUE"

rm -rf "$DST"
mkdir -p "$DST"

count=0
for t in "$SRC"/traces_parsec-"$FILTER"-*; do
    [ -d "$t" ] || continue
    name=$(basename "$t")
    cp -r "$t" "$DST/$name"

    # -- task.toml: docker_image + REPLACE single mcp_servers block with FOUR endpoints --
    python3 - "$DST/$name/task.toml" "$BACKEND_MCP_URL_VALUE" "$GITHUB_MCP_URL_VALUE" "$BABYLON_MCP_URL_VALUE" "$PROVISIONS_DB_MCP_URL_VALUE" <<'PY'
import sys
path = sys.argv[1]
aap2_url, github_url, babylon_url, provisions_url = sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]
text = open(path).read()

# 1. Swap docker_image
text = text.replace(
    'docker_image = "registry.access.redhat.com/ubi9/ubi:latest"',
    'docker_image = "localhost/parsec-agent-base:latest"',
)

# 2. Replace the single [[environment.mcp_servers]] block that has
#    name = "backend" + url = "${BACKEND_MCP_URL}" with FOUR blocks:
#    aap2 (was the placeholder) + github + babylon + provisions_db.
#    All four cover the aap2 sub-agent's tool set (query_aap2 +
#    fetch_github_file/search_github_repo/etc + lookup_catalog_item/
#    query_babylon_catalog + query_provisions_db/db_describe_table).
import re
pattern = re.compile(
    r'\[\[environment\.mcp_servers\]\]\s*\n'
    r'\s*name\s*=\s*"backend"\s*\n'
    r'\s*url\s*=\s*"\$\{BACKEND_MCP_URL\}"\s*\n?',
    re.MULTILINE,
)
replacement = (
    '[[environment.mcp_servers]]\n'
    f'name = "aap2"\n'
    f'url = "{aap2_url}"\n'
    '\n'
    '[[environment.mcp_servers]]\n'
    f'name = "github"\n'
    f'url = "{github_url}"\n'
    '\n'
    '[[environment.mcp_servers]]\n'
    f'name = "babylon"\n'
    f'url = "{babylon_url}"\n'
    '\n'
    '[[environment.mcp_servers]]\n'
    f'name = "provisions_db"\n'
    f'url = "{provisions_url}"\n'
)
new_text, n = pattern.subn(replacement, text)
if n != 1:
    print(f"WARN: mcp_servers block not rewritten in {path} (matched {n} times); check task.toml shape", file=sys.stderr)
    sys.exit(2)
open(path, "w").write(new_text)
PY

    # -- tests/verify.py: strip MCP prefix in parse_transcript --
    python3 - "$DST/$name/tests/verify.py" <<'PY'
import sys, re
path = sys.argv[1]
text = open(path).read()

# Inject a prefix-stripping call right after the `tool_use` block extracts the name.
# Idempotent: if already patched, do nothing.
if "STRIP_MCP_PREFIX_PATCHED" in text:
    sys.exit(0)

pattern = re.compile(
    r'(if isinstance\(block, dict\) and block\.get\("type"\) == "tool_use":\s*\n'
    r'\s+tool_names\.append\(block\.get\("name", ""\)\))'
)
replacement = (
    'if isinstance(block, dict) and block.get("type") == "tool_use":  # STRIP_MCP_PREFIX_PATCHED\n'
    '                    _n = block.get("name", "")\n'
    '                    if _n.startswith("mcp__"):\n'
    '                        _parts = _n.split("__", 2)\n'
    '                        if len(_parts) == 3:\n'
    '                            _n = _parts[2]\n'
    '                    tool_names.append(_n)'
)
new_text, n = pattern.subn(replacement, text)
if n != 1:
    print(f"WARN: verify.py tool_use pattern not found in {path} (matched {n} times)", file=sys.stderr)
    sys.exit(2)
open(path, "w").write(new_text)
PY

    # -- ensure environment/ subdir exists for Harbor's is_valid_dir check --
    mkdir -p "$DST/$name/environment"
    touch "$DST/$name/environment/.keep"

    count=$((count + 1))
done

echo ""
echo "Patched $count tasks."
echo ""
echo "Next: set HARBOR_DATASET=$DST in your shell (see PROJECT.md env checklist)."
