#!/usr/bin/env bash
# STAGE 2 of the parsec v2 tier's local pipeline.
#
# Bake the aap2 kaegis "skill" (SKILL.md + api.json + schema.json) once, offline. Every
# task's per-task skills-store is then a copy of this output with db.json swapped for that
# task's own seed.json — that swap is what makes v2's 10 simulators independent, and it
# happens in stage 3 (utils/start-sims-v2.sh).
#
# INTERNAL-ONLY. Both inputs are IBM/RH-internal and neither has a default:
#   * the aap2 OpenAPI spec is not in the public rhpds/parsec repo, and
#   * kaegis (the simulation harness) lives at github.ibm.com/kaegis/simulation-harness.
# There is therefore no HARNESS_SRC/SPEC path that is correct for anyone but its author, so
# both are required env vars and this script fails loudly naming them rather than pointing at
# somebody's laptop.
#
# Overrides (env vars):
#   PARSEC_AAP2_SPEC_SRC — the aap2 OpenAPI spec JSON (REQUIRED; no default)
#   HARNESS_SRC          — a github.ibm.com/kaegis/simulation-harness checkout
#                          (REQUIRED; no default). Needs `uv` on PATH.
#   PARSEC_V2_WORK       — runtime scratch root for the v2 tier
#                          (default: <repo>/e2e/parsec/v2 — gitignored). Holds the baked
#                          artifacts, the generated harness config, the per-task
#                          skills-store shadows, the sims manifest and the sim logs. This is
#                          deliberately NOT under ci/benchmarks/parsec/: a committed source
#                          tree must not double as a runtime scratch directory.
#
# Idempotent — wipes any prior bake output first, so stale files from a previous schema
# variant cannot linger alongside the freshly generated artifacts.
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd -P)
REPO=$(cd "$HERE/../../../.." && pwd -P)
V2WORK=${PARSEC_V2_WORK:-$REPO/e2e/parsec/v2}
SPEC=${PARSEC_AAP2_SPEC_SRC:?set PARSEC_AAP2_SPEC_SRC to your local parsec aap2 OpenAPI spec (e.g. .../parsec/aap2.json)}
HARNESS_SRC=${HARNESS_SRC:?set HARNESS_SRC to your github.ibm.com/kaegis/simulation-harness checkout}
OUT="$V2WORK/harness-src/skills-store"

[ -f "$SPEC" ] || { echo "missing spec: $SPEC (override with PARSEC_AAP2_SPEC_SRC)" >&2; exit 1; }
[ -d "$HARNESS_SRC" ] || { echo "missing simulation-harness at $HARNESS_SRC (override with HARNESS_SRC)" >&2; exit 1; }

rm -rf "$OUT/aap2"
mkdir -p "$OUT" "$V2WORK/harness-src" "$V2WORK/logs/sims-v2"

# The setup CLI writes to <skills.folder>/<name>/… — override skills.folder
# to our v2-local path via a tiny config override.
cat > "$V2WORK/harness-src/harness.local.yaml" <<YAML
llm:
  provider: openai
  skill_generation_model: azure/gpt-5.4
  skill_generation_max_tokens: 40000
  simulation_model: azure/gpt-5.4
  temperature: 0
skills:
  folder: $OUT
sessions:
  max_messages: 100
  idle_timeout_seconds: 3600
  max_concurrent_queue_depth: 8
  agent_recursion_limit: 50
generation:
  concurrency: 5
  chunk_threshold: 40
  stage_timeout_seconds: 420
  extract: { temperature: 0.0, max_tokens: 20000 }
  classify: { temperature: 0.0, max_tokens: 10000 }
  schema_seed: { temperature: 0.0, max_tokens: 20000 }
  operation: { temperature: 0.2, max_tokens: 10000 }
  scenarios_enabled: true
  scenarios_count: 5
  scenarios: { temperature: 0.4, max_tokens: 3000 }
mcp:
  transport: sse
server:
  host: 127.0.0.1
  port: 8086
logging:
  level: INFO
  destination_folder: $V2WORK/logs/sims-v2
YAML

cd "$HARNESS_SRC"
uv run python -m simulation_harness.setup_cli "$SPEC" \
  --name aap2 \
  --config "$V2WORK/harness-src/harness.local.yaml"

echo "Baked skill artifacts:"
ls "$OUT/aap2/"
echo "Next: utils/start-sims-v2.sh"
