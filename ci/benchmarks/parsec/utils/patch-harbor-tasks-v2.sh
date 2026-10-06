#!/usr/bin/env bash
# STAGE 1 of the parsec v2 tier's local pipeline.
#
# Shadow-copy the 10 authored bench-aap2-* tasks into <repo>/e2e/parsec/v2/harbor-tasks-v2/
# and rewrite each task.toml's docker_image to the parsec-agent-base image (same as v1 — the
# ubi9 base ships nodejs + npm, which the claude-code agent bootstrap needs; build it with
# utils/build-parsec-agent-base.sh).
#
# ${BACKEND_MCP_URL} is left alone here; start-sims-v2.sh replaces it per task with that
# task's own kaegis URL once the sims are up.
#
# The authored task tree is NOT committed to this repo (same deliberate convention as v1's
# harbor-tasks/): it is regenerated at run time from an external checkout, so the source has
# no default — see PARSEC_HARBOR_TASKS_V2_SRC below.
#
# Order of operations for the whole v2 tier — see ci/benchmarks/parsec/README.md:
#   1. utils/patch-harbor-tasks-v2.sh    (this script)      → harbor-tasks-v2/
#   2. utils/bake-aap2-skill.sh          (kaegis artifacts)
#   3. utils/start-sims-v2.sh            (10 sims + per-task MCP URLs into harbor-tasks-v2/)
#   4. utils/patch-harbor-tasks-v2.1.sh  (container fixes)  → harbor-tasks-v2.1/
#   5. TIER=v2 bash ci/benchmarks/lib/run_suite.sh parsec
#
# Overrides (env vars):
#   PARSEC_HARBOR_TASKS_V2_SRC   — the authored tasks_v2/ tree (REQUIRED; no default —
#                                  it is an internal RH/authored tree, so no path is right
#                                  for anyone but its author)
#   PARSEC_HARBOR_TASKS_V2_STAGE — stage-1 destination, which stage 3 mutates and stage 4
#                                  reads (default: <repo>/e2e/parsec/v2/harbor-tasks-v2).
#                                  Under the gitignored e2e/, same convention as v1's shadow
#                                  and skillsbench's e2e/skillsbench-src.
#
# Rerun. Idempotent — deletes and recreates the shadow. NB rerunning this discards the
# concrete per-task MCP URLs stage 3 wrote, so rerun stages 3 and 4 after it.
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd -P)
REPO=$(cd "$HERE/../../../.." && pwd -P)
SRC=${PARSEC_HARBOR_TASKS_V2_SRC:?set PARSEC_HARBOR_TASKS_V2_SRC to your local authored parsec tasks_v2/ checkout}
DST=${PARSEC_HARBOR_TASKS_V2_STAGE:-$REPO/e2e/parsec/v2/harbor-tasks-v2}

[ -d "$SRC" ] || { echo "missing tasks_v2 source: $SRC (override with PARSEC_HARBOR_TASKS_V2_SRC)" >&2; exit 1; }

echo "→ source: $SRC"
echo "→ shadow: $DST"

rm -rf "$DST"
mkdir -p "$DST"

for task in "$SRC"/bench-aap2-*/; do
  [ -d "$task" ] || continue
  name=$(basename "$task")
  cp -R "$task" "$DST/$name"
  # Rewrite docker_image to the v1 base (has node+npm for claude-code bootstrap).
  sed -i.bak -E \
    's|^docker_image = ".*"$|docker_image = "localhost/parsec-agent-base:latest"|' \
    "$DST/$name/task.toml"
  rm -f "$DST/$name/task.toml.bak"
done

count=$(find "$DST" -maxdepth 1 -type d -name 'bench-aap2-*' | wc -l | tr -d ' ')
[ "$count" -gt 0 ] || { echo "no bench-aap2-* tasks found under $SRC" >&2; exit 1; }

echo "Patched $count tasks in $DST"
echo "Next: utils/bake-aap2-skill.sh, then utils/start-sims-v2.sh."
